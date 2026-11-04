"""Translate HTTP requests and business results."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.session import SessionCreate, SessionResponse
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(data: SessionCreate):
    return session_service.create_session(data)


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID):
    try:
        return session_service.get_session(session_id)
    except session_service.SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from exc
