# WMS POC Enhancement Tasks

- [x] **1. FastAPI service layer** (`api/main.py`, `api/routes.py`)
  - [x] 6 HTTP endpoints wrapping tool functions
  - [x] Auto Swagger UI at /docs
- [x] **2. Middleware** (`api/middleware.py`)
  - [x] Rate limiter (429 after 60 req/min)
  - [x] Structured JSON audit logger (logs/wms_audit.jsonl)
  - [x] HTTP Basic Auth + X-Supervisor-Id header
- [x] **3. MCP server** (`mcp_server/server.py`)
  - [x] Install `google-adk[mcp]`
  - [x] SSE transport on port 8002
  - [x] All 6 tools registered
- [x] **4. Structured audit logging** (`wms_agent/tools.py`)
  - [x] JSON log records to `logs/wms_audit.jsonl`
  - [x] Rotating file handler (10MB, 5 backups)
  - [x] duration_ms + result_status per record
- [x] **5. Session context** (`wms_agent/agent.py`)
  - [x] supervisor_id + supervisor_site in prompt instructions
  - [x] Auto site scoping for get_idle_users
- [x] **6. Update requirements.txt** (google-adk[mcp], uvicorn)
- [x] **7. Run all tests + verify endpoints** — 9/9 passing, all curl tests green

