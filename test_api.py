"""
Tests for Model Router API
Tests routing logic, quota tracking, and error cases
"""

import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import json

# Import the app
from main import app, route_model, detect_task_type, count_tools, estimate_tokens

# Test client
client = TestClient(app)

# Test fixtures
@pytest.fixture
def valid_headers():
    """Valid authorization headers"""
    os.environ["API_KEY"] = "test-api-key-123"
    return {"Authorization": "Bearer test-api-key-123"}

@pytest.fixture
def invalid_headers():
    """Invalid authorization headers"""
    return {"Authorization": "Bearer wrong-key"}

# === Tests for routing logic ===

def test_detect_task_type_summary():
    """Test task type detection for summaries"""
    prompt = "Summarize the main points from this document"
    assert detect_task_type(prompt) == "summary"

def test_detect_task_type_code():
    """Test task type detection for code tasks"""
    prompt = "Write a Python function to calculate fibonacci"
    assert detect_task_type(prompt) == "code"

def test_detect_task_type_analysis():
    """Test task type detection for analysis tasks"""
    prompt = "Analyze the performance issues in this system"
    assert detect_task_type(prompt) == "analysis"

def test_detect_task_type_deployment():
    """Test task type detection for deployment tasks"""
    prompt = "Deploy this Docker container to Kubernetes"
    assert detect_task_type(prompt) == "deployment"

def test_detect_task_type_general():
    """Test task type detection falls back to general"""
    prompt = "What is the weather like?"
    assert detect_task_type(prompt) == "general"

def test_count_tools():
    """Test tool counting in prompts"""
    prompt = "Run a docker container, then use kubectl to deploy"
    context = {}
    count = count_tools(prompt, context)
    assert count >= 2  # docker, kubectl

def test_count_tools_with_context():
    """Test tool counting includes context tools"""
    prompt = "Process some data"
    context = {"tools_available": ["curl", "grep", "sed"]}
    count = count_tools(prompt, context)
    assert count >= 3  # tools in context

def test_estimate_tokens():
    """Test token estimation"""
    prompt = "This is a test prompt"
    tokens = estimate_tokens(prompt)
    assert tokens == 5  # 5 words

def test_route_model_simple():
    """Test routing to simple model"""
    prompt = "Summarize this short text"
    context = {}
    routing = route_model(prompt, context)

    assert routing["complexity"] == "low"
    assert "llama" in routing["model"].lower()
    assert routing["confidence"] >= 0.8

def test_route_model_medium():
    """Test routing to medium model"""
    prompt = "Help me with a moderately complex task"
    context = {}
    routing = route_model(prompt, context)

    assert routing["complexity"] == "medium"
    assert routing["confidence"] >= 0.7

def test_route_model_complex():
    """Test routing to complex/premium model"""
    prompt = "Write a complex Python script that handles error cases and edge cases with proper logging"
    context = {}
    routing = route_model(prompt, context)

    assert routing["complexity"] == "high"
    assert "claude" in routing["model"].lower()
    assert routing["confidence"] >= 0.9

# === Tests for HTTP endpoints ===

