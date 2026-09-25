# import os
# import uuid
# from datetime import datetime, timezone

# from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException

# from app.core.config import settings
# from app.core.db import prisma
# from app.core.security import get_current_user, require_role
# from app.schemas.report import ReportOut, ReportStatusUpdate, ReportAssign
# from app.services import vision

# router = APIRouter(prefix="/reports", tags=["reports"])


# def _to_report_out(report) -> ReportOut:
#     """Attach a client-usable relative photo URL (e.g. /uploads/xyz.jpg) --
#     mobile/web clients prepend their own API_BASE_URL to this."""
#     data = report.dict()
#     filename = os.path.basename(report.photoPath) if report.photoPath else None
#     data["photoUrl"] = f"/uploads/{filename}" if filename else None
#     return ReportOut(**data)


# @router.post("", response_model=ReportOut)
# async def create_report(
#     photo: UploadFile = File(...),
#     site_id: int = Form(...),
#     latitude: float | None = Form(None),
#     longitude: float | None = Form(None),
#     location: str | None = Form(None),
#     notes: str | None = Form(None),
#     user=Depends(get_current_user),
# ):
#     """Worker submits a photo. Pipeline: save photo -> AI classify
#     (category + severity) -> create report. Runs synchronously for MVP
#     simplicity; move to a background queue once volume grows."""

#     os.makedirs(settings.upload_dir, exist_ok=True)
#     ext = os.path.splitext(photo.filename or "")[1] or ".jpg"
#     photo_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}{ext}")
#     with open(photo_path, "wb") as f:
#         f.write(await photo.read())

#     classification = await vision.classify_photo(photo_path)

#     status = "NOT_AN_ISSUE" if not classification.is_valid_issue else "OPEN"

#     report = await prisma.report.create(
#         data={
#             "siteId": site_id,
#             "reporterId": user.id,
#             "photoPath": photo_path,
#             "category": classification.category,
#             "severity": classification.severity,
#             "aiConfidence": classification.confidence,
#             "aiDescription": classification.description,
#             "latitude": latitude,
#             "longitude": longitude,
#             "location": location,
#             "notes": notes,
#             "status": status,
#         }
#     )
#     return _to_report_out(report)


# @router.get("", response_model=list[ReportOut])
# async def list_reports(
#     site_id: int | None = None,
#     status: str | None = None,
#     severity: str | None = None,
#     user=Depends(get_current_user),
# ):
#     where = {}
#     if site_id:
#         where["siteId"] = site_id
#     if status:
#         where["status"] = status
#     if severity:
#         where["severity"] = severity

#     reports = await prisma.report.find_many(where=where, order={"createdAt": "desc"})
#     return [_to_report_out(r) for r in reports]


# @router.get("/{report_id}", response_model=ReportOut)
# async def get_report(report_id: int, user=Depends(get_current_user)):
#     report = await prisma.report.find_unique(where={"id": report_id})
#     if not report:
#         raise HTTPException(status_code=404, detail="Report not found")
#     return _to_report_out(report)


# @router.patch("/{report_id}/status", response_model=ReportOut)
# async def update_status(
#     report_id: int,
#     payload: ReportStatusUpdate,
#     # No role restriction at the dependency level anymore -- ANY logged-in
#     # user can call this endpoint. The actual permission check happens
#     # below, once we know both the user's role AND who reported this
#     # specific report, because "worker can acknowledge their own report"
#     # can't be expressed as a static role list.
#     user=Depends(get_current_user),
# ):
#     report = await prisma.report.find_unique(where={"id": report_id})
#     if not report:
#         raise HTTPException(status_code=404, detail="Report not found")

#     is_supervisor_or_admin = user.role in ("SUPERVISOR", "ADMIN")
#     is_own_report = report.reporterId == user.id
#     # A worker may only move THEIR OWN report from OPEN -> ACKNOWLEDGED.
#     # Every other transition (IN_PROGRESS, RESOLVED) and every action on
#     # someone else's report still requires SUPERVISOR/ADMIN.
#     worker_can_acknowledge = (
#         user.role == "WORKER"
#         and is_own_report
#         and report.status == "OPEN"
#         and payload.status == "ACKNOWLEDGED"
#     )

#     if not (is_supervisor_or_admin or worker_can_acknowledge):
#         raise HTTPException(status_code=403, detail="Not authorized for this action")

#     data = {"status": payload.status}
#     if payload.status == "RESOLVED":
#         data["resolvedAt"] = datetime.now(timezone.utc)

#     updated = await prisma.report.update(where={"id": report_id}, data=data)
#     return _to_report_out(updated)


