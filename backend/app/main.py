from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, ble, exchange, payment, report, reservation, store, user
from app.tasks.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield


app = FastAPI(
    title="知行岛自习室预约系统 API",
    description="微信小程序 + 后台管理系统后端",
    version="1.0.2",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router, prefix="/api")
app.include_router(store.router, prefix="/api")
app.include_router(reservation.router, prefix="/api")
app.include_router(ble.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(exchange.router, prefix="/api")
app.include_router(payment.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
