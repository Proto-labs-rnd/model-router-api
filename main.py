"""
Model Router API - Intelligent LLM routing
Routes prompts to optimal models based on task complexity
"""

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
import json
import hashlib
from datetime import datetime, date
import redis
import httpx

# Configuration
API_KEY = os.getenv("API_KEY", "dev-key-change-me")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
FREE_TIER_DAILY = int(os.getenv("FREE_TIER_DAILY_REQUESTS", 100))

# Initialize FastAPI
app = FastAPI(
    title="Model Router API",
    description="Intelligent model routing for LLM applications",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis client (will connect lazily)
redis_client = None

# Models
class RoutingRequest(BaseModel):
    prompt: str = Field(..., description="The prompt to route", min_length=1)
    context: Optional[Dict[str, Any]] = Field(
        default={},
        description="Additional context (max_tokens, tools_available, etc.)"
    )

class RoutingResponse(BaseModel):
    model: str = Field(..., description="Selected model")
    reasoning: str = Field(..., description="Why this model was chosen")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Routing confidence")
    estimated_cost: float = Field(..., description="Estimated cost in USD")
    estimated_savings: float = Field(..., description="Estimated savings vs using top model")
    complexity: str = Field(..., description="Task complexity: low, medium, or high")

class StatsResponse(BaseModel):
    requests_today: int = Field(..., description="Requests made today")
    requests_month: int = Field(..., description="Requests made this month")
    quota_remaining: int = Field(..., description="Remaining quota")
    total_saved: float = Field(..., description="Total money saved in USD")
    models_used: Dict[str, int] = Field(..., description="Usage count per model")

class HealthResponse(BaseModel):
    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    models: Dict[str, str] = Field(..., description="Model provider status")

class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="The prompt to generate from", min_length=1)
    complexity: str = Field(
        default="medium",
        description="Task complexity: low, medium, or high"
    )
    context: Optional[Dict[str, Any]] = Field(
        default={},
        description="Additional context"
    )
    max_tokens: Optional[int] = Field(
        default=1024,
        description="Maximum tokens to generate"
    )

class GenerateResponse(BaseModel):
    model: str = Field(..., description="Model used for generation")
    generation: str = Field(..., description="Generated text")
    reasoning: str = Field(..., description="Routing reasoning")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence")
    tokens_used: int = Field(..., description="Tokens used in generation")
    cost: float = Field(..., description="Cost in USD")
    cost_saved: float = Field(..., description="Cost saved vs premium model")
    complexity: str = Field(..., description="Task complexity used")

# Helper functions
def get_redis():
    """Get or create Redis connection"""
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=0,
                decode_responses=True
            )
            redis_client.ping()
        except Exception as e:
            print(f"Warning: Redis connection failed: {e}")
            redis_client = False
    return redis_client

def estimate_tokens(text: str) -> int:
    """Estimate token count (rough approximation: 1 token ≈ 1 word)"""
    return len(text.split())

def count_tools(text: str, context: Dict[str, Any]) -> int:
    """Count tool-related keywords in prompt"""
    tool_keywords = [
        "docker", "kubectl", "git", "curl", "wget", "ssh", "grep", "awk", "sed",
        "file", "script", "command", "execute", "run",
        "read", "write", "create", "delete",
        "api", "http", "https", "url", "endpoint",
        "database", "sql", "query", "backup", "restore",
        "container", "image", "volume", "network",
        "email", "send", "notify", "alert"
    ]
    
    text_lower = text.lower()
    count = sum(1 for kw in tool_keywords if kw in text_lower)
    
    # Check tools_available in context
    if "tools_available" in context:
        count += len(context["tools_available"])
    
    return count

def detect_task_type(text: str) -> str:
    """Detect the type of task from the prompt"""
    text_lower = text.lower()
    
    if any(kw in text_lower for kw in ["summary", "summarize", "résumé", "résume"]):
        return "summary"
    elif any(kw in text_lower for kw in ["code", "script", "python", "bash", "function"]):
        return "code"
    elif any(kw in text_lower for kw in ["analyze", "analysis", "audit", "review", "debug"]):
        return "analysis"
    elif any(kw in text_lower for kw in ["deploy", "install", "configure", "setup"]):
        return "deployment"
    else:
        return "general"

