# WMS Supervisor Assistant POC

A secure, read-only AI assistant and API service designed for warehouse supervisors. It answers operational questions about pick tasks, OLPNs, shipments, and idle pickers with deterministic data guarantees.

> **Security Guarantee:** The LLM **never** writes or executes raw SQL. All data retrieval runs through pre-approved, parameterized Python functions with regex input validation, database read-only constraints, and strict execution timeouts.

---

## Architecture & Services

| Service | Port | Description |
|---|---|---|
| **ADK Web Agent UI** | `:8000` | Conversational interface powered by Google ADK & Gemini |
| **FastAPI REST API** | `:8001` | REST endpoints with interactive Swagger UI at `/docs` |
| **MCP Server** | `:8002` | Model Context Protocol server (`/sse`) for external AI tools |
| **Adminer (Database UI)** | `:8081` | Web-based database management interface for PostgreSQL |
| **PostgreSQL 16** | `:5432` | Relational WMS test database with schema and seed data |
| **Structured Audit Logs** | File | Append-only rotating JSON log at `logs/wms_audit.jsonl` |

---

## 1. Prerequisites

- [Docker Desktop](https://www.docker.com/) installed and running
- Python 3.10+
- A Google Gemini API Key (no GCP billing required for local testing)

---

## 2. Local Setup (Step-by-Step)

### Step 1: Start PostgreSQL & Adminer
Start the database container. PostgreSQL automatically executes `schema.sql` and `seed.sql` on first launch:
```bash
docker compose up -d
```
*To reset the database cleanly at any point: `docker compose down -v && docker compose up -d`.*

### Step 2: Set Up Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy the example environment file:
```bash
cp .env.example .env
cp .env.example wms_agent/.env
```
Ensure your `.env` contains your Gemini API key:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
MODEL=gemini-2.5-flash

# Database Settings (matches docker-compose.yml defaults)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=wms
DB_USER=postgres
DB_PASSWORD=postgres
```

---

## 3. Running the Services

You can run any or all of the three services concurrently across separate terminal windows:

### Service A: ADK Web Assistant (Chatbot UI)
In your terminal (with `.venv` activated):
```bash
adk web
```
- Open your browser to **http://localhost:8000**
- Select **`wms_agent`** from the agent dropdown.

### Service B: FastAPI Service (REST API & Swagger)
In a second terminal:
```bash
source .venv/bin/activate
python -m uvicorn api.main:app --port 8001 --reload
```
- Interactive Swagger UI: **http://localhost:8001/docs**
- ReDoc UI: **http://localhost:8001/redoc**

### Service C: Model Context Protocol (MCP) Server
In a third terminal:
```bash
source .venv/bin/activate
python -m mcp_server.server
```
- SSE endpoint available at: **http://localhost:8002/sse**

### Database UI: Adminer
- Open your browser to **http://localhost:8081**
- **System**: PostgreSQL
- **Server**: `db` (or `localhost` if connecting from host machine)
- **Username**: `postgres`
- **Password**: `postgres`
- **Database**: `wms`

---

## 4. How to Test & Verify

### 1. Run Automated Unit & Integration Tests
Run pytest to verify the 6 deterministic tools, input sanitization, and DB constraints without triggering LLM calls:
```bash
pytest -v
```

### 2. Test the REST API via cURL
Test health check and individual WMS tool endpoints:
```bash
# 1. Health check
curl -s http://localhost:8001/health

# 2. Get task owner
curl -s http://localhost:8001/tools/task/TSK500101

# 3. Pending tasks for a shipment
curl -s http://localhost:8001/tools/shipment/SHP10001/tasks

# 4. Pending OLPNs (not yet picked)
curl -s http://localhost:8001/tools/shipment/SHP10001/olpns/pending

# 5. Unloaded OLPNs
curl -s http://localhost:8001/tools/shipment/SHP10003/olpns/unloaded

# 6. Unwaved orders
curl -s http://localhost:8001/tools/shipment/SHP10002/orders/unwaved

# 7. Idle pickers for a specific site (or empty for all sites)
curl -s "http://localhost:8001/tools/users/idle?site_id=SITE01"
```

#### Test Authentication & Rate Limiting
```bash
# Provide supervisor identity
curl -s -H "X-Supervisor-Id: SUP_SARAH_01" http://localhost:8001/tools/task/TSK500101

# Trigger Rate Limiter (60 req/min limit - returns 429 when exceeded)
for i in {1..70}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/health; done
```

### 3. Test the MCP Server with MCP Inspector
Inspect the MCP tools directly in your browser:
```bash
npx @modelcontextprotocol/inspector http://localhost:8002/sse
```

### 4. Test the Agent in ADK Web (Sample Queries)
Try asking the supervisor assistant in http://localhost:8000:
- *"Who is picking task TSK500101?"*
- *"How many pending tasks are there for truck SHP10001?"*
- *"Which OLPNs are not yet loaded for shipment SHP10003?"*
- *"Are there any orders not waved for SHP10002?"*
- *"Who is currently idle at SITE01?"*
- *"What is the ETA for truck delivery?"* *(Notice: The agent politely declines as out-of-scope rather than hallucinating)*

### 5. Inspect Structured Audit Logs
Every tool invocation from the Agent, REST API, or MCP server emits a structured audit record:
```bash
# View live audit log stream
tail -f logs/wms_audit.jsonl

# Pretty-print recent logs with jq
tail -n 5 logs/wms_audit.jsonl | jq .
```
Sample record:
```json
{
  "ts": 1726987345.12,
  "tool": "get_pending_tasks",
  "args": ["SHP10001"],
  "kwargs": {},
  "result_status": "success",
  "duration_ms": 3.8
}
```

---

## 5. GCP Production Deployment Roadmap

When deploying to Google Cloud Platform:
1. **Database**: Migrate from local Docker Postgres to **AlloyDB for PostgreSQL** with Private Service Connect / VPC peering.
2. **Identity**: Connect **Okta / Google Cloud Identity** via OAuth2/OIDC into the middleware.
3. **API Gateway**: Place **Apigee** in front of Cloud Run to manage external rate limits, quotas, and analytics.
4. **Compute**: Deploy the container to **Cloud Run** with internal VPC egress:
   ```bash
   gcloud run deploy wms-agent \
     --source . \
     --region us-central1 \
     --no-allow-unauthenticated \
     --network default \
     --subnet default \
     --vpc-egress private-ranges-only \
     --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=<project_id>,GOOGLE_CLOUD_LOCATION=us-central1,DB_HOST=<alloydb_private_ip>,DB_NAME=postgres,DB_USER=wms_reader,DB_PASSWORD=<pw>
   ```
