"""HTTP endpoints for the independent Artisia mock application."""

import os

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import JSONResponse

from artisia_app.schemas.artisia import BookingCreate, BookingResponse, SessionListResponse, SessionPatch, SessionResponse
from artisia_app.services import artisia_service


def check_api_key(authorization: str | None = Header(default=None)):
    expected = "Bearer " + os.environ.get("ARTISIA_API_KEY", "artisia-demo-key")
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid Artisia API key")


router = APIRouter(prefix="/v1", tags=["artisia"], dependencies=[Depends(check_api_key)])


# These handlers only call synchronous memory operations, with no await between
# checking capacity and updating it. Run one API process for this mock.
@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    return artisia_service.list_sessions()


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(session_id: str, data: SessionPatch):
    changes = data.model_dump(exclude_unset=True)
    if not changes or None in changes.values():
        raise HTTPException(status_code=422, detail="Provide capacity or status; null is not supported")
    try:
        return artisia_service.update_session(session_id, data)
    except artisia_service.ArtisiaNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except artisia_service.ArtisiaConflictError as exc:
        return JSONResponse(exc.detail, status_code=409)


@router.post("/sessions/{session_id}/bookings", response_model=BookingResponse, status_code=201)
async def create_booking(session_id: str, data: BookingCreate):
    try:
        return artisia_service.create_booking(session_id, data)
    except artisia_service.ArtisiaNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except artisia_service.ArtisiaConflictError as exc:
        return JSONResponse(exc.detail, status_code=409)


@router.delete("/bookings/{booking_id}", status_code=204)
async def cancel_booking(booking_id: str):
    try:
        artisia_service.cancel_booking(booking_id)
    except artisia_service.ArtisiaNotFoundError:
        return Response(status_code=404)
    return Response(status_code=204)
