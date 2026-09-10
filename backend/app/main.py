from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.database import Base, engine
import app.models  # Import all models to register on Base.metadata
from app.routers import auth, test_roles, projects, users, schedule, execution, dashboard, ai_chat, progress_reports, planner_review


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize all database tables safely on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="SIH26122 Backend",
    description="Intelligent Data Capture & Schedule-Linking Layer for Infrastructure Project Management API",
    version="0.3.0",
    lifespan=lifespan,
)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth.router, prefix="/api")
app.include_router(test_roles.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(execution.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(ai_chat.router, prefix="/api")
app.include_router(progress_reports.router, prefix="/api")
app.include_router(planner_review.router, prefix="/api")



@app.get("/api/health", tags=["Health"])
def health_check():
    """Health check endpoint to verify backend operational status and connectivity."""
    return {
        "status": "ok",
        "service": "SIH26122 Backend"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
