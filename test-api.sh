#!/bin/bash
# Test script for Model Router API

BASE_URL="http://localhost:8000"
API_KEY="dev-key-change-me"

echo "=== Model Router API Test Suite ==="
echo

# Test 1: Health check
echo "1. Testing health endpoint..."
curl -s "${BASE_URL}/v1/health" | jq .
echo

# Test 2: Simple prompt (should route to small model)
echo "2. Testing simple prompt (summary)..."
curl -s -X POST "${BASE_URL}/v1/route" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_KEY}" \
  -d '{
    "prompt": "Summarize this log file in one sentence",
    "context": {}
  }' | jq .
echo

# Test 3: Medium prompt (should route to balanced model)
echo "3. Testing medium prompt (code generation)..."
curl -s -X POST "${BASE_URL}/v1/route" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_KEY}" \
  -d '{
    "prompt": "Write a Python script to parse JSON files and extract the email addresses",
    "context": {
      "max_tokens": 500,
      "tools_available": ["python", "bash"]
    }
  }' | jq .
echo

# Test 4: Complex prompt (should route to premium model)
echo "4. Testing complex prompt (analysis + tools)..."
curl -s -X POST "${BASE_URL}/v1/route" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_KEY}" \
  -d '{
    "prompt": "Analyze the performance of our Docker containers, identify bottlenecks using docker stats, check database query logs, and create a monitoring script with alerting for email and Slack",
    "context": {
      "max_tokens": 2000,
      "tools_available": ["docker", "kubectl", "python", "bash", "sql"]
    }
  }' | jq .
echo

# Test 5: Stats
echo "5. Testing stats endpoint..."
curl -s "${BASE_URL}/v1/stats" \
  -H "Authorization: Bearer ${API_KEY}" | jq .
echo

echo "=== Test suite complete ==="