# @router.patch("/{report_id}/assign", response_model=ReportOut)
# async def assign_report(
#     report_id: int,
#     payload: ReportAssign,
#     user=Depends(require_role("SUPERVISOR", "ADMIN")),
# ):
#     report = await prisma.report.update(
#         where={"id": report_id},
#         data={"assignedToId": payload.assigned_to_id, "status": "ACKNOWLEDGED"},
#     )
#     if not report:
#         raise HTTPException(status_code=404, detail="Report not found")
#     return _to_report_out(report)












import os
import uuid
from datetime import datetime, timezone

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException

from app.core.config import settings
from app.core.db import prisma
from app.core.security import get_current_user, require_role
from app.schemas.report import ReportOut, ReportStatusUpdate, ReportAssign
from app.services import vision

# Auto-configures using CLOUDINARY_URL environment variable
cloudinary.config(secure=True)

router = APIRouter(prefix="/reports", tags=["reports"])


def _to_report_out(report) -> ReportOut:
    """Returns report schema. 
    If photoPath starts with http, return it directly (Cloudinary URL).
    Otherwise fallback to relative uploads path for legacy local files."""
    data = report.dict()
    photo_path = report.photoPath or ""
    
    if photo_path.startswith("http://") or photo_path.startswith("https://"):
        data["photoUrl"] = photo_path
    else:
        filename = os.path.basename(photo_path) if photo_path else None
        data["photoUrl"] = f"/uploads/{filename}" if filename else None

    return ReportOut(**data)


@router.post("", response_model=ReportOut)
async def create_report(
    photo: UploadFile = File(...),
    site_id: int = Form(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    location: str | None = Form(None),
    notes: str | None = Form(None),
    user=Depends(get_current_user),
):
    """Worker submits a photo. Uploads to Cloudinary, runs AI classification, 
    and saves full HTTPS Cloudinary URL to database."""
    
    # Read image content
    photo_bytes = await photo.read()

    # 1. Upload directly to Cloudinary
    upload_result = cloudinary.uploader.upload(
        photo_bytes,
        folder="safety_reports",
        resource_type="image"
    )
    
    # Permanent HTTPS URL from Cloudinary
    cloudinary_photo_url = upload_result.get("secure_url")

    # 2. Run AI vision classification using Cloudinary URL (or bytes)
    classification = await vision.classify_photo(cloudinary_photo_url)

    status = "NOT_AN_ISSUE" if not classification.is_valid_issue else "OPEN"

    # 3. Store permanent Cloudinary URL into database as photoPath
    report = await prisma.report.create(
        data={
            "siteId": site_id,
            "reporterId": user.id,
            "photoPath": cloudinary_photo_url,
            "category": classification.category,
            "severity": classification.severity,
            "aiConfidence": classification.confidence,
            "aiDescription": classification.description,
            "latitude": latitude,
            "longitude": longitude,
            "location": location,
            "notes": notes,
            "status": status,
        }
    )
    return _to_report_out(report)


@router.get("", response_model=list[ReportOut])
async def list_reports(
    site_id: int | None = None,
    status: str | None = None,
    severity: str | None = None,
    user=Depends(get_current_user),
):
    where = {}
    if site_id:
        where["siteId"] = site_id
    if status:
        where["status"] = status
    if severity:
        where["severity"] = severity

    reports = await prisma.report.find_many(where=where, order={"createdAt": "desc"})
    return [_to_report_out(r) for r in reports]


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(report_id: int, user=Depends(get_current_user)):
    report = await prisma.report.find_unique(where={"id": report_id})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _to_report_out(report)


@router.patch("/{report_id}/status", response_model=ReportOut)
async def update_status(
    report_id: int,
    payload: ReportStatusUpdate,
    user=Depends(get_current_user),
):
    report = await prisma.report.find_unique(where={"id": report_id})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    is_supervisor_or_admin = user.role in ("SUPERVISOR", "ADMIN")
    is_own_report = report.reporterId == user.id

    worker_can_acknowledge = (
        user.role == "WORKER"
        and is_own_report
        and report.status == "OPEN"
        and payload.status == "ACKNOWLEDGED"
    )

    if not (is_supervisor_or_admin or worker_can_acknowledge):
        raise HTTPException(status_code=403, detail="Not authorized for this action")

    data = {"status": payload.status}
    if payload.status == "RESOLVED":
        data["resolvedAt"] = datetime.now(timezone.utc)

    updated = await prisma.report.update(where={"id": report_id}, data=data)
    return _to_report_out(updated)


@router.patch("/{report_id}/assign", response_model=ReportOut)
async def assign_report(
    report_id: int,
    payload: ReportAssign,
    user=Depends(require_role("SUPERVISOR", "ADMIN")),
):
    report = await prisma.report.update(
        where={"id": report_id},
        data={"assignedToId": payload.assigned_to_id, "status": "ACKNOWLEDGED"},
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _to_report_out(report)