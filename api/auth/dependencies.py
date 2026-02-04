"""Authentication dependencies for protecting routes."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from api.auth import security

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict:
    """
    Extract and validate current user from JWT token.
    
    Args:
        token: JWT access token from Authorization header or None
        
    Returns:
        Dictionary with user info: {"id": user_id, "email": email}
        
    Raises:
        HTTPException: If token is invalid or missing required claims
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = security.decode_token(token)
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {"id": user_id, "email": email}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(token: str | None = Depends(oauth2_scheme)) -> dict | None:
    """
    Get current user if authenticated, None otherwise.
    Useful for routes that work for both authenticated and guest users.
    """
    if not token:
        return None
        
    try:
        return await get_current_user(token)
    except HTTPException:
        return None
