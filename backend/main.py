"""FastAPI application entry point."""

from fastapi import FastAPI

from app.routers.sessions import router as sessions_router
from app.routers.reservations import router as reservations_router
from app.routers.webhooks import router as webhooks_router

app = FastAPI(title="Daisy — Sujet A")
app.include_router(sessions_router)
app.include_router(reservations_router)
app.include_router(webhooks_router)
