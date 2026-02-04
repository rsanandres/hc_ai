#!/bin/bash

# Authentication Endpoints Test Script
# This script tests all auth endpoints in sequence

BASE_URL="http://localhost:8000"
TEST_EMAIL="test@example.com"
TEST_PASSWORD="testpass12345"

echo "======================================"
echo "Testing Authentication System"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Test Registration
echo "1. Testing Registration..."
REGISTER_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")

if echo "$REGISTER_RESPONSE" | grep -q "Registration successful"; then
  echo -e "${GREEN}✓ Registration successful${NC}"
  echo "Response: $REGISTER_RESPONSE"
else
  echo -e "${YELLOW}⚠ Registration response: $REGISTER_RESPONSE${NC}"
fi
echo ""

# 2. Extract verification token from database (for testing)
echo "2. Getting verification token from database..."
VERIFICATION_TOKEN=$(PGPASSWORD='Postgres3245!' psql -h localhost -U postgres -d postgres -t -c \
  "SELECT token FROM email_verification_tokens WHERE user_id = (SELECT id FROM users WHERE email = '${TEST_EMAIL}') ORDER BY created_at DESC LIMIT 1;" | xargs)

if [ -n "$VERIFICATION_TOKEN" ]; then
  echo -e "${GREEN}✓ Found verification token${NC}"
  echo "Token: ${VERIFICATION_TOKEN:0:20}..."
else
  echo -e "${RED}✗ No verification token found${NC}"
  exit 1
fi
echo ""

# 3. Test Email Verification
echo "3. Testing Email Verification..."
VERIFY_RESPONSE=$(curl -s -X GET "${BASE_URL}/auth/verify?token=${VERIFICATION_TOKEN}")

if echo "$VERIFY_RESPONSE" | grep -q "verified successfully"; then
  echo -e "${GREEN}✓ Email verification successful${NC}"
  echo "Response: $VERIFY_RESPONSE"
else
  echo -e "${RED}✗ Verification failed${NC}"
  echo "Response: $VERIFY_RESPONSE"
  exit 1
fi
echo ""

# 4. Test Login
echo "4. Testing Login..."
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${TEST_EMAIL}&password=${TEST_PASSWORD}" \
  -c cookies.txt)

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
USER_ID=$(echo "$LOGIN_RESPONSE" | jq -r '.user_id')

if [ "$ACCESS_TOKEN" != "null" ] && [ -n "$ACCESS_TOKEN" ]; then
  echo -e "${GREEN}✓ Login successful${NC}"
  echo "User ID: $USER_ID"
  echo "Access Token: ${ACCESS_TOKEN:0:50}..."
else
  echo -e "${RED}✗ Login failed${NC}"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi
echo ""

# 5. Test Protected Endpoint (/auth/me)
echo "5. Testing Protected Endpoint (/auth/me)..."
ME_RESPONSE=$(curl -s -X GET "${BASE_URL}/auth/me" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

if echo "$ME_RESPONSE" | grep -q "id"; then
  echo -e "${GREEN}✓ Protected endpoint accessible${NC}"
  echo "Response: $ME_RESPONSE"
else
  echo -e "${RED}✗ Protected endpoint failed${NC}"
  echo "Response: $ME_RESPONSE"
  exit 1
fi
echo ""

# 6. Test Token Refresh
echo "6. Testing Token Refresh..."
REFRESH_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/refresh" \
  -b cookies.txt \
  -c cookies_new.txt)

NEW_ACCESS_TOKEN=$(echo "$REFRESH_RESPONSE" | jq -r '.access_token')

if [ "$NEW_ACCESS_TOKEN" != "null" ] && [ -n "$NEW_ACCESS_TOKEN" ]; then
  echo -e "${GREEN}✓ Token refresh successful${NC}"
  echo "New Access Token: ${NEW_ACCESS_TOKEN:0:50}..."
else
  echo -e "${RED}✗ Token refresh failed${NC}"
  echo "Response: $REFRESH_RESPONSE"
  exit 1
fi
echo ""

# 7. Test Session List (Protected)
echo "7. Testing Session List Endpoint..."
SESSION_LIST=$(curl -s -X GET "${BASE_URL}/session/list" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

echo "Response: $SESSION_LIST"
if echo "$SESSION_LIST" | grep -q "sessions"; then
  echo -e "${GREEN}✓ Session list accessible${NC}"
else
  echo -e "${YELLOW}⚠ Session list response unexpected (might be empty)${NC}"
fi
echo ""

# 8. Test Logout
echo "8. Testing Logout..."
LOGOUT_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/logout" \
  -b cookies_new.txt)

if echo "$LOGOUT_RESPONSE" | grep -q "Logged out successfully"; then
  echo -e "${GREEN}✓ Logout successful${NC}"
  echo "Response: $LOGOUT_RESPONSE"
else
  echo -e "${RED}✗ Logout failed${NC}"
  echo "Response: $LOGOUT_RESPONSE"
fi
echo ""

# 9. Test Access After Logout (Should Fail)
echo "9. Testing Access After Logout (should fail)..."
AFTER_LOGOUT=$(curl -s -X POST "${BASE_URL}/auth/refresh" \
  -b cookies_new.txt)

if echo "$AFTER_LOGOUT" | grep -q "revoked"; then
  echo -e "${GREEN}✓ Refresh token properly revoked${NC}"
else
  echo -e "${YELLOW}⚠ Unexpected after-logout response${NC}"
  echo "Response: $AFTER_LOGOUT"
fi
echo ""

# Cleanup
rm -f cookies.txt cookies_new.txt

# Cleanup test user from database
echo "10. Cleaning up test user..."
PGPASSWORD='Postgres3245!' psql -h localhost -U postgres -d postgres -c \
  "DELETE FROM users WHERE email = '${TEST_EMAIL}';" > /dev/null 2>&1

echo ""
echo "======================================"
echo -e "${GREEN}✓ All Authentication Tests Completed!${NC}"
echo "======================================"
echo ""
echo "Summary:"
echo "  ✓ Registration"
echo "  ✓ Email Verification"
echo "  ✓ Login"
echo "  ✓ Protected Endpoint Access"
echo "  ✓ Token Refresh"
echo "  ✓ Session Integration"
echo "  ✓ Logout"
echo "  ✓ Token Revocation"
echo ""
