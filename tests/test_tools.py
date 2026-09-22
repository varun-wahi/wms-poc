"""Run against the local seeded DB:  pytest -q   (expected values come from seed.sql)"""
from wms_agent import tools as t


def test_task_owner():
    r = t.get_task_owner("tsk500101")  # also checks case-normalisation
    assert r["status"] == "success" and r["assigned_to"] == "Karthik Rao"

def test_task_not_found():
    assert t.get_task_owner("TSK000000")["status"] == "not_found"

def test_pending_tasks():
    r = t.get_pending_tasks("SHP10001")
    assert r["count"] == 8 and set(r["by_status"]) == {"pending", "in_progress"}

def test_pending_olpns():
    assert t.get_pending_olpns("SHP10001")["count"] == 21

def test_unloaded_olpns():
    assert t.get_unloaded_olpns("SHP10001")["count"] == 32
    assert t.get_unloaded_olpns("SHP10005")["count"] == 0      # staged truck

def test_unwaved_orders():
    assert t.get_unwaved_orders("SHP10001")["count"] == 6
    assert t.get_unwaved_orders("SHP10004")["count"] == 0

def test_unknown_shipment_and_bad_input():
    assert t.get_pending_tasks("SHP99999")["status"] == "not_found"
    assert t.get_pending_tasks("x'; DROP TABLE tasks;--")["status"] == "invalid_input"

def test_idle_users():
    names = {u["user_name"] for u in t.get_idle_users("")["users"]}
    assert {"Karthik Rao", "Sunita Das"} <= names and "Imran Khan" not in names

def test_read_only_enforced():
    import pytest, psycopg
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        t._query("UPDATE users SET user_name='x'")
