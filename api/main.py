"""
WMS FastAPI Service Layer
Exposes the 6 read-only WMS tool functions as HTTP endpoints.
- Swagger UI: http://localhost:8001/docs
- Rate limiter: 60 req/min per IP (Apigee equivalent)
- Basic Auth:   X-Supervisor-Id header or HTTP Basic (OKTA equivalent)
- Audit logs:   structured JSON to logs/wms_audit.jsonl
"""

import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from api.middleware import setup_middleware
from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("  WMS FastAPI Service")
    print("  Docs:  http://localhost:8001/docs")
    print("  Tools: http://localhost:8001/tools/")
    print("=" * 60)
    yield


app = FastAPI(
    title="WMS Supervisor Tool API",
    description=(
        "Read-only Warehouse Management System lookups. "
        "All endpoints are parameterized, pre-approved queries — "
        "the LLM never writes SQL."
    ),
    version="1.0.0",
    contact={"name": "WMS Operations", "email": "ops@warehouse.internal"},
    lifespan=lifespan,
)

setup_middleware(app)
app.include_router(router, prefix="/tools", tags=["WMS Tools"])


@app.get("/health", tags=["Health"])
def health():
    """Service liveness check."""
    return {"status": "ok", "service": "wms-tool-api"}


if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)
