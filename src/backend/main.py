from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.api.webhooks import router as webhooks_router


def create_app() -> FastAPI:
    app = FastAPI(title="CRM AI Plus API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(webhooks_router)
    return app


app = create_app()

