"""Six pre-approved, parameterized, read-only WMS lookups. The LLM never writes SQL."""
import functools, json, logging, logging.handlers, os, re, time
from collections import Counter
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

# ---------------------------------------------------------------------------
# Structured JSON audit logger → logs/wms_audit.jsonl
# ---------------------------------------------------------------------------
_log_dir = Path("logs")
_log_dir.mkdir(exist_ok=True)

log = logging.getLogger("wms.audit")
log.setLevel(logging.INFO)

_file_handler = logging.handlers.RotatingFileHandler(
    _log_dir / "wms_audit.jsonl",
    maxBytes=10 * 1024 * 1024,  # 10 MB per file
    backupCount=5,
)
_file_handler.setFormatter(logging.Formatter("%(message)s"))
log.addHandler(_file_handler)

# Also keep a console handler so ADK terminal still shows tool calls
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
log.addHandler(_console_handler)


def _audit(tool_name: str, args: tuple, kwargs: dict, result: dict, duration_ms: float) -> None:
    """Write one structured JSON record per tool invocation."""
    log.info(json.dumps({
        "ts": time.time(),
        "tool": tool_name,
        "args": args,
        "kwargs": kwargs,
        "result_status": result.get("status", "unknown"),
        "duration_ms": round(duration_ms, 1),
    }, default=str))


MAX_ROWS = 50
_ID = re.compile(r"[A-Z0-9_-]{1,20}")
_INVALID = {"status": "invalid_input", "message": "That ID looks malformed."}


def _conn():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "wms"), user=os.getenv("DB_USER", "wms_reader"),
        password=os.getenv("DB_PASSWORD", "reader_pw"), row_factory=dict_row, connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=5000",
    )


def _query(sql, params=()):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _tool(fn):  # structured audit log + never leak raw DB errors to the model/user
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        t0 = time.perf_counter()
        try:
            result = fn(*a, **kw)
            _audit(fn.__name__, a, kw, result, (time.perf_counter() - t0) * 1000)
            return result
        except Exception:
            duration_ms = (time.perf_counter() - t0) * 1000
            error_result = {"status": "error", "message": "Database lookup failed. Try again or contact IT."}
            _audit(fn.__name__, a, kw, error_result, duration_ms)
            log.exception("tool %s failed", fn.__name__)
            return error_result
    return wrapper


def _norm(v):
    return str(v or "").strip().upper()


def _shipment_list(shipment_id, sql, key):
    sid = _norm(shipment_id)
    if not _ID.fullmatch(sid):
        return _INVALID
    if not _query("SELECT 1 FROM shipments WHERE shipment_id=%s", (sid,)):
        return {"status": "not_found", "message": f"Shipment {sid} not found."}
    rows = _query(sql, (sid,))
    return {"status": "success", "shipment_id": sid, "count": len(rows),
            "by_status": dict(Counter(r["status"] for r in rows)),
            key: rows[:MAX_ROWS], "truncated": len(rows) > MAX_ROWS}


@_tool
def get_task_owner(task_id: str) -> dict:
    """Find who is working a given pick task.

    Args:
        task_id: Task number, e.g. 'TSK500101'.
    Returns:
        Dict with the assigned user's name (None if unassigned), task status and shipment.
    """
    tid = _norm(task_id)
    if not _ID.fullmatch(tid):
        return _INVALID
    rows = _query(
        "SELECT t.task_id, t.status AS task_status, t.shipment_id, t.assigned_at::text AS assigned_at, "
        "u.user_name AS assigned_to FROM tasks t LEFT JOIN users u ON u.user_id=t.user_id "
        "WHERE t.task_id=%s", (tid,))
    if not rows:
        return {"status": "not_found", "message": f"Task {tid} not found."}
    return {"status": "success", **rows[0]}


@_tool
def get_pending_tasks(shipment_id: str) -> dict:
    """List tasks not yet completed (pending or in progress) for a shipment/truck.

    Args:
        shipment_id: Shipment number, e.g. 'SHP10001'.
    """
    return _shipment_list(
        shipment_id,
        "SELECT t.task_id, t.status, u.user_name AS assigned_to FROM tasks t "
        "LEFT JOIN users u ON u.user_id=t.user_id "
        "WHERE t.shipment_id=%s AND t.status<>'completed' ORDER BY t.task_id", "tasks")


@_tool
def get_pending_olpns(shipment_id: str) -> dict:
    """List OLPNs still pending (not yet picked) for a shipment/truck.

    Args:
        shipment_id: Shipment number, e.g. 'SHP10001'.
    """
    return _shipment_list(
        shipment_id,
        "SELECT olpn_id, status, task_id FROM olpns WHERE shipment_id=%s AND status='pending' "
        "ORDER BY olpn_id", "olpns")


@_tool
def get_unloaded_olpns(shipment_id: str) -> dict:
    """List OLPNs not yet loaded onto the truck (pending or picked) for a shipment.

    Args:
        shipment_id: Shipment number, e.g. 'SHP10001'.
    """
    return _shipment_list(
        shipment_id,
        "SELECT olpn_id, status, task_id FROM olpns WHERE shipment_id=%s AND status<>'loaded' "
        "ORDER BY olpn_id", "olpns")


@_tool
def get_unwaved_orders(shipment_id: str) -> dict:
    """List orders on a shipment that have not been waved yet.

    Args:
        shipment_id: Shipment number, e.g. 'SHP10001'.
    """
    return _shipment_list(
        shipment_id,
        "SELECT order_id, status FROM orders WHERE shipment_id=%s AND status='not_waved' "
        "ORDER BY order_id", "orders")


@_tool
def get_idle_users(site_id: str) -> dict:
    """Find pickers who are clocked in but have no pending or in-progress task (out of work).

    Args:
        site_id: Site code such as 'SITE01', or an empty string for all sites.
    """
    site = _norm(site_id) or None
    rows = _query(
        "SELECT u.user_id, u.user_name, u.site_id, "
        "(SELECT ROUND(EXTRACT(EPOCH FROM (NOW()-MAX(completed_at)))/60)::int FROM tasks "
        " WHERE user_id=u.user_id AND status='completed') AS minutes_since_last_task "
        "FROM users u WHERE u.role='picker' AND u.is_active_shift "
        "AND (%(site)s::text IS NULL OR u.site_id=%(site)s::text) "
        "AND NOT EXISTS (SELECT 1 FROM tasks t WHERE t.user_id=u.user_id "
        "                AND t.status IN ('pending','in_progress')) ORDER BY u.user_name",
        {"site": site})
    return {"status": "success", "count": len(rows), "users": rows[:MAX_ROWS]}
