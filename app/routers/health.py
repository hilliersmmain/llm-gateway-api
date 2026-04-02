"""Health check router."""

from fastapi import APIRouter

from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
)
async def health_check():
    """Check API health status."""
    return HealthResponse(status="healthy", version="1.0.0")
