from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.db import prisma
from app.core.security import get_current_user, require_role

router = APIRouter(tags=["inspections"])


# ---------- Checklist templates (created by supervisors/admins) ----------

class ChecklistItemIn(BaseModel):
    label: str
    order: int = 0


class ChecklistTemplateCreate(BaseModel):
    name: str
    category: str | None = None
    site_id: int
    items: list[ChecklistItemIn]


@router.post("/checklist-templates")
async def create_template(payload: ChecklistTemplateCreate, user=Depends(require_role("SUPERVISOR", "ADMIN"))):
    template = await prisma.checklisttemplate.create(
        data={
            "name": payload.name,
            "category": payload.category,
            "siteId": payload.site_id,
            "items": {
                "create": [
                    {"label": item.label, "order": item.order} for item in payload.items
                ]
            },
        },
        include={"items": True},
    )
    return template


@router.get("/checklist-templates")
async def list_templates(site_id: int | None = None, user=Depends(get_current_user)):
    where = {"siteId": site_id} if site_id else {}
    return await prisma.checklisttemplate.find_many(where=where, include={"items": True})


# ---------- Inspections (a worker/supervisor running through a template) ----------

class InspectionStart(BaseModel):
    site_id: int
    template_id: int
    scheduled_for: datetime | None = None


@router.post("/inspections")
async def start_inspection(payload: InspectionStart, user=Depends(get_current_user)):
    inspection = await prisma.inspection.create(
        data={
            "siteId": payload.site_id,
            "templateId": payload.template_id,
            "inspectorId": user.id,
            "scheduledFor": payload.scheduled_for,
            "startedAt": datetime.now(timezone.utc),
            "status": "IN_PROGRESS",
        }
    )
    return inspection


class ItemResultIn(BaseModel):
    checklist_item_id: int
    passed: bool
    notes: str | None = None
    photo_path: str | None = None


@router.post("/inspections/{inspection_id}/items")
async def record_item_result(inspection_id: int, payload: ItemResultIn, user=Depends(get_current_user)):
    inspection = await prisma.inspection.find_unique(where={"id": inspection_id})
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    result = await prisma.inspectionitemresult.create(
        data={
            "inspectionId": inspection_id,
            "checklistItemId": payload.checklist_item_id,
            "passed": payload.passed,
            "notes": payload.notes,
            "photoPath": payload.photo_path,
        }
    )
    return result


@router.post("/inspections/{inspection_id}/complete")
async def complete_inspection(inspection_id: int, user=Depends(get_current_user)):
    inspection = await prisma.inspection.update(
        where={"id": inspection_id},
        data={"status": "COMPLETED", "completedAt": datetime.now(timezone.utc)},
    )
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return inspection


@router.get("/inspections/{inspection_id}")
async def get_inspection(inspection_id: int, user=Depends(get_current_user)):
    inspection = await prisma.inspection.find_unique(
        where={"id": inspection_id},
        include={"results": {"include": {"checklistItem": True}}, "template": True},
    )
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return inspection


@router.get("/inspections")
async def list_inspections(site_id: int | None = None, status: str | None = None, user=Depends(get_current_user)):
    where = {}
    if site_id:
        where["siteId"] = site_id
    if status:
        where["status"] = status
    return await prisma.inspection.find_many(where=where, order={"createdAt": "desc"})
