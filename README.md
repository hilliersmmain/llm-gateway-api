# LLM Gateway API

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](./LICENSE)

An enterprise-grade LLM gateway that proxies requests to Google's Gemini 2.5 Flash model with built-in input validation, structured output enforcement, and comprehensive request logging. Built for production scenarios where security, observability, and reliability actually matter.

---

## Why I Built This

As organizations increasingly integrate LLMs into their workflows, the gap between "making an API call" and "deploying a production-ready AI service" becomes starkly apparent. I built **LLM Gateway API** to bridge that gap—demonstrating that responsible AI deployment requires more than just connecting to an API endpoint. It requires input validation to prevent prompt injection, observability to understand usage patterns, and enterprise-grade infrastructure to ensure reliability. This project showcases how to build an LLM gateway that's ready for real-world deployment.

---

## Screenshots

Here's what the application looks like in action:

### Chat Interface

![Chat Interface](screenshots/llm-gateway-api-screenshot-showing-chat-intro-contents.png)

The main chat interface features a clean, dark-mode UI with session management and easy access to API docs and analytics.

![Working Chat](screenshots/llm-gateway-api-screenshot-showing-working-chat.png)

Real-time chat responses from Gemini 2.5 Flash with markdown support and message history.

### Analytics Dashboard

![Analytics Dashboard](screenshots/llm-gateway-api-analytics-dashboard.png)

Interactive analytics dashboard showing latency trends, token usage, request volume, success rates, and security metrics.

### API Documentation

![API Documentation](screenshots/llm-gateway-api-screenshot-showing-stoplight-documentation-page.png)

Comprehensive API documentation with interactive testing capabilities powered by Stoplight Elements.

---

## Quick Start

### Prerequisites

Before you begin, make sure you have:

