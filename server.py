#python -m fastapi dev .\server.py
#python -m uvicorn main:api --reload
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api.routes.media_generation import router as media_generation_router
from api.routes.auth import router as auth_router
from api.routes.social import router as social_router
from api.routes.media import router as media_router
from api.routes.trending import router as trending_router
from api.routes.voice import router as voice_router
from api.routes.background import router as background_router
from api.routes.subtitle import router as subtitle_router
from api.routes.video import router as video_router
from api.routes.facebook_pages import router as facebook_pages_router
from api.routes.video_export import router as video_export_router
import uvicorn
import time
import logging
from contextlib import asynccontextmanager
from config import test_connection
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
@asynccontextmanager
async def lifespan(app:FastAPI):
    await test_connection()
    yield
# Create FastAPI app
api = FastAPI(
    title="Media Processing API",
    description="API for processing media files with AI",
    version="1.0.0",
    lifespan=lifespan, 
)
# Add CORS middleware
api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=['Content-Type', 'Authorization'],
)

# Include routers
api.include_router(media_generation_router)
api.include_router(auth_router)
api.include_router(media_router)
api.include_router(social_router)
api.include_router(trending_router)
api.include_router(voice_router)
api.include_router(background_router)
api.include_router(subtitle_router)
api.include_router(video_router)
api.include_router(facebook_pages_router)
api.include_router(video_export_router)

# Request logging middleware
@api.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
    return response
@api.get("/")
def index():
    return {
        "app": "Media Processing API",
        "version": "1.0.0",
        "status": "running"
    }

if __name__ == "__main__":
    uvicorn.run("server:api", host="127.0.0.1", port=8000, reload=True)
    
