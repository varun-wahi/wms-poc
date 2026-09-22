"""
WMS MCP Server (Model Context Protocol)
Exposes the 6 read-only WMS tool functions as MCP tools so any
MCP-compatible AI agent (Claude Desktop, another Gemini agent, etc.)
can discover and call them without custom integration code.

Transport: SSE (HTTP) on http://localhost:8002/sse
           — connect from Claude Desktop or the MCP Inspector.

Usage:
    # In one terminal (with venv activated):
    python -m mcp_server.server

    # Test with the MCP Inspector (no install needed):
    npx @modelcontextprotocol/inspector http://localhost:8002/sse
"""

import json
import logging

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount

from wms_agent.tools import (
    get_task_owner,
    get_pending_tasks,
    get_pending_olpns,
    get_unloaded_olpns,
    get_unwaved_orders,
    get_idle_users,
)

log = logging.getLogger("wms.mcp")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# ---------------------------------------------------------------------------
# MCP Server definition
# ---------------------------------------------------------------------------
server = Server("wms-tools")

_TOOLS: list[Tool] = [
    Tool(
        name="get_task_owner",
        description="Find who is working a given pick task. Returns the assigned picker's name, task status, and shipment.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task number, e.g. 'TSK500101'"},
            },
            "required": ["task_id"],
        },
    ),
    Tool(
        name="get_pending_tasks",
        description="List tasks not yet completed (pending or in-progress) for a shipment/truck.",
        inputSchema={
            "type": "object",
            "properties": {
                "shipment_id": {"type": "string", "description": "Shipment number, e.g. 'SHP10001'"},
            },
            "required": ["shipment_id"],
        },
    ),
    Tool(
        name="get_pending_olpns",
        description="List OLPNs (cartons/pallets) still pending (not yet picked) for a shipment.",
        inputSchema={
            "type": "object",
            "properties": {
                "shipment_id": {"type": "string", "description": "Shipment number, e.g. 'SHP10001'"},
            },
            "required": ["shipment_id"],
        },
    ),
    Tool(
        name="get_unloaded_olpns",
        description="List OLPNs not yet loaded onto the truck (pending or picked but not loaded) for a shipment.",
        inputSchema={
            "type": "object",
            "properties": {
                "shipment_id": {"type": "string", "description": "Shipment number, e.g. 'SHP10001'"},
            },
            "required": ["shipment_id"],
        },
    ),
    Tool(
        name="get_unwaved_orders",
        description="List customer orders on a shipment that have not been released/waved yet.",
        inputSchema={
            "type": "object",
            "properties": {
                "shipment_id": {"type": "string", "description": "Shipment number, e.g. 'SHP10001'"},
            },
            "required": ["shipment_id"],
        },
    ),
    Tool(
        name="get_idle_users",
        description="Find pickers who are clocked in but have no pending or in-progress task (out of work).",
        inputSchema={
            "type": "object",
            "properties": {
                "site_id": {
                    "type": "string",
                    "description": "Site code e.g. 'SITE01', or empty string for all sites.",
                },
            },
            "required": ["site_id"],
        },
    ),
]

_TOOL_FN = {
    "get_task_owner": get_task_owner,
    "get_pending_tasks": get_pending_tasks,
    "get_pending_olpns": get_pending_olpns,
    "get_unloaded_olpns": get_unloaded_olpns,
    "get_unwaved_orders": get_unwaved_orders,
    "get_idle_users": get_idle_users,
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return _TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    log.info("mcp_call tool=%s args=%s", name, arguments)
    fn = _TOOL_FN.get(name)
    if not fn:
        return [TextContent(type="text", text=json.dumps({"status": "error", "message": f"Unknown tool: {name}"}))]
    result = fn(**arguments)
    return [TextContent(type="text", text=json.dumps(result, default=str))]


# ---------------------------------------------------------------------------
# SSE transport + Starlette app
# ---------------------------------------------------------------------------
sse_transport = SseServerTransport("/messages")


async def sse_endpoint(scope, receive, send):
    async with sse_transport.connect_sse(scope, receive, send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=sse_endpoint),
        Mount("/messages", app=sse_transport.handle_post_message),
    ]
)


if __name__ == "__main__":
    print("=" * 60)
    print("  WMS MCP Server (SSE)")
    print("  Endpoint: http://localhost:8002/sse")
    print("  Inspector: npx @modelcontextprotocol/inspector http://localhost:8002/sse")
    print("=" * 60)
    uvicorn.run(starlette_app, host="0.0.0.0", port=8002)
