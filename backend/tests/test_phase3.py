"""
Phase 3 tests — verify the database layer matches the approved ERD.

Tests:
1. Schema creation (all 6 tables exist)
2. Foreign key constraints enforced
3. Seed data populates correctly
4. Query helpers return expected shapes
5. Insert + update operations work
6. No policy_id column in audit_logs (ERD compliance)

Run with:  python -m pytest tests/test_phase3.py -v
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from optiroute import database as db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def use_test_db(tmp_path, monkeypatch):
    """Point the database module at a temp directory so tests don't touch real data."""
    monkeypatch.setattr(db, "_DB_DIR", tmp_path)
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "test_optiroute.db")


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def run(coro):
    """Shorthand to run an async function synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSchemaCreation:
    """Verify all 6 ERD tables are created correctly."""

    def test_init_db_creates_tables(self):
        run(db.init_db())
        
        async def check():
            conn = await db.get_connection()
            try:
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [row["name"] for row in await cursor.fetchall()]
                return tables
            finally:
                await conn.close()

        tables = run(check())
        expected = ["ai_models", "audit_logs", "routing_policies", "semantic_cache", "users", "workflows"]
        assert sorted(tables) == sorted(expected), f"Expected tables {expected}, got {tables}"

    def test_audit_logs_has_no_policy_id(self):
        """ERD compliance: audit_logs must NOT have a policy_id column."""
        run(db.init_db())

        async def check():
            conn = await db.get_connection()
            try:
                cursor = await conn.execute("PRAGMA table_info(audit_logs)")
                columns = [row["name"] for row in await cursor.fetchall()]
                return columns
            finally:
                await conn.close()

        columns = run(check())
        assert "policy_id" not in columns, f"audit_logs should not have policy_id, but columns are: {columns}"

    def test_audit_logs_columns_match_erd(self):
        """Verify the exact column set matches the ERD."""
        run(db.init_db())

        async def check():
            conn = await db.get_connection()
            try:
                cursor = await conn.execute("PRAGMA table_info(audit_logs)")
                columns = [row["name"] for row in await cursor.fetchall()]
                return columns
            finally:
                await conn.close()

        columns = run(check())
        expected = ["log_id", "workflow_id", "model_id", "cache_id", "status_code", "latency_ms", "total_cost", "created_at"]
        assert columns == expected


class TestSeedData:
    """Verify seed data populates the tables."""

    def test_ai_models_seeded(self):
        run(db.init_db())
        models = run(db.get_all_ai_models())
        assert len(models) == 3
        model_ids = {m["model_id"] for m in models}
        assert model_ids == {"gpt-4o-mini", "gpt-4o", "gpt-4.1"}

    def test_workflows_seeded(self):
        run(db.init_db())
        workflows = run(db.get_all_workflows())
        assert len(workflows) == 4
        names = {w["workflow_name"] for w in workflows}
        assert "Workflow A: High-Complexity Model Usage" in names

    def test_policies_seeded(self):
        run(db.init_db())
        policies = run(db.get_all_policies())
        assert len(policies) == 8
        # allowed_models should be deserialized to list
        for p in policies:
            assert isinstance(p["allowed_models"], list)

    def test_cache_seeded(self):
        run(db.init_db())
        entries = run(db.get_all_cache_entries())
        assert len(entries) == 5

    def test_audit_logs_seeded(self):
        run(db.init_db())
        logs = run(db.get_recent_audit_logs())
        assert len(logs) == 5

    def test_models_all_healthy(self):
        run(db.init_db())
        models = run(db.get_all_ai_models())
        for m in models:
            assert m["is_healthy"] == 1


class TestQueryHelpers:
    """Verify the async query helpers return expected shapes."""

    def test_overview_stats(self):
        run(db.init_db())
        stats = run(db.get_overview_stats())
        assert "total_requests" in stats
        assert "total_cost" in stats
        assert "cache_hit_rate" in stats
        assert "active_failovers" in stats
        assert stats["total_requests"] == 5

    def test_budget_summary(self):
        run(db.init_db())
        budgets = run(db.get_budget_summary())
        assert len(budgets) == 4
        for b in budgets:
            assert "workflow_name" in b
            assert "current_spend" in b


class TestMutations:
    """Verify insert/update operations."""

    def test_insert_audit_log(self):
        run(db.init_db())
        log_id = run(db.insert_audit_log(
            workflow_id="wf-a",
            model_id="gpt-4o-mini",
            cache_id=None,
            status_code=200,
            latency_ms=123.4,
            total_cost=0.001,
        ))
        assert log_id.startswith("log-")
        logs = run(db.get_recent_audit_logs())
        assert len(logs) == 6  # 5 seeded + 1 new

    def test_update_workflow_spend(self):
        run(db.init_db())
        run(db.update_workflow_spend("wf-a", 100.0))
        workflows = run(db.get_all_workflows())
        wf_a = next(w for w in workflows if w["workflow_id"] == "wf-a")
        assert wf_a["current_spend"] == 1500.0  # 1400 + 100

    def test_set_model_health(self):
        run(db.init_db())
        run(db.set_model_health("gpt-4o-mini", False))
        healthy = run(db.get_model_health("gpt-4o-mini"))
        assert healthy is False

        run(db.set_model_health("gpt-4o-mini", True))
        healthy = run(db.get_model_health("gpt-4o-mini"))
        assert healthy is True

    def test_insert_and_increment_cache(self):
        run(db.init_db())
        run(db.insert_cache_entry(
            cache_id="cache-test-1",
            prompt_hash="hash:TEST",
            cached_response='{"content":"test response"}',
            model_id="gpt-4o-mini",
        ))
        run(db.increment_cache_hit("cache-test-1"))
        run(db.increment_cache_hit("cache-test-1"))

        entries = run(db.get_all_cache_entries())
        test_entry = next(e for e in entries if e["cache_id"] == "cache-test-1")
        assert test_entry["hit_count"] == 2

    def test_idempotent_init(self):
        """Calling init_db() twice should not fail or duplicate data."""
        run(db.init_db())
        run(db.init_db())
        models = run(db.get_all_ai_models())
        assert len(models) == 3  # Still 3, not 6
