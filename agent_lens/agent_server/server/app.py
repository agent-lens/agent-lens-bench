from __future__ import annotations

from fastapi import FastAPI

from .routers import claude, mock


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Benchmark Server")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(mock.router, prefix="/mock", tags=["mock"])
    app.include_router(claude.router, prefix="/claude", tags=["claude"])
    return app


app = create_app()