def test_health_endpoint():
    """Test /v1/health endpoint"""
    response = client.get("/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "models" in data

def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "docs" in data

def test_route_endpoint_success(valid_headers):
    """Test /v1/route endpoint with valid request"""
    response = client.post(
        "/v1/route",
        json={
            "prompt": "Summarize this short document",
            "context": {}
        },
        headers=valid_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "model" in data
    assert "reasoning" in data
    assert "confidence" in data
    assert "complexity" in data
    assert "estimated_cost" in data

def test_route_endpoint_missing_auth():
    """Test /v1/route without auth"""
    response = client.post(
        "/v1/route",
        json={
            "prompt": "Test prompt",
            "context": {}
        }
    )

    assert response.status_code == 403 or response.status_code == 422

def test_route_endpoint_invalid_auth(invalid_headers):
    """Test /v1/route with invalid auth"""
    response = client.post(
        "/v1/route",
        json={
            "prompt": "Test prompt",
            "context": {}
        },
        headers=invalid_headers
    )

    assert response.status_code == 403

def test_stats_endpoint_success(valid_headers):
    """Test /v1/stats endpoint"""
    response = client.get("/v1/stats", headers=valid_headers)

    assert response.status_code == 200
    data = response.json()
    assert "requests_today" in data
    assert "requests_month" in data
    assert "quota_remaining" in data
    assert "total_saved" in data
    assert "models_used" in data

def test_stats_endpoint_invalid_auth(invalid_headers):
    """Test /v1/stats with invalid auth"""
    response = client.get("/v1/stats", headers=invalid_headers)

    assert response.status_code == 403

# === Tests for /v1/generate endpoint ===

@patch('main.generate_from_ollama')
def test_generate_endpoint_low_complexity(mock_ollama, valid_headers):
    """Test /v1/generate with low complexity (uses Ollama)"""
    mock_ollama.return_value = {
        "generation": "This is the generated output",
        "tokens_used": 10,
        "cost": 0.0
    }

    response = client.post(
        "/v1/generate",
        json={
            "prompt": "Generate a short response",
            "complexity": "low",
            "max_tokens": 512
        },
        headers=valid_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["complexity"] == "low"
    assert "ollama" in data["model"].lower()
    assert "generation" in data
    assert data["tokens_used"] >= 0
    assert data["cost_saved"] > 0  # Should save money using local model

@patch('main.generate_from_openrouter')
def test_generate_endpoint_high_complexity(mock_openrouter, valid_headers):
    """Test /v1/generate with high complexity (uses OpenRouter)"""
    mock_openrouter.return_value = {
        "generation": "This is a sophisticated response",
        "tokens_used": 50,
        "cost": 0.005
    }

    response = client.post(
        "/v1/generate",
        json={
            "prompt": "Solve a complex problem",
            "complexity": "high",
            "max_tokens": 2048
        },
        headers=valid_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["complexity"] == "high"
    assert "claude" in data["model"].lower()
    assert "generation" in data
    assert data["tokens_used"] >= 0

@patch('main.generate_from_ollama')
def test_generate_endpoint_medium_complexity(mock_ollama, valid_headers):
    """Test /v1/generate with medium complexity"""
    mock_ollama.return_value = {
        "generation": "This is a medium output",
        "tokens_used": 25,
        "cost": 0.0
    }

    response = client.post(
        "/v1/generate",
        json={
            "prompt": "Generate something of medium difficulty",
            "complexity": "medium"
        },
        headers=valid_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["complexity"] == "medium"

def test_generate_endpoint_invalid_complexity(valid_headers):
    """Test /v1/generate with invalid complexity"""
    response = client.post(
        "/v1/generate",
        json={
            "prompt": "Test",
            "complexity": "invalid"
        },
        headers=valid_headers
    )

    assert response.status_code == 400

def test_generate_endpoint_missing_prompt(valid_headers):
    """Test /v1/generate without prompt"""
    response = client.post(
        "/v1/generate",
        json={
            "complexity": "low"
        },
        headers=valid_headers
    )

    assert response.status_code == 422  # Validation error

def test_generate_endpoint_invalid_auth(invalid_headers):
    """Test /v1/generate with invalid auth"""
    response = client.post(
        "/v1/generate",
        json={
            "prompt": "Test prompt",
            "complexity": "low"
        },
        headers=invalid_headers
    )

    assert response.status_code == 403

# === Tests for quota tracking ===

@patch('main.generate_from_ollama')
def test_quota_tracking_decrements(mock_ollama, valid_headers):
    """Test that quota tracking works and decrements"""
    mock_ollama.return_value = {
        "generation": "Test output",
        "tokens_used": 10,
        "cost": 0.0
    }

    # Make a few requests
    for _ in range(3):
        response = client.post(
            "/v1/route",
            json={"prompt": "Test", "context": {}},
            headers=valid_headers
        )
        assert response.status_code == 200

    # Check stats
    stats_response = client.get("/v1/stats", headers=valid_headers)
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["requests_today"] >= 3

# === Tests for error handling ===

@patch('main.generate_from_ollama')
def test_generate_handles_ollama_error(mock_ollama, valid_headers):
    """Test /v1/generate handles Ollama failures gracefully"""
    from fastapi import HTTPException
    mock_ollama.side_effect = HTTPException(status_code=503, detail="Ollama unavailable")

    response = client.post(
        "/v1/generate",
        json={
            "prompt": "Test",
            "complexity": "low"
        },
        headers=valid_headers
    )

    assert response.status_code == 503

def test_route_endpoint_missing_prompt(valid_headers):
    """Test /v1/route with empty prompt"""
    response = client.post(
        "/v1/route",
        json={
            "prompt": "",
            "context": {}
        },
        headers=valid_headers
    )

    assert response.status_code == 422  # Validation error

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