def route_model(prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route prompt to optimal model based on complexity analysis.
    Returns: {model, reasoning, confidence, complexity, estimated_cost, estimated_savings}
    """
    tokens = estimate_tokens(prompt)
    tools = count_tools(prompt, context)
    task_type = detect_task_type(prompt)
    
    # Routing logic (ported from bash prototype)
    model = "ollama/phi3:mini"
    reasoning = "Default case → generalist model"
    complexity = "medium"
    confidence = 0.5
    estimated_cost = 0.001
    estimated_savings = 0.004
    
    if tokens < 200 and tools <= 1 and task_type == "summary":
        model = "ollama/llama3.2:3b"
        reasoning = "Short prompt, simple summary, few tools → fast local model"
        complexity = "low"
        confidence = 0.9
        estimated_cost = 0.0005
        estimated_savings = 0.0045
        
    elif tokens < 500 and tools <= 2:
        model = "ollama/phi3:mini"
        reasoning = "Medium prompt, some tools → balanced model"
        complexity = "medium"
        confidence = 0.8
        estimated_cost = 0.001
        estimated_savings = 0.004
        
    elif tokens >= 500 or tools >= 3 or task_type in ["code", "analysis"]:
        model = "anthropic/claude-sonnet-4"
        reasoning = "Long prompt, multiple tools, or complex task (code/analysis) → premium model"
        complexity = "high"
        confidence = 0.95
        estimated_cost = 0.005
        estimated_savings = 0.0
    
    return {
        "model": model,
        "reasoning": reasoning,
        "confidence": confidence,
        "complexity": complexity,
        "estimated_cost": estimated_cost,
        "estimated_savings": estimated_savings
    }

def check_api_key(authorization: str = Header(...)) -> bool:
    """Validate API key"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    key = authorization.split(" ")[1]
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return True

def track_request(user_id: str, model: str, cost_saved: float):
    """Track request in Redis for quotas and analytics"""
    rd = get_redis()
    if not rd:
        return  # Skip tracking if Redis unavailable
    
    today = str(date.today())
    month = today[:7]  # "2026-03"
    
    # Increment counters
    rd.incr(f"user:{user_id}:requests:{today}")
    rd.incr(f"user:{user_id}:requests:{month}")
    rd.incr(f"user:{user_id}:model:{model}")
    rd.incrbyfloat(f"user:{user_id}:saved", cost_saved)
    
    # Set expiration for daily counter
    rd.expire(f"user:{user_id}:requests:{today}", 86400 * 2)

async def generate_from_ollama(prompt: str, model: str, max_tokens: int = 1024) -> Dict[str, Any]:
    """
    Generate text using Ollama model.
    Returns: {generation, tokens_used, cost}
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model.replace("ollama/", ""),
                    "prompt": prompt,
                    "stream": False,
                    "num_predict": max_tokens
                }
            )

            if response.status_code != 200:
                raise Exception(f"Ollama error: {response.status_code}")

            data = response.json()
            generation = data.get("response", "")
            tokens_used = data.get("eval_count", estimate_tokens(generation))

            # Local models are essentially free
            cost = 0.0

            return {
                "generation": generation,
                "tokens_used": tokens_used,
                "cost": cost
            }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {str(e)}")

async def generate_from_openrouter(prompt: str, model: str, max_tokens: int = 1024) -> Dict[str, Any]:
    """
    Generate text using OpenRouter API.
    Returns: {generation, tokens_used, cost}
    """
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="OpenRouter not configured")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_BASE_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://model-router-api.dev",
                    "X-Title": "Model Router API"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens
                }
            )

            if response.status_code != 200:
                error_detail = response.json().get("error", {}).get("message", "Unknown error")
                raise Exception(f"OpenRouter error: {error_detail}")

            data = response.json()
            generation = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", estimate_tokens(generation))

            # Extract cost from response
            cost = data.get("usage", {}).get("total_cost", 0.005)

            return {
                "generation": generation,
                "tokens_used": tokens_used,
                "cost": cost
            }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"OpenRouter unavailable: {str(e)}")

def get_user_stats(user_id: str) -> Dict[str, Any]:
    """Get user statistics from Redis"""
    rd = get_redis()
    if not rd:
        return {
            "requests_today": 0,
            "requests_month": 0,
            "quota_remaining": FREE_TIER_DAILY,
            "total_saved": 0.0,
            "models_used": {}
        }
    
    today = str(date.today())
    month = today[:7]
    
    requests_today = int(rd.get(f"user:{user_id}:requests:{today}") or 0)
    requests_month = int(rd.get(f"user:{user_id}:requests:{month}") or 0)
    total_saved = float(rd.get(f"user:{user_id}:saved") or 0.0)
    
    # Get model counts
    models_used = {}
    for key in rd.scan_iter(f"user:{user_id}:model:*"):
        model = key.split(":")[-1]
        count = rd.get(key)
        if count:
            models_used[model] = int(count)
    
    quota_remaining = max(0, FREE_TIER_DAILY - requests_today)
    
    return {
        "requests_today": requests_today,
        "requests_month": requests_month,
        "quota_remaining": quota_remaining,
        "total_saved": total_saved,
        "models_used": models_used
    }

# API Endpoints
@app.post("/v1/route", response_model=RoutingResponse)
async def route(request: RoutingRequest, authorization: str = Header(...)):
    """
    Route a prompt to the optimal model.
    
    Analyzes the prompt's complexity and selects the best model:
    - Simple tasks → Local small models (fast, cheap)
    - Complex tasks → Cloud powerful models (accurate)
    """
    # Validate API key
    check_api_key(authorization)
    
    # Check quota
    user_id = hashlib.md5(authorization.encode()).hexdigest()[:8]
    stats = get_user_stats(user_id)
    if stats["quota_remaining"] <= 0:
        raise HTTPException(status_code=429, detail="Daily quota exceeded")
    
    # Route the request
    routing = route_model(request.prompt, request.context or {})
    
    # Track usage
    track_request(user_id, routing["model"], routing["estimated_savings"])
    
    return RoutingResponse(**routing)

@app.get("/v1/stats", response_model=StatsResponse)
async def stats(authorization: str = Header(...)):
    """Get usage statistics for the authenticated user."""
    check_api_key(authorization)
    user_id = hashlib.md5(authorization.encode()).hexdigest()[:8]
    
    return StatsResponse(**get_user_stats(user_id))

@app.post("/v1/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest, authorization: str = Header(...)):
    """
    Generate text using intelligent model routing.

    Routes to appropriate model:
    - complexity=low/medium → Ollama (fast, cheap)
    - complexity=high → OpenRouter (powerful)

    Tracks usage and enforces quotas.
    """
    # Validate API key
    check_api_key(authorization)

    # Check quota
    user_id = hashlib.md5(authorization.encode()).hexdigest()[:8]
    stats = get_user_stats(user_id)
    if stats["quota_remaining"] <= 0:
        raise HTTPException(status_code=429, detail="Daily quota exceeded")

    # Validate complexity
    if request.complexity not in ["low", "medium", "high"]:
        raise HTTPException(status_code=400, detail="Invalid complexity: must be low, medium, or high")

    # Route to appropriate model and provider
    if request.complexity in ["low", "medium"]:
        # Use Ollama for simple/medium tasks
        model = "ollama/phi3:mini" if request.complexity == "medium" else "ollama/llama3.2:3b"
        reasoning = f"Complexity {request.complexity} → local Ollama model (fast, cheap)"
        result = await generate_from_ollama(request.prompt, model, request.max_tokens)
        cost_saved = 0.005 - result["cost"]
    else:
        # Use OpenRouter for complex tasks
        model = "anthropic/claude-sonnet-4"
        reasoning = f"Complexity high → premium OpenRouter model (accurate, powerful)"
        result = await generate_from_openrouter(request.prompt, model, request.max_tokens)
        cost_saved = 0.0

    # Track usage
    track_request(user_id, model, cost_saved)

    return GenerateResponse(
        model=model,
        generation=result["generation"],
        reasoning=reasoning,
        confidence=0.85,
        tokens_used=result["tokens_used"],
        cost=result["cost"],
        cost_saved=cost_saved,
        complexity=request.complexity
    )

@app.get("/v1/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    # Check Ollama connection
    ollama_status = "disconnected"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
            if response.status_code == 200:
                ollama_status = "connected"
    except Exception:
        pass

    # Check OpenRouter configuration
    openrouter_status = "configured" if OPENROUTER_API_KEY else "not_configured"

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        models={
            "ollama": ollama_status,
            "openrouter": openrouter_status
        }
    )

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Model Router API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/v1/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
