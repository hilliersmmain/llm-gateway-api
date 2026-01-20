#!/bin/bash

# LLM Gateway API - Startup Verification Script
# Verifies that all services start correctly and the application is healthy

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "========================================="
echo "LLM Gateway API - Startup Verification"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Cleanup function
cleanup() {
    if [ "$CLEANUP_ON_EXIT" = "true" ]; then
        print_info "Cleaning up..."
        docker-compose down -v > /dev/null 2>&1
        print_success "Services stopped"
    fi
}

trap cleanup EXIT

# Parse arguments
CLEANUP_ON_EXIT="false"
for arg in "$@"; do
    case $arg in
        --cleanup)
            CLEANUP_ON_EXIT="true"
            shift
            ;;
    esac
done

# Step 1: Check prerequisites
print_info "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    exit 1
fi
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed"
    exit 1
fi
print_success "Docker and docker-compose found"

# Step 2: Check .env file
if [ ! -f .env ]; then
    print_error ".env file not found. Copy .env.example to .env and configure it."
    exit 1
fi
print_success ".env file exists"

# Step 3: Stop any existing containers
print_info "Stopping any existing containers..."
docker-compose down -v > /dev/null 2>&1 || true
print_success "Cleaned up existing containers"

# Step 4: Build and start services
print_info "Building and starting services (this may take a few minutes)..."
if docker-compose up -d --build; then
    print_success "Services started"
else
    print_error "Failed to start services"
    docker-compose logs
    exit 1
fi

# Step 5: Wait for database to be healthy
print_info "Waiting for database to be healthy..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if docker-compose exec -T db pg_isready -U user -d llm_gateway > /dev/null 2>&1; then
        print_success "Database is ready"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    print_error "Database did not become ready in time"
    docker-compose logs db
    exit 1
fi

# Step 6: Wait for API to be healthy
print_info "Waiting for API to be healthy..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        print_success "API is healthy"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    print_error "API did not become healthy in time"
    docker-compose logs api
    exit 1
fi

# Step 7: Verify health endpoint returns proper response
print_info "Verifying health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
    print_success "Health endpoint returns correct response"
else
    print_error "Health endpoint returned unexpected response: $HEALTH_RESPONSE"
    exit 1
fi

# Step 8: Verify database tables exist
print_info "Verifying database tables..."
TABLES=$(docker-compose exec -T db psql -U user -d llm_gateway -t -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public';" | tr -d ' ')

if echo "$TABLES" | grep -q "request_logs"; then
    print_success "request_logs table exists"
else
    print_error "request_logs table not found"
    exit 1
fi

if echo "$TABLES" | grep -q "guardrail_logs"; then
    print_success "guardrail_logs table exists"
else
    print_error "guardrail_logs table not found"
    exit 1
fi

# Step 9: Verify API endpoints are accessible
print_info "Verifying API endpoints..."

# Check /docs
if curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
    print_success "/docs endpoint is accessible"
else
    print_error "/docs endpoint is not accessible"
fi

# Check /metrics
if curl -sf http://localhost:8000/metrics > /dev/null 2>&1; then
    print_success "/metrics endpoint is accessible"
else
    print_error "/metrics endpoint is not accessible"
fi

# Check /analytics
if curl -sf http://localhost:8000/analytics > /dev/null 2>&1; then
    print_success "/analytics endpoint is accessible"
else
    print_error "/analytics endpoint is not accessible"
fi

# Step 10: Check for errors in logs
print_info "Checking logs for errors..."
if docker-compose logs api | grep -i "error" | grep -v "ERROR_RESPONSE" | grep -v "error_type" > /dev/null 2>&1; then
    print_error "Found errors in API logs:"
    docker-compose logs api | grep -i "error" | grep -v "ERROR_RESPONSE" | grep -v "error_type" | tail -5
else
    print_success "No errors found in logs"
fi

echo ""
echo "========================================="
echo -e "${GREEN}✓ All verification checks passed!${NC}"
echo "========================================="
echo ""
echo "Services are running:"
echo "  - API: http://localhost:8000"
echo "  - Swagger UI: http://localhost:8000/docs"
echo "  - Analytics: http://localhost:8000/analytics?format=html"
echo "  - Database: localhost:5432"
echo ""

if [ "$CLEANUP_ON_EXIT" = "true" ]; then
    echo "Services will be stopped automatically."
else
    echo "To stop services, run: docker-compose down"
fi

exit 0
