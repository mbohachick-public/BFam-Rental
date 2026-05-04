"""Shared pytest fixtures for backend API integration tests.

Uses a mock Supabase client so tests run without a live database.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fake in-memory "database" tables
# ---------------------------------------------------------------------------

class FakeTable:
    """Minimal emulation of Supabase .table() chained queries for testing."""

    def __init__(self, store: dict[str, list[dict]]):
        self._store = store
        self._table: str = ""
        self._chain: list[tuple[str, Any]] = []

    def _reset(self, table: str) -> "FakeTable":
        ft = FakeTable(self._store)
        ft._table = table
        ft._chain = []
        return ft

    # --- Chaining methods ---

    def select(self, *args: Any, **kwargs: Any) -> "FakeTable":
        self._chain.append(("select", args))
        return self

    def insert(self, data: dict | list[dict], **kwargs: Any) -> "FakeTable":
        self._chain.append(("insert", data))
        return self

    def update(self, data: dict) -> "FakeTable":
        self._chain.append(("update", data))
        return self

    def upsert(self, data: list[dict], **kwargs: Any) -> "FakeTable":
        self._chain.append(("upsert", data))
        return self

    def delete(self) -> "FakeTable":
        self._chain.append(("delete", None))
        return self

    def eq(self, col: str, val: Any) -> "FakeTable":
        self._chain.append(("eq", (col, val)))
        return self

    def in_(self, col: str, vals: list) -> "FakeTable":
        self._chain.append(("in_", (col, vals)))
        return self

    def gte(self, col: str, val: Any) -> "FakeTable":
        self._chain.append(("gte", (col, val)))
        return self

    def lte(self, col: str, val: Any) -> "FakeTable":
        self._chain.append(("lte", (col, val)))
        return self

    def order(self, col: str, desc: bool = False, **kwargs: Any) -> "FakeTable":
        self._chain.append(("order", (col, desc)))
        return self

    def limit(self, n: int) -> "FakeTable":
        self._chain.append(("limit", n))
        return self

    # --- Execute ---

    def execute(self) -> MagicMock:
        ops = {op[0] for op in self._chain}
        rows = list(self._store.get(self._table, []))

        if "insert" in ops:
            return self._exec_insert()
        if "update" in ops:
            return self._exec_update(rows)
        if "upsert" in ops:
            return self._exec_upsert()
        if "delete" in ops:
            return self._exec_delete(rows)
        # SELECT
        return self._exec_select(rows)

    def _apply_filters(self, rows: list[dict]) -> list[dict]:
        result = rows
        for op, arg in self._chain:
            if op == "eq":
                col, val = arg
                result = [r for r in result if str(r.get(col)) == str(val)]
            elif op == "in_":
                col, vals = arg
                svals = {str(v) for v in vals}
                result = [r for r in result if str(r.get(col)) in svals]
            elif op == "gte":
                col, val = arg
                result = [r for r in result if str(r.get(col, "")) >= str(val)]
            elif op == "lte":
                col, val = arg
                result = [r for r in result if str(r.get(col, "")) <= str(val)]
        return result

    def _apply_order_limit(self, rows: list[dict]) -> list[dict]:
        for op, arg in self._chain:
            if op == "order":
                col, desc_ = arg
                rows = sorted(rows, key=lambda r: str(r.get(col, "")), reverse=desc_)
        for op, arg in self._chain:
            if op == "limit":
                rows = rows[: arg]
        return rows

    def _exec_select(self, rows: list[dict]) -> MagicMock:
        filtered = self._apply_filters(rows)
        filtered = self._apply_order_limit(filtered)

        # Handle column selection
        select_cols = None
        for op, arg in self._chain:
            if op == "select" and arg:
                cols_str = arg[0] if isinstance(arg[0], str) else "*"
                if cols_str != "*":
                    select_cols = [c.strip() for c in cols_str.split(",")]
                break

        if select_cols:
            filtered = [{k: r.get(k) for k in select_cols if k in r} for r in filtered]

        resp = MagicMock()
        resp.data = deepcopy(filtered)
        return resp

    def _exec_insert(self) -> MagicMock:
        for op, arg in self._chain:
            if op == "insert":
                data = deepcopy(arg)
                if "id" not in data:
                    data["id"] = str(uuid.uuid4())
                if "created_at" not in data:
                    data["created_at"] = datetime.now(timezone.utc).isoformat()
                self._store.setdefault(self._table, []).append(data)
                resp = MagicMock()
                resp.data = [deepcopy(data)]
                return resp
        resp = MagicMock()
        resp.data = []
        return resp

    def _exec_update(self, rows: list[dict]) -> MagicMock:
        filtered = self._apply_filters(rows)
        update_data = {}
        for op, arg in self._chain:
            if op == "update":
                update_data = arg
                break
        for row in filtered:
            row.update(update_data)
        resp = MagicMock()
        resp.data = deepcopy(filtered)
        return resp

    def _exec_upsert(self) -> MagicMock:
        for op, arg in self._chain:
            if op == "upsert":
                for record in arg:
                    table_rows = self._store.setdefault(self._table, [])
                    # Simple PK-based upsert
                    found = False
                    for existing in table_rows:
                        # item_day_status uses composite key (rows have no `id`)
                        if self._table == "item_day_status":
                            if (
                                existing.get("item_id") == record.get("item_id")
                                and existing.get("day") == record.get("day")
                            ):
                                existing.update(record)
                                found = True
                                break
                            continue
                        rid = record.get("id")
                        if rid is not None and existing.get("id") == rid:
                            existing.update(record)
                            found = True
                            break
                    if not found:
                        row = deepcopy(record)
                        if "id" not in row and self._table != "item_day_status":
                            row["id"] = str(uuid.uuid4())
                        table_rows.append(row)
                resp = MagicMock()
                resp.data = deepcopy(arg)
                return resp
        resp = MagicMock()
        resp.data = []
        return resp

    def _exec_delete(self, rows: list[dict]) -> MagicMock:
        filtered = self._apply_filters(rows)
        ids_to_remove = {id(r) for r in filtered}
        table_rows = self._store.get(self._table, [])
        self._store[self._table] = [r for r in table_rows if id(r) not in ids_to_remove]
        resp = MagicMock()
        resp.data = deepcopy(filtered)
        return resp


class FakeStorage:
    """Minimal mock for Supabase storage (does nothing but doesn't crash)."""

    def __init__(self):
        self._files: dict[str, bytes] = {}

    def from_(self, bucket: str):
        return self

    def upload(self, path: str, data: bytes, file_options: dict | None = None):
        self._files[path] = data

    def remove(self, paths: list[str]):
        for p in paths:
            self._files.pop(p, None)

    def create_signed_url(self, path: str, expires_in: int = 3600):
        return {"signedURL": f"https://fake-storage/{path}?token=test"}

    def create_signed_upload_url(self, path: str, options=None):
        token = "fake-upload-token"
        url = f"https://fake-upload.example/{path}?token={token}"
        return {"signed_url": url, "signedUrl": url, "token": token, "path": path}

    def exists(self, path: str) -> bool:
        return path in self._files

    def download(self, path: str, options=None, query_params=None) -> bytes:
        return self._files.get(path, b"")

    def list(self, path: str | None = None, options=None):
        prefix = (path or "").rstrip("/")
        names: list[str] = []
        for key in self._files:
            if prefix and key.startswith(prefix + "/"):
                rest = key[len(prefix) + 1 :]
                if "/" not in rest:
                    names.append(rest)
            elif not prefix and "/" in key:
                continue
        return [{"name": n} for n in sorted(names)]


def make_fake_client(store: dict[str, list[dict]]) -> MagicMock:
    """Build a MagicMock that behaves like a Supabase Client for our routes."""
    client = MagicMock()
    fake_table = FakeTable(store)
    client.table = lambda name: fake_table._reset(name)
    client.storage = FakeStorage()
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_store() -> dict[str, list[dict]]:
    """Shared mutable in-memory store used by the fake Supabase client."""
    return defaultdict(list)


@pytest.fixture()
def fake_client(db_store):
    return make_fake_client(db_store)


def _make_fake_settings():
    s = MagicMock()
    s.supabase_url = "https://test.supabase.co"
    s.supabase_service_role_key = "test-key"
    s.cors_origin_list = ["http://localhost:5173"]
    s.booking_documents_storage = "local"
    s.booking_documents_local_dir = "/tmp/bfam-test-booking"
    s.item_images_storage = "local"
    s.item_images_local_dir = "/tmp/bfam-test-images"
    s.api_public_url = "http://127.0.0.1:8000"
    s.smtp_host = ""
    s.smtp_port = 587
    s.smtp_user = ""
    s.smtp_password = ""
    s.smtp_from = ""
    s.smtp_use_tls = True
    s.auth0_domain = ""
    s.auth0_audience = ""
    s.auth0_admin_roles = "admin"
    s.auth0_admin_roles_claim = ""
    s.auth0_admin_emails = ""
    s.auth0_admin_subs = ""
    s.sales_tax_rate_url = ""
    s.sales_tax_fallback_percent = "4.225"
    s.sales_tax_default_postal_code = "64089"
    s.sales_tax_http_timeout_sec = 8.0
    s.frontend_public_url = "http://localhost:5173"
    s.app_base_url = ""
    s.stripe_secret_key = ""
    s.stripe_webhook_secret = ""
    s.stripe_checkout_include_deposit = True
    s.public_app_base_url = MagicMock(return_value="http://localhost:5173")
    s.google_maps_api_key = ""
    s.google_maps_http_timeout_sec = 12.0
    s.stripe_publishable_key = ""
    s.damage_waiver_per_day_usd = "15.00"
    return s


@pytest.fixture(autouse=True)
def _seed_delivery_settings_table(db_store):
    """Singleton row so admin PATCH and load_delivery_settings hit the fake DB."""
    db_store["delivery_settings"] = [
        {
            "id": 1,
            "enabled": False,
            "origin_address": "",
            "price_per_mile": 0.0,
            "minimum_fee": 0.0,
            "free_miles": 0.0,
            "max_delivery_miles": None,
        }
    ]


@pytest.fixture()
def fake_settings():
    return _make_fake_settings()


@pytest.fixture()
def client(fake_client, fake_settings):
    """FastAPI TestClient with the Supabase dependency overridden."""
    from app.main import app
    from app.deps import get_supabase_client

    def _override():
        yield fake_client

    app.dependency_overrides[get_supabase_client] = _override

    # Patch get_settings everywhere it's imported
    with (
        patch("app.config.get_settings", return_value=fake_settings),
        patch("app.deps.get_settings", return_value=fake_settings),
        patch("app.routers.admin.get_settings", return_value=fake_settings),
        patch("app.routers.booking_requests.get_settings", return_value=fake_settings),
        patch("app.routers.items.get_settings", return_value=fake_settings),
        patch("app.routers.stripe_webhook.get_settings", return_value=fake_settings),
    ):
        with TestClient(app) as tc:
            yield tc

    app.dependency_overrides.clear()


@pytest.fixture()
def admin_headers(fake_settings, monkeypatch) -> dict[str, str]:
    """Bearer admin auth: enables Auth0 settings on the shared fake settings and stubs JWT verify."""
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.test/"
    fake_settings.auth0_admin_roles = "admin"
    fake_settings.auth0_admin_roles_claim = ""
    fake_settings.auth0_admin_emails = ""
    fake_settings.auth0_admin_subs = ""

    def _verify(_token: str, *, domain: str, audience: str, domain_aliases: str = "") -> dict:
        return {"sub": "auth0|pytest-admin", "permissions": ["admin"]}

    monkeypatch.setattr("app.deps.verify_auth0_access_token", _verify)
    return {"Authorization": "Bearer pytest-admin-access-token"}


# ---------------------------------------------------------------------------
# Helper to seed an item via the fake store
# ---------------------------------------------------------------------------

@pytest.fixture()
def seed_item(db_store):
    def _seed(
        *,
        title: str = "Test Item",
        active: bool = True,
        towable: bool = False,
        cost_per_day: float = 50.0,
        minimum_day_rental: int = 1,
        deposit_amount: float = 100.0,
    ) -> dict:
        item_id = str(uuid.uuid4())
        row = {
            "id": item_id,
            "title": title,
            "description": "test desc",
            "category": "general",
            "cost_per_day": cost_per_day,
            "minimum_day_rental": minimum_day_rental,
            "deposit_amount": deposit_amount,
            "user_requirements": "",
            "towable": towable,
            "delivery_available": True,
            "active": active,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        db_store["items"].append(row)
        return row

    return _seed


@pytest.fixture()
def seed_day_statuses(db_store):
    def _seed(item_id: str, days: list[tuple[str, str]]):
        for day_str, status in days:
            db_store["item_day_status"].append(
                {"item_id": item_id, "day": day_str, "status": status}
            )
    return _seed
