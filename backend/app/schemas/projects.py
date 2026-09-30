import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.workspaces import WorkspaceResponse


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ProjectUpdate(BaseModel):
    """Partial update: only fields present in the payload are applied."""
    name: str | None = Field(default=None, min_length=1, max_length=100)


class ProjectOrder(BaseModel):
    """Drag-to-order payload for /projects. `priority` and `other` are the
    bucketed project ids in display order; the server flips each project's
    priority flag and rewrites its position in a single transaction."""
    priority: list[uuid.UUID] = []
    other: list[uuid.UUID] = []


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    name_key: str
    priority: bool = False
    position: int = 0
    archived: bool = False
    archived_at: datetime | None = None
    date_created: datetime
    last_activity: datetime
    workspace_count: int = 0
    archived_workspace_count: int = 0


class ProjectDetailResponse(ProjectResponse):
    workspaces: list[WorkspaceResponse] = []