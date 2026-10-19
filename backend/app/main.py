import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.api.routes import router as api_router
from backend.app.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="Loan Eligibility Engine API",
    description="Scalable event-driven bulk loan matching and notification platform",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# Mount frontend static directory if exists
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/ui", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.get("/")
def root():
    return {
        "message": "Loan Eligibility Engine is running",
        "docs": "/docs",
        "frontend": "/ui",
        "health": "/api/health",
    }
