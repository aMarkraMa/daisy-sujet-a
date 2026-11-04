"""Run the independent Artisia mock: uvicorn artisia_app.main:app --port 8001."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from artisia_app.routers.artisia import router

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Artisia mock")
app.include_router(router)
