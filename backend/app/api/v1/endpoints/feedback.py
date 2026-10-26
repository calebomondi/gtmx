"""The app's feedback button: suggestions and problems, sent to the team."""

from fastapi import APIRouter, status

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.schemas.feedback import FeedbackCreate, FeedbackResponse
from backend.app.services import feedback as feedback_service

router = APIRouter()


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def send_feedback(payload: FeedbackCreate, user: CurrentUser, db: DbSession):
    """Keep what the user wrote, with the page and Lace they were on."""
    row = await feedback_service.submit(db, user.id, user.email, payload.text, payload.path, payload.lace_id)
    return FeedbackResponse.model_validate(row)
