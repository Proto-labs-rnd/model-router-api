# Model Router API 🎯

**Intelligent model routing for LLM applications — save up to 80% on costs while maintaining quality.**

## What It Does

When you have multiple LLM models available (GPT-5, Claude, GLM, local models), not every request needs the most expensive one. This API analyzes each request and routes it to the best model based on:

- **Task complexity** — Simple questions → cheap model, complex reasoning → powerful model
- **Cost optimization** — Don't waste $0.03/1K tokens on "what time is it?"
- **Latency requirements** — Time-sensitive requests → fastest available model
- **Fallback chains** — If a model is down, automatically try the next one

## Quick Start

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/Proto-labs-rnd/model-router-api.git
cd model-router-api

# Configure your API keys
cp .env.example .env
# Edit .env with your API keys

# Start
docker compose up -d
# → API running on http://localhost:8000
```

### Option 2: Direct

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python main.py
```

## API Usage

```bash
# Route a chat completion request
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Explain quantum computing"}],
    "routing_strategy": "cost_optimized"
  }'

# Check which model was selected
curl http://localhost:8000/v1/routing/stats
```

### Supported Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /v1/chat/completions` | OpenAI-compatible chat completion (auto-routed) |
| `POST /v1/routing/decide` | Preview which model would be selected without executing |
| `GET /v1/routing/stats` | Routing statistics (model usage, costs, latency) |
| `GET /v1/models` | List available models and their capabilities |
| `GET /health` | Health check |

### Routing Strategies

| Strategy | Description |
|----------|-------------|
| `cost_optimized` | Cheapest model that can handle the task (default) |
| `quality_first` | Always use the best available model |
| `latency_optimized` | Fastest response, regardless of cost |
| `balanced` | Balance cost, quality, and latency |

## Configuration

Edit `.env` to configure your models:

```env
# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
ZAI_API_KEY=...

# Model definitions
MODELS=gpt-5.4,claude-sonnet-4-6,glm-5-turbo

# Default strategy
ROUTING_STRATEGY=cost_optimized

# Server
PORT=8000
```

## Testing

```bash
# Run automated tests
python test_api.py

# Or use the bash test script
./test-api.sh
```

## Architecture

```
Client Request
      │
      ▼
┌─────────────────┐
│  Router API      │
│  ┌─────────────┐│
│  │ Analyzer    ││ ──→ Classify complexity, intent, domain
│  │ Selector    ││ ──→ Pick best model for the task
│  │ Executor    ││ ──→ Forward to chosen LLM provider
│  │ Tracker     ││ ──→ Log cost, latency, quality
│  └─────────────┘│
└─────────────────┘
      │
      ▼
  GPT-5.4 / Claude / GLM / Local
```

## Requirements

- Python 3.10+
- At least one LLM API key (OpenAI, Anthropic, or ZAI)
- Docker (optional, recommended)

## License

MIT
