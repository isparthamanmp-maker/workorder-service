from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager

from src.config.database import db_manager
from src.api.routes.user_routes import router as api_router
from src.api.routes.work_order_routes import router as work_order_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events"""
    # Startup
    print("Initializing database...")
    db_manager.init_db()
    
    # Create tables (in production, use Alembic migrations)
    from src.models.base import Base
    try:
        Base.metadata.create_all(bind=db_manager.engine)
        print("Database tables created/verified")
    except Exception as e:
        print(f"Error creating tables: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down...")
    if db_manager.engine:
        db_manager.engine.dispose()

# Create FastAPI app
app = FastAPI(
    title="Microservice DB Abstraction",
    description="Microservice with multi-database support",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)
app.include_router(work_order_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "microservice-db",
        "database": "connected" if db_manager.engine else "disconnected"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Microservice DB Abstraction API",
        "docs": "/docs",
        "redoc": "/redoc"
    }

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=6001,
        reload=False,
        log_level="info"
    )