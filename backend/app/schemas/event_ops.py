import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class EventAssignIn(BaseModel):
    user_id: uuid.UUID | None = None

class EventNoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

class EventReviewIn(BaseModel):
    outcome: str
    notes: str | None = Field(default=None, max_length=4000)

class EventResolveIn(BaseModel):
    note: str = Field(min_length=2, max_length=4000)

class EvidenceOut(BaseModel):
    id: uuid.UUID
    kind: str
    mime_type: str
    sha256: str
    size_bytes: int
    captured_at: datetime
    source_frame_at: str | None = None
    immutable: bool
    metadata_json: dict

class TimelineItem(BaseModel):
    id: uuid.UUID
    type: str
    action: str | None = None
    body: str | None = None
    actor_user_id: uuid.UUID | None = None
    actor_name: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    details: dict = {}
    created_at: datetime

class AssigneeOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
