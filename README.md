# LLM Gateway API

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](./LICENSE)

**LLM Gateway API** is an enterprise-grade LLM gateway that proxies requests to Google's Gemini 2.5 Flash model with built-in input validation, structured output enforcement, and comprehensive request logging. Designed for production scenarios where security, observability, and reliability are paramount.

---

### Why I Built This

As organizations increasingly integrate LLMs into their workflows, the gap between "making an API call" and "deploying a production-ready AI service" becomes starkly apparent. I built **LLM Gateway API** to bridge that gap—demonstrating that responsible AI deployment requires more than just connecting to an API endpoint. It requires input validation to prevent prompt injection, observability to understand usage patterns, and enterprise-grade infrastructure to ensure reliability. This project showcases how to build an LLM gateway that's ready for real-world deployment.

---

## API Reference

| Endpoint       | Method | Description                                        |
| -------------- | ------ | -------------------------------------------------- |
| `/chat`        | POST   | Send a message through guardrails to Gemini        |
| `/chat/stream` | POST   | Stream response via Server-Sent Events (SSE)       |
| `/metrics`     | GET    | Get usage statistics and estimated cost            |
| `/analytics`   | GET    | Get detailed analytics with trends and charts      |
| `/health`      | GET    | Health check endpoint                              |
| `/docs`        | GET    | Interactive Swagger UI documentation               |
| `/redoc`       | GET    | ReDoc API documentation                            |

### Analytics Endpoint

The `/analytics` endpoint provides detailed historical metrics and trends:

```bash
curl http://localhost:8000/analytics
```

```json
{
  "total_requests_24h": 150,
  "total_requests_7d": 890,
  "latency_trend": [
    {"hour": "2026-01-20T10:00:00", "avg_latency_ms": 245.5, "request_count": 12},
    {"hour": "2026-01-20T11:00:00", "avg_latency_ms": 198.3, "request_count": 18}
  ],
  "total_tokens_in_24h": 12500,
  "total_tokens_out_24h": 45000,
  "total_tokens_in_7d": 85000,
  "total_tokens_out_7d": 312000,
  "top_blocked_keywords": [
    {"keyword": "secret_key", "count": 23},
    {"keyword": "internal_only", "count": 8}
  ],
  "total_blocked_requests_24h": 15
}
```

**Analytics Dashboard (HTML)**

For an interactive chart visualization, add `?format=html`:

```bash
open http://localhost:8000/analytics?format=html
```

The HTML dashboard includes:
- **Latency Trend:** Line chart showing hourly average response times
- **Token Usage:** Bar chart comparing input vs output tokens
- **Blocked Keywords:** Horizontal bar chart of most commonly blocked terms
- **Request Volume:** Bar chart of hourly request counts

---

## Quick Start

**Prerequisites:** Python 3.12+, Docker

```bash
# Clone and setup
git clone https://github.com/hilliersmmain/llm-gateway-api.git
cd llm-gateway-api

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Start the complete stack
docker-compose up -d --build

# Verify it's running
curl http://localhost:8000/health

# Or run the automated verification script
./scripts/verify_startup.sh
```

---

## Verification

To verify all components are working correctly:

```bash
# Run the comprehensive verification script
./scripts/verify_startup.sh

# The script will:
# - Check prerequisites
# - Build and start services
# - Verify database health
# - Test API endpoints
# - Confirm table creation
# - Check for errors

# To cleanup after verification:
./scripts/verify_startup.sh --cleanup
```

See [VERIFICATION.md](./VERIFICATION.md) for detailed verification results and troubleshooting.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *required* | Your Google Gemini API key |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection URL |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `RATE_LIMIT_REQUESTS` | `10` | Maximum requests per IP in time window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Time window for rate limiting in seconds |
| `REDIS_URL` | *(optional)* | Redis URL for distributed rate limiting |

### Rate Limiting

The API includes built-in rate limiting to prevent abuse:
- **Default:** 10 requests per 60 seconds per IP address
- **Backend:** In-memory (single instance) or Redis (distributed)
- **Excluded paths:** `/health`, `/metrics`, `/docs`, `/redoc`

To enable Redis-based distributed rate limiting:
```bash
# In .env
REDIS_URL=redis://localhost:6379/0
```

---

## License

MIT License
