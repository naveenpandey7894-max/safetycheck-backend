from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.db import prisma
from app.core.security import get_current_user, require_role

router = APIRouter(prefix="/sites", tags=["sites"])


class SiteCreate(BaseModel):
    name: str
    address: str | None = None
    city: str | None = None
    company_id: int
    min_lat: float | None = None
    max_lat: float | None = None
    min_lng: float | None = None
    max_lng: float | None = None


@router.post("")
async def create_site(payload: SiteCreate, user=Depends(require_role("ADMIN"))):
    site = await prisma.site.create(
        data={
            "name": payload.name,
            "address": payload.address,
            "city": payload.city,
            "companyId": payload.company_id,
            "minLat": payload.min_lat,
            "maxLat": payload.max_lat,
            "minLng": payload.min_lng,
            "maxLng": payload.max_lng,
        }
    )
    return site


@router.get("")
async def list_sites(company_id: int | None = None, user=Depends(get_current_user)):
    where = {"companyId": company_id} if company_id else {}
    return await prisma.site.find_many(where=where)


@router.get("/{site_id}")
async def get_site(site_id: int, user=Depends(get_current_user)):
    site = await prisma.site.find_unique(where={"id": site_id})
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site
