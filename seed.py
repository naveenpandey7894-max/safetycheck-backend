"""Populate a fresh DB with sample data so the pipeline can be tested
end-to-end immediately.

Run with: python seed.py
(after `prisma generate` and `prisma db push`)
"""
import asyncio

from prisma import Prisma
from app.core.security import hash_password


async def main():
    db = Prisma()
    await db.connect()

    company = await db.company.create(data={"name": "Sample Manufacturing Pvt Ltd"})

    site = await db.site.create(
        data={
            "name": "Plant 1 - Indore",
            "address": "Industrial Area, Indore",
            "city": "Indore",
            "companyId": company.id,
            "minLat": 22.68,
            "maxLat": 22.75,
            "minLng": 75.83,
            "maxLng": 75.90,
        }
    )

    admin = await db.user.create(
        data={
            "name": "Admin User",
            "email": "admin@example.com",
            "hashedPassword": hash_password("admin123"),
            "role": "ADMIN",
            "companyId": company.id,
        }
    )

    worker = await db.user.create(
        data={
            "name": "Sample Worker",
            "email": "worker@example.com",
            "hashedPassword": hash_password("worker123"),
            "role": "WORKER",
            "companyId": company.id,
        }
    )

    template = await db.checklisttemplate.create(
        data={
            "name": "Weekly Fire Safety Audit",
            "category": "Fire Safety",
            "siteId": site.id,
            "items": {
                "create": [
                    {"label": "Fire extinguisher pressure gauge in green zone", "order": 1},
                    {"label": "Emergency exits unobstructed", "order": 2},
                    {"label": "Fire alarm panel shows no faults", "order": 3},
                ]
            },
        }
    )

    await db.disconnect()

    print("Seed complete:")
    print(f"  Company:  {company.name} (id={company.id})")
    print(f"  Site:     {site.name} (id={site.id})")
    print(f"  Admin:    admin@example.com / admin123 (id={admin.id})")
    print(f"  Worker:   worker@example.com / worker123 (id={worker.id})")
    print(f"  Template: {template.name} (id={template.id})")


if __name__ == "__main__":
    asyncio.run(main())
