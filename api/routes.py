"""
FastAPI route handlers — one endpoint per WMS tool function.
Each endpoint delegates directly to the validated, read-only tool functions.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from wms_agent.tools import (
    get_task_owner,
    get_pending_tasks,
    get_pending_olpns,
    get_unloaded_olpns,
    get_unwaved_orders,
    get_idle_users,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response model (shared — tools always return a dict)
# ---------------------------------------------------------------------------
class ToolResponse(BaseModel):
    model_config = {"extra": "allow"}
    status: str


# ---------------------------------------------------------------------------
# Task endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/task/{task_id}",
    summary="Who is working a given pick task?",
    response_model=ToolResponse,
)
def api_get_task_owner(task_id: str):
    """
    Returns the picker assigned to **task_id** along with their current status
    and the shipment it belongs to.

    Example: `/tools/task/TSK500101`
    """
    return get_task_owner(task_id)


# ---------------------------------------------------------------------------
# Shipment — tasks
# ---------------------------------------------------------------------------
@router.get(
    "/shipment/{shipment_id}/tasks",
    summary="List pending / in-progress tasks for a shipment",
    response_model=ToolResponse,
)
def api_get_pending_tasks(shipment_id: str):
    """
    Returns all tasks that are **not yet completed** for the given shipment/truck.

    Example: `/tools/shipment/SHP10001/tasks`
    """
    return get_pending_tasks(shipment_id)


# ---------------------------------------------------------------------------
# Shipment — OLPNs
# ---------------------------------------------------------------------------
@router.get(
    "/shipment/{shipment_id}/olpns/pending",
    summary="List OLPNs not yet picked for a shipment",
    response_model=ToolResponse,
)
def api_get_pending_olpns(shipment_id: str):
    """
    Returns cartons/pallets (OLPNs) that are still in **pending** status
    (not yet picked by any picker).

    Example: `/tools/shipment/SHP10001/olpns/pending`
    """
    return get_pending_olpns(shipment_id)


@router.get(
    "/shipment/{shipment_id}/olpns/unloaded",
    summary="List OLPNs not yet loaded onto the truck",
    response_model=ToolResponse,
)
def api_get_unloaded_olpns(shipment_id: str):
    """
    Returns cartons/pallets that have been picked but **not yet loaded** onto
    the truck (status ≠ 'loaded').

    Example: `/tools/shipment/SHP10001/olpns/unloaded`
    """
    return get_unloaded_olpns(shipment_id)


# ---------------------------------------------------------------------------
# Shipment — orders
# ---------------------------------------------------------------------------
@router.get(
    "/shipment/{shipment_id}/orders/unwaved",
    summary="List orders not yet waved for a shipment",
    response_model=ToolResponse,
)
def api_get_unwaved_orders(shipment_id: str):
    """
    Returns customer orders that have **not yet been released/waved** for picking.

    Example: `/tools/shipment/SHP10001/orders/unwaved`
    """
    return get_unwaved_orders(shipment_id)


# ---------------------------------------------------------------------------
# Users — idle pickers
# ---------------------------------------------------------------------------
@router.get(
    "/users/idle",
    summary="Find pickers who are clocked in but out of work",
    response_model=ToolResponse,
)
def api_get_idle_users(
    site_id: str = Query(default="", description="Site code e.g. SITE01, or blank for all sites"),
):
    """
    Returns warehouse pickers who are currently clocked in for a shift but have
    **no pending or in-progress task** assigned to them.

    Example: `/tools/users/idle?site_id=SITE01`
    """
    return get_idle_users(site_id)
