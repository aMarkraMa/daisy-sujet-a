"""HTTP endpoint for Daisy reservations."""

from fastapi import APIRouter, HTTPException, Response, status

from app.schemas.reservation import ReservationCreate, ReservationResponse
from app.services import reservation_service

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": ReservationResponse, "description": "Existing reservation for this source_ref"},
        404: {"description": "Session not found"},
        409: {"description": "Source reference conflict, sales closed or insufficient capacity"},
    },
)
def create_reservation(data: ReservationCreate, response: Response):
    try:
        reservation, created = reservation_service.create_reservation(data)
    except reservation_service.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except reservation_service.IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="source_ref already used with a different session or quantity",
        ) from exc
    except reservation_service.ReservationUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail="Session is not open for booking or has insufficient capacity",
        ) from exc

    if not created:
        response.status_code = status.HTTP_200_OK
    return reservation
