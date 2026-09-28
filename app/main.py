import os

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.db import prisma
from app.routers import auth, sites, reports, inspections, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    await prisma.connect()
    yield
    await prisma.disconnect()


app = FastAPI(
    title="SafetyCheck API",
    description="Backend for a factory/facility safety inspection & "
                 "compliance platform: photo -> AI severity classification "
                 "-> assignment -> resolution tracking, plus checklist-based "
                 "inspections and a compliance dashboard.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded photos so mobile/web clients can display them, e.g.
# GET /uploads/<filename> -> the actual image bytes.
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
#app.mount("/", StaticFiles(directory="public", html=True), name="public")

app.include_router(auth.router)
app.include_router(sites.router)
app.include_router(reports.router)
app.include_router(inspections.router)
app.include_router(dashboard.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "SafetyCheck API"}


@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/privacy-policy.html")
def privacy_policy():
    return FileResponse("public/privacy-policy.html")


@app.get("/terms-and-conditions.html")
def terms_and_conditions():
    return FileResponse("public/terms-and-conditions.html")





# from contextlib import asynccontextmanager

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# from app.core.db import prisma
# from app.routers import auth, sites, reports, inspections, dashboard


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     await prisma.connect()
#     yield
#     await prisma.disconnect()


# app = FastAPI(
#     title="SafetyCheck API",
#     description="Backend for a factory/facility safety inspection & "
#                  "compliance platform: photo -> AI severity classification "
#                  "-> assignment -> resolution tracking, plus checklist-based "
#                  "inspections and a compliance dashboard.",
#     version="0.1.0",
#     lifespan=lifespan,
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # tighten this in production
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(auth.router)
# app.include_router(sites.router)
# app.include_router(reports.router)
# app.include_router(inspections.router)
# app.include_router(dashboard.router)


# @app.get("/")
# def root():
#     return {"status": "ok", "service": "SafetyCheck API"}


# @app.get("/health")
# def health():
#     return {"status": "healthy"}
