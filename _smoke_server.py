"""Smoke-test launcher: runs the FastAPI app with init_db and Gemini stubbed.

Used for manual browser smoke testing when no real PG / Gemini key is available.
Not part of the normal app surface; safe to delete or .gitignore.
"""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import uvicorn

from app import main as app_main


async def _noop_init_db() -> None:
    return None


async def _noop_cleanup_old_logs(retention_days: int) -> None:
    return None


app_main.init_db = _noop_init_db
app_main.cleanup_old_logs = _noop_cleanup_old_logs


class _StubGemini:
    async def generate_response(self, message: str) -> tuple[str, dict]:
        return (
            f"**Mock reply** to: _{message}_\n\nThis is a smoke-test stub.",
            {"input_tokens": 12, "output_tokens": 24},
        )

    async def generate_response_stream(
        self, message: str
    ) -> AsyncGenerator[tuple[str, dict | None], None]:
        for chunk in ["**Streaming** ", "mock ", "reply ", "to: ", f"_{message}_."]:
            yield chunk, None
            await asyncio.sleep(0.15)
        yield "", {"input_tokens": 12, "output_tokens": 24}


from app.services import gemini as gemini_module  # noqa: E402

gemini_module._gemini_service = _StubGemini()  # type: ignore[assignment]


from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402


def _stub_session():
    async def _gen():
        sess = AsyncMock(spec=AsyncSession)
        sess.add = lambda *a, **kw: None
        sess.commit = AsyncMock()
        sess.execute = AsyncMock()
        yield sess

    return _gen


from app.core.database import get_session  # noqa: E402

app_main.app.dependency_overrides[get_session] = _stub_session()


if __name__ == "__main__":
    uvicorn.run(app_main.app, host="127.0.0.1", port=8765, log_level="info")
