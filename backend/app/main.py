"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import tournament, players, system
from app.scheduler import start_scheduler, stop_scheduler

# Configure logging to show in console
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB and scheduler on startup, shut down scheduler on exit."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized.")
    logger.info("Starting scheduler...")
    start_scheduler()
    logger.info("Scheduler started.")
    yield
    logger.info("Shutting down scheduler...")
    stop_scheduler()
    logger.info("Scheduler stopped.")


app = FastAPI(title="PGA Tournament Analysis", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tournament.router, prefix="/api/tournament", tags=["tournament"])
app.include_router(players.router, prefix="/api/players", tags=["players"])
app.include_router(system.router, prefix="/api", tags=["system"])
