# Authentication Setup - Installation Notes

## Dependencies Required

The following Python packages need to be installed via pip:

```bash
pip install 'passlib[bcrypt]' 'python-jose[cryptography]' sendgrid python-multipart email-validator
```

**Note**: If you encounter "externally-managed-environment" error on macOS, you have two options:

### Option 1: Use Virtual Environment (Recommended)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Option 2: User Installation
```bash
pip install --user 'passlib[bcrypt]' 'python-jose[cryptography]' sendgrid python-multipart email-validator
```

## Environment Variables

Add to your `.env` file:

```bash
# JWT Configuration
JWT_SECRET_KEY=your-secret-key-here  # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# Email Configuration (SendGrid)
SENDGRID_API_KEY=your-sendgrid-api-key
FROM_EMAIL=noreply@your-domain.com

# Frontend URL for email verification links
FRONTEND_URL=http://localhost:3000
```

## Database Migration

Already completed! Tables created:
- ✅ `users`
- ✅ `email_verification_tokens`
- ✅ `refresh_tokens`

## Testing Auth Endpoints

After installing dependencies, test with:

```bash
# Start the API server
uvicorn api.main:app --reload

# Test registration
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'

# Test login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=testpass123"
```
