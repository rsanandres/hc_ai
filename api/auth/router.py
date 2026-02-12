"""Authentication router with registration, login, verification, and token management."""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text

from api.auth import security, email, models
from api.auth.dependencies import get_current_user
from api.database.postgres import get_engine

router = APIRouter(tags=["authentication"])


@router.post("/register", status_code=201, response_model=models.MessageResponse)
async def register(user: models.UserRegister):
    """
    Register a new user account.
    
    - Creates user with hashed password
    - Generates email verification token
    - Sends verification email
    """
    async with get_engine().begin() as conn:
        # Check if user exists
        existing = await conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": user.email}
        )
        if existing.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        # Create user
        hashed_pw = security.hash_password(user.password)
        result = await conn.execute(
            text("""
                INSERT INTO users (email, password_hash, is_verified) 
                VALUES (:email, :hash, false) 
                RETURNING id
            """),
            {"email": user.email, "hash": hashed_pw}
        )
        user_id = result.fetchone()[0]
        
        # Create verification token
        token = security.generate_verification_token()
        expires = datetime.utcnow() + timedelta(hours=24)
        await conn.execute(
            text("""
                INSERT INTO email_verification_tokens (user_id, token, expires_at) 
                VALUES (:uid, :token, :exp)
            """),
            {"uid": user_id, "token": token, "exp": expires}
        )
    
    # Send verification email
    email.send_verification_email(user.email, token)
    
    return models.MessageResponse(
        message="Registration successful. Please check your email to verify your account."
    )


@router.get("/verify", response_model=models.MessageResponse)
async def verify_email(token: str):
    """
    Verify user email address using token from email link.
    
    - Validates token and expiration
    - Marks user as verified
    - Deletes used token
    """
    async with get_engine().begin() as conn:
        # Find token
        result = await conn.execute(
            text("""
                SELECT user_id, expires_at 
                FROM email_verification_tokens 
                WHERE token = :token
            """),
            {"token": token}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=400,
                detail="Invalid verification token"
            )
        
        user_id, expires_at = row
        if datetime.utcnow() > expires_at:
            raise HTTPException(
                status_code=400,
                detail="Verification token expired"
            )
        
        # Mark user as verified
        await conn.execute(
            text("UPDATE users SET is_verified = true WHERE id = :uid"),
            {"uid": user_id}
        )
        
        # Delete used token
        await conn.execute(
            text("DELETE FROM email_verification_tokens WHERE token = :token"),
            {"token": token}
        )
    
    return models.MessageResponse(message="Email verified successfully. You can now log in.")


@router.post("/login", response_model=models.UserLogin)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Login with email and password.
    
    - Validates credentials
    - Checks email verification
    - Creates access and refresh tokens
    - Sets refresh token as HttpOnly cookie
    """
    async with get_engine().begin() as conn:
        # Get user
        result = await conn.execute(
            text("""
                SELECT id, email, password_hash, is_verified 
                FROM users 
                WHERE email = :email
            """),
            {"email": form_data.username}  # OAuth2PasswordRequestForm uses 'username' field
        )
        user = result.fetchone()
        
        if not user or not security.verify_password(form_data.password, user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )
        
        if not user.is_verified:
            raise HTTPException(
                status_code=403,
                detail="Please verify your email first"
            )
        
        # Create tokens
        access_token = security.create_access_token({
            "sub": str(user.id),
            "email": user.email
        })
        refresh_token = security.create_refresh_token({"sub": str(user.id)})
        
        # Store refresh token
        expires = datetime.utcnow() + timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS)
        await conn.execute(
            text("""
                INSERT INTO refresh_tokens (user_id, token, expires_at) 
                VALUES (:uid, :token, :exp)
            """),
            {"uid": user.id, "token": refresh_token, "exp": expires}
        )
    
    # Set httpOnly cookie for refresh token
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,  # HTTPS only in production
        samesite="lax",
        max_age=30 * 24 * 60 * 60  # 30 days
    )
    
    return models.UserLogin(
        access_token=access_token,
        user_id=str(user.id)
    )


@router.post("/refresh", response_model=models.TokenRefresh)
async def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(None)
):
    """
    Refresh access token using refresh token from cookie.
    
    - Validates refresh token
    - Rotates refresh token (invalidates old, creates new)
    - Returns new access token
    """
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token missing"
        )
    
    try:
        payload = security.decode_token(refresh_token)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token"
        )
    
    async with get_engine().begin() as conn:
        # Check if token exists and not revoked
        result = await conn.execute(
            text("""
                SELECT expires_at, revoked 
                FROM refresh_tokens 
                WHERE token = :token AND user_id = :uid
            """),
            {"token": refresh_token, "uid": user_id}
        )
        token_record = result.fetchone()
        
        if not token_record or token_record.revoked:
            raise HTTPException(
                status_code=401,
                detail="Refresh token revoked"
            )
        
        if datetime.utcnow() > token_record.expires_at:
            raise HTTPException(
                status_code=401,
                detail="Refresh token expired"
            )
        
        # Get user email
        result = await conn.execute(
            text("SELECT email FROM users WHERE id = :uid"),
            {"uid": user_id}
        )
        user = result.fetchone()
        
        # Rotate tokens (revoke old, create new)
        await conn.execute(
            text("UPDATE refresh_tokens SET revoked = true WHERE token = :token"),
            {"token": refresh_token}
        )
        
        new_access = security.create_access_token({
            "sub": user_id,
            "email": user.email
        })
        new_refresh = security.create_refresh_token({"sub": user_id})
        
        expires = datetime.utcnow() + timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS)
        await conn.execute(
            text("""
                INSERT INTO refresh_tokens (user_id, token, expires_at) 
                VALUES (:uid, :token, :exp)
            """),
            {"uid": user_id, "token": new_refresh, "exp": expires}
        )
    
    # Update cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 60 * 60
    )
    
    return models.TokenRefresh(access_token=new_access)


@router.post("/logout", response_model=models.MessageResponse)
async def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(None)
):
    """
    Logout user by revoking refresh token.
    
    - Revokes refresh token in database
    - Deletes refresh token cookie
    """
    if refresh_token:
        async with get_engine().begin() as conn:
            await conn.execute(
                text("UPDATE refresh_tokens SET revoked = true WHERE token = :token"),
                {"token": refresh_token}
            )
    
    response.delete_cookie("refresh_token")
    return models.MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=models.UserInfo)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user information."""
    return models.UserInfo(
        id=current_user["id"],
        email=current_user["email"]
    )
