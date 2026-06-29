from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api.routes import admin, admin_tools, assistant, ble, card, exchange, home, payment, report, reservation, store, user
from app.core.config import settings
from app.db.session import get_db
from app.services.health import run_health_checks
from app.tasks.scheduler import start_scheduler

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.services.schema_migrate import run_schema_migrations

    settings.validate_for_production()

    db = SessionLocal()
    try:
        run_schema_migrations(db)
    finally:
        db.close()
    start_scheduler()
    yield


app = FastAPI(
    title="知行岛自习室预约系统 API",
    description="微信小程序 + 后台管理系统后端",
    version="1.0.2",
    lifespan=lifespan,
)
_cors_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # 通配来源时浏览器禁止携带凭证；本系统用 Bearer Token 鉴权，无需 cookie 凭证
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router, prefix="/api")
app.include_router(store.router, prefix="/api")
app.include_router(reservation.router, prefix="/api")
app.include_router(ble.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(exchange.router, prefix="/api")
app.include_router(card.router, prefix="/api")
app.include_router(payment.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(home.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(admin_tools.router, prefix="/api")

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(UPLOADS_DIR)), name="static")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    return run_health_checks(db)


@app.get("/health/live")
def health_live():
    return {"status": "ok"}
