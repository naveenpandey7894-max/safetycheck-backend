from datetime import datetime
from pydantic import BaseModel


class ReportOut(BaseModel):
    id: int
    category: str
    severity: str
    status: str

    photoUrl: str | None = None

    aiConfidence: float | None = None
    aiDescription: str | None = None

    latitude: float | None = None
    longitude: float | None = None
    location: str | None = None

    siteId: int
    reporterId: int | None = None
    assignedToId: int | None = None
    notes: str | None = None

    createdAt: datetime
    updatedAt: datetime | None = None
    resolvedAt: datetime | None = None

    class Config:
        from_attributes = True


class ReportStatusUpdate(BaseModel):
    status: str


class ReportAssign(BaseModel):
    assigned_to_id: int


class DashboardStats(BaseModel):
    total_reports: int
    by_status: dict
    by_category: dict
    by_severity: dict
    avg_resolution_hours: float | None = None
    open_critical: int