- **Docker** installed and running ([Get Docker](https://docs.docker.com/get-docker/))
- **Git** installed ([Get Git](https://git-scm.com/downloads))
- A **Google account** to get a free Gemini API key

Verify Docker is running:

```bash
docker --version
```

### Step 1: Get Your Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Accept the terms of service if prompted
4. Click **"Create API Key"** or **"Get API Key"**
5. Choose **"Create API key in new project"** (recommended for beginners)
6. Copy your API key (it starts with `AIza...`)

> **Note:** The free tier includes generous limits suitable for development and testing (1,500 requests/day). Keep your API key secure and never commit it to version control.

### Step 2: Clone the Repository

```bash
git clone https://github.com/hilliersmmain/llm-gateway-api.git
cd llm-gateway-api
```

### Step 3: Configure Environment Variables

Create your environment file from the example:

```bash
cp .env.example .env
```

Edit the `.env` file and add your Gemini API key:

```bash
nano .env
# or use your preferred editor: code .env, vim .env, etc.
```

Replace `YOUR_GEMINI_API_KEY` with the actual key you copied in Step 1:

```env
GEMINI_API_KEY=AIzaYourActualKeyHere
```

Save and close the file.

### Step 4: Start the Application

Launch the complete stack with Docker Compose:

```bash
docker-compose up -d --build
```

This will:

- Download the required Docker images (first time only)
- Build the application container
- Start PostgreSQL database and the API server
- Run in the background (`-d` flag)

**First-time startup** may take 2-3 minutes to download images and build.

### Step 5: Verify Installation

Check that the API is running:

```bash
curl http://localhost:8000/health
```

You should see: `{"status":"healthy","version":"1.0.0"}`

### Step 6: Access the Application

Open your browser and navigate to:

- **Chat Interface:** [http://localhost:8000](http://localhost:8000)
- **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Analytics Dashboard:** [http://localhost:8000/analytics?format=html](http://localhost:8000/analytics?format=html)

Try sending a message in the chat interface to confirm everything works!

### Stopping the Application

When you're done, stop the containers:

```bash
docker-compose down
```

To view logs if something goes wrong:

```bash
docker-compose logs -f
```

### Troubleshooting

**Port 8000 already in use:**

```bash
# Find what's using port 8000
lsof -i :8000
# Stop it or change the port in docker-compose.yml
```

**Docker permission errors (Linux):**

```bash
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

**Invalid API key errors:**

- Double-check that you copied the full key from Google AI Studio
- Make sure there are no extra spaces in your `.env` file
- Verify the line reads: `GEMINI_API_KEY=AIzaYourKeyHere` (no quotes needed)

---

## Next Steps

Once you have the application running, here are some things to try:

**Explore the Features:**

- Send various types of messages in the chat to see how the AI responds
- Try creating multiple chat sessions using the sidebar
- Check the analytics dashboard to see your usage metrics
- Review the API documentation to understand available endpoints

**Test the Security Features:**

- Try sending messages with blocked keywords (check `app/services/guardrails.py` for the list)
- Monitor how the system logs blocked requests in the analytics

**Customize Your Setup:**

- Adjust rate limiting in `.env` (`RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`)
- Modify the guardrails rules in `app/services/guardrails.py`
- Add your own blocked keywords for content filtering

**Use the API Programmatically:**

```bash
# Test the chat endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?"}'

# Get usage metrics
curl http://localhost:8000/metrics

# Stream a response
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a story"}'
```

**Prepare for Production:**

- Review the "Deployment Considerations" section below
- Change the default database password in `.env`
- Consider setting up Redis for distributed rate limiting
- Review and customize security settings for your use case

---

## Key Features

**Security & Validation:**

- Input validation and guardrails to prevent prompt injection attacks
- Keyword-based content filtering with configurable blocklists
- Rate limiting (configurable per-user or global)
- IP tracking for security monitoring

**Observability:**

- Comprehensive request logging with PostgreSQL persistence
- Real-time metrics and analytics endpoints
- Interactive analytics dashboard with Chart.js visualizations
- Token usage tracking and cost estimation
- Success rate monitoring and error tracking

**Chat Interface:**

- Modern, responsive web UI with dark mode
- Multi-session chat history with localStorage persistence
- Markdown rendering for bot responses
- Real-time streaming responses via Server-Sent Events (SSE)

**Developer Experience:**

- Interactive API documentation with Stoplight Elements
- OpenAPI 3.0 spec generation
- Docker Compose for one-command deployment
- Comprehensive test suite with pytest

---

## API Endpoints

**Chat Endpoints:**

- `POST /chat` - Send a message through guardrails to Gemini
- `POST /chat/stream` - Stream response via Server-Sent Events (SSE)

**Monitoring & Metrics:**

- `GET /metrics` - Get usage statistics and estimated cost
- `GET /analytics` - Get detailed analytics with trends and charts
- `GET /analytics?format=html` - Interactive analytics dashboard
- `GET /health` - Health check endpoint

**Documentation:**

- `GET /docs` - Interactive Stoplight API documentation
- `GET /redoc` - ReDoc API documentation

---

## Analytics Dashboard

The `/analytics` endpoint provides detailed historical metrics and trends. Access the JSON response directly, or use `?format=html` for an interactive dashboard with:

- **Latency Trend:** Line chart showing hourly average response times
- **Token Usage:** Bar chart comparing input vs output tokens over 24h and 7d
- **Blocked Keywords:** Horizontal bar chart of most commonly blocked terms
- **Request Volume:** Bar chart of hourly request counts
- **Success Rate:** Pie chart showing successful vs failed requests
- **Security Overview:** Bar chart of blocked requests over time

Example analytics JSON response:

```json
{
  "total_requests_24h": 150,
  "total_requests_7d": 890,
  "latency_trend": [
    {
      "hour": "2026-01-20T10:00:00",
      "avg_latency_ms": 245.5,
      "request_count": 12
    },
    {
      "hour": "2026-01-20T11:00:00",
      "avg_latency_ms": 198.3,
      "request_count": 18
    }
  ],
  "total_tokens_in_24h": 12500,
  "total_tokens_out_24h": 45000,
  "top_blocked_keywords": [
    { "keyword": "secret_key", "count": 23 },
    { "keyword": "internal_only", "count": 8 }
  ],
  "total_blocked_requests_24h": 15,
  "success_count_24h": 135,
  "error_count_24h": 0
}
```

---

## Project Structure

The codebase is organized for clarity and maintainability:

```
llm-gateway-api/
├── app/
│   ├── core/              # Configuration and database setup
│   ├── middleware/        # Rate limiting and request logging
│   ├── models/            # SQLAlchemy models and Pydantic schemas
│   ├── services/          # Business logic (Gemini, Guardrails)
│   └── main.py            # FastAPI application entry point
├── static/                # Frontend files (HTML, CSS, JS)
├── screenshots/           # Application screenshots
├── tests/                 # Pytest test suite
├── docker-compose.yml     # Docker orchestration
├── Dockerfile             # Container configuration
└── requirements.txt       # Python dependencies
```

---

## Running Tests

The project includes a comprehensive test suite:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app
```

Tests cover:

- Guardrail validation logic
- Chat endpoint functionality
- Streaming responses
- Analytics calculations
- Database operations
- Error handling

---

## Configuration

Environment variables are configured via `.env` file:

- `GEMINI_API_KEY` - Your Google Gemini API key (required)
- `DATABASE_URL` - PostgreSQL connection string (auto-configured in Docker)
- `POSTGRES_PASSWORD` - Database password (change for production!)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `RATE_LIMIT_REQUESTS` - Max requests per window (default: 10)
- `RATE_LIMIT_WINDOW_SECONDS` - Rate limit window in seconds (default: 60)
- `REDIS_URL` - Redis URL for distributed rate limiting (optional)

---

## Deployment Considerations

This project is designed to be production-ready with minimal configuration:

1. **Change the default database password** in `.env` before deploying
2. **Configure rate limiting** based on your expected traffic
3. **Set up Redis** if you need distributed rate limiting across multiple instances
4. **Review guardrails configuration** in `app/services/guardrails.py` to match your security requirements
5. **Monitor the `/analytics` endpoint** for usage patterns and potential security issues

The application is containerized and can be deployed to any Docker-compatible platform (AWS ECS, Google Cloud Run, Azure Container Instances, etc.).

---

## Technology Stack

- **FastAPI** - Modern, high-performance Python web framework
- **PostgreSQL 17** - Robust relational database for request logging
- **Docker Compose** - Multi-container orchestration
- **Google Gemini 2.5 Flash** - State-of-the-art LLM with fast inference
- **SQLAlchemy** - Async ORM for database operations
- **Pydantic** - Data validation and settings management
- **Chart.js** - Interactive analytics visualizations
- **Marked.js** - Markdown rendering in the chat UI
- **Stoplight Elements** - Beautiful API documentation

---

## Contributing

This is a personal portfolio project, but I'm open to feedback and suggestions! Feel free to open an issue or submit a pull request if you find bugs or have ideas for improvements.

---

## License

MIT License - see [LICENSE](./LICENSE) for details.

---

## Acknowledgments

Built as a demonstration of production-ready LLM integration patterns, inspired by real-world challenges in deploying AI systems at scale.
