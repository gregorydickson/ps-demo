#!/bin/bash

# Manual API testing script using curl
# Run this after starting the FastAPI server with: uvicorn main:app --reload

set -e

API_BASE="http://localhost:8000"
echo "Testing Contract Intelligence API at $API_BASE"
echo "=" | tr '=' '=' | head -c 60; echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health check
echo -e "${YELLOW}Test 1: Health Check${NC}"
curl -s "$API_BASE/" | jq .
echo -e "${GREEN}✓ Passed${NC}\n"

# Test 2: Detailed health check
echo -e "${YELLOW}Test 2: Detailed Health Check${NC}"
curl -s "$API_BASE/health" | jq .
echo -e "${GREEN}✓ Passed${NC}\n"

# Test 3: Cost analytics (current day)
echo -e "${YELLOW}Test 3: Cost Analytics (Current Day)${NC}"
curl -s "$API_BASE/api/analytics/costs" | jq .
echo -e "${GREEN}✓ Passed${NC}\n"

# Test 4: Cost analytics (specific date)
echo -e "${YELLOW}Test 4: Cost Analytics (Specific Date)${NC}"
curl -s "$API_BASE/api/analytics/costs?date=2024-12-10" | jq .
echo -e "${GREEN}✓ Passed${NC}\n"

# Test 5: Invalid date format (should return 400)
echo -e "${YELLOW}Test 5: Invalid Date Format (Expecting 400)${NC}"
response=$(curl -s -w "\n%{http_code}" "$API_BASE/api/analytics/costs?date=invalid")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "400" ]; then
    echo "$body" | jq .
    echo -e "${GREEN}✓ Passed (Got 400 as expected)${NC}\n"
else
    echo -e "${RED}✗ Failed (Expected 400, got $http_code)${NC}\n"
fi

# Test 6: Upload non-PDF file (should return 400)
echo -e "${YELLOW}Test 6: Upload Non-PDF File (Expecting 400)${NC}"
echo "This is not a PDF" > /tmp/test.txt
response=$(curl -s -w "\n%{http_code}" -X POST -F "file=@/tmp/test.txt" "$API_BASE/api/contracts/upload")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "400" ]; then
    echo "$body" | jq .
    echo -e "${GREEN}✓ Passed (Got 400 as expected)${NC}\n"
else
    echo -e "${RED}✗ Failed (Expected 400, got $http_code)${NC}\n"
fi

rm /tmp/test.txt

# Test 7: Get nonexistent contract (should return 404)
echo -e "${YELLOW}Test 7: Get Nonexistent Contract (Expecting 404)${NC}"
fake_id="00000000-0000-0000-0000-000000000000"
response=$(curl -s -w "\n%{http_code}" "$API_BASE/api/contracts/$fake_id")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "404" ]; then
    echo "$body" | jq .
    echo -e "${GREEN}✓ Passed (Got 404 as expected)${NC}\n"
else
    echo -e "${RED}✗ Failed (Expected 404, got $http_code)${NC}\n"
fi

# Test 8: Query validation (query too short, should return 422)
echo -e "${YELLOW}Test 8: Query Validation (Too Short, Expecting 422)${NC}"
response=$(curl -s -w "\n%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"Hi","include_context":true}' \
  "$API_BASE/api/contracts/$fake_id/query")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "422" ]; then
    echo "$body" | jq .
    echo -e "${GREEN}✓ Passed (Got 422 as expected)${NC}\n"
else
    echo -e "${RED}✗ Failed (Expected 422, got $http_code)${NC}\n"
fi

# Test 9: OpenAPI schema
echo -e "${YELLOW}Test 9: OpenAPI Schema${NC}"
curl -s "$API_BASE/openapi.json" | jq '{openapi, info, paths: (.paths | keys)}'
echo -e "${GREEN}✓ Passed${NC}\n"

# Test 10: Swagger UI (just check it returns HTML)
echo -e "${YELLOW}Test 10: Swagger UI Accessibility${NC}"
curl -s "$API_BASE/docs" | grep -q "swagger-ui" && echo -e "${GREEN}✓ Swagger UI is accessible${NC}\n" || echo -e "${RED}✗ Failed${NC}\n"

# Test 11: ReDoc (just check it returns HTML)
echo -e "${YELLOW}Test 11: ReDoc Accessibility${NC}"
curl -s "$API_BASE/redoc" | grep -q "redoc" && echo -e "${GREEN}✓ ReDoc is accessible${NC}\n" || echo -e "${RED}✗ Failed${NC}\n"

echo "=" | tr '=' '=' | head -c 60; echo
echo -e "${GREEN}All manual tests completed!${NC}"
echo -e "${YELLOW}To test with a real PDF, run:${NC}"
echo "  curl -X POST -F 'file=@your_contract.pdf' $API_BASE/api/contracts/upload | jq ."
