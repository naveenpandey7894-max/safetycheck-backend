from collections import Counter

from fastapi import APIRouter, Depends

from app.core.db import prisma
from app.core.security import get_current_user
from app.schemas.report import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_stats(site_id: int | None = None, user=Depends(get_current_user)):
    """The metrics a company actually pays for: open critical issues,
    status/category/severity breakdown, average resolution speed."""
    where = {"siteId": site_id} if site_id else {}
    reports = await prisma.report.find_many(where=where)

    by_status = Counter(r.status for r in reports)
    by_category = Counter(r.category for r in reports)
    by_severity = Counter(r.severity for r in reports)

    resolved = [r for r in reports if r.status == "RESOLVED" and r.resolvedAt]
    avg_resolution_hours = None
    if resolved:
        total_hours = sum((r.resolvedAt - r.createdAt).total_seconds() / 3600 for r in resolved)
        avg_resolution_hours = round(total_hours / len(resolved), 1)

    open_critical = sum(
        1 for r in reports if r.severity == "CRITICAL" and r.status not in ("RESOLVED", "CLOSED", "NOT_AN_ISSUE")
    )

    return DashboardStats(
        total_reports=len(reports),
        by_status=dict(by_status),
        by_category=dict(by_category),
        by_severity=dict(by_severity),
        avg_resolution_hours=avg_resolution_hours,
        open_critical=open_critical,
    )
