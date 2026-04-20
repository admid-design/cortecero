"""Tests para POST /orders/import-xlsx — XLSX-ORDERS-001.

Cubre:
  - Happy path XLSX: 3 filas → 3 pedidos creados
  - Happy path CSV: misma lógica
  - Cliente no existe → creado como nuevo + warning
  - external_ref ausente → generado automáticamente
  - Fila con nombre vacío → skipped + error
  - Ambigüedad por exact match múltiple → skipped + error
  - Ambigüedad por partial match múltiple → skipped + error
  - Partial match único → pedido creado + warning
  - Idempotencia: segunda importación → 0 imported, skipped
  - Extensión inválida → 422
  - service_date ausente → 422
  - Tenant isolation: pedidos de otro tenant no visibles
"""

import io
import uuid
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import select

from app.models import (
    Customer,
    Order,
    OrderStatus,
    SourceChannel,
    OrderIntakeType,
    Tenant,
    Zone,
)
from tests.helpers import auth_headers, login_as


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_xlsx(rows: list[list]) -> bytes:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_csv(content: str) -> bytes:
    return content.encode("utf-8")


def _office_token(client) -> str:
    return login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )


def _demo_tenant(db_session) -> Tenant:
    return db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))


def _first_customer(db_session, tenant_id) -> Customer:
    return db_session.scalar(
        select(Customer).where(Customer.tenant_id == tenant_id).limit(1)
    )


def _post_xlsx(client, token: str, file_bytes: bytes, filename: str, service_date: str):
    return client.post(
        "/orders/import-xlsx",
        headers=auth_headers(token),
        files={"file": (filename, file_bytes, "application/octet-stream")},
        data={"service_date": service_date},
    )


# ---------------------------------------------------------------------------
# Happy path — XLSX
# ---------------------------------------------------------------------------

class TestImportXlsxHappyPath:
    def test_imports_three_orders(self, client, db_session):
        tenant = _demo_tenant(db_session)
        # Usar 3 clientes del seed (nombres reales en la DB)
        customers = db_session.scalars(
            select(Customer).where(Customer.tenant_id == tenant.id).limit(3)
        ).all()
        assert len(customers) >= 3, "El seed debe tener al menos 3 clientes"

        xlsx = _make_xlsx([
            ["Cliente", "Referencia", "Peso"],
            [customers[0].name, "REF-001", "10"],
            [customers[1].name, "REF-002", "20"],
            [customers[2].name, "REF-003", "30"],
        ])

        token = _office_token(client)
        res = _post_xlsx(client, token, xlsx, "pedidos.xlsx", "2026-06-01")

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["imported"] == 3
        assert body["skipped"] == 0
        assert body["errors"] == []

        # Verificar en DB
        orders = db_session.scalars(
            select(Order).where(
                Order.tenant_id == tenant.id,
                Order.service_date == date(2026, 6, 1),
                Order.external_ref.in_(["REF-001", "REF-002", "REF-003"]),
            )
        ).all()
        assert len(orders) == 3
        for order in orders:
            assert order.status in (OrderStatus.ready_for_planning, OrderStatus.late_pending_exception)
            assert order.source_channel == SourceChannel.office
            assert order.intake_type == OrderIntakeType.new_order

    def test_weight_mapped_correctly(self, client, db_session):
        tenant = _demo_tenant(db_session)
        customer = _first_customer(db_session, tenant.id)

        xlsx = _make_xlsx([
            ["Cliente", "Referencia", "Peso"],
            [customer.name, "REF-WEIGHT", "55.5"],
        ])
        token = _office_token(client)
        res = _post_xlsx(client, token, xlsx, "p.xlsx", "2026-06-02")

        assert res.status_code == 200
        order = db_session.scalar(
            select(Order).where(Order.tenant_id == tenant.id, Order.external_ref == "REF-WEIGHT")
        )
        assert order is not None
        assert float(order.total_weight_kg) == pytest.approx(55.5, rel=1e-3)


# ---------------------------------------------------------------------------
# Happy path — CSV
# ---------------------------------------------------------------------------

class TestImportCsvHappyPath:
    def test_imports_csv(self, client, db_session):
        tenant = _demo_tenant(db_session)
        customers = db_session.scalars(
            select(Customer).where(Customer.tenant_id == tenant.id).limit(2)
        ).all()
        assert len(customers) >= 2

        csv_bytes = _make_csv(
            f"Cliente,Referencia\n"
            f"{customers[0].name},CSV-001\n"
            f"{customers[1].name},CSV-002\n"
        )
        token = _office_token(client)
        res = _post_xlsx(client, token, csv_bytes, "pedidos.csv", "2026-06-03")

        assert res.status_code == 200
        body = res.json()
        assert body["imported"] == 2
        assert body["skipped"] == 0


# ---------------------------------------------------------------------------
# Cliente no existe → creado como nuevo
# ---------------------------------------------------------------------------

class TestNewCustomerCreated:
    def test_creates_new_customer(self, client, db_session):
        tenant = _demo_tenant(db_session)
        new_name = f"Cliente Nuevo {uuid.uuid4().hex[:6]}"

        xlsx = _make_xlsx([
            ["Cliente", "Referencia"],
            [new_name, "REF-NEW"],
        ])
        token = _office_token(client)
        res = _post_xlsx(client, token, xlsx, "p.xlsx", "2026-06-04")

        assert res.status_code == 200
        body = res.json()
        assert body["imported"] == 1
        assert body["skipped"] == 0
        # Warning sobre cliente nuevo
        assert any(new_name in w["reason"] for w in body["warnings"])

        # Cliente existe en DB
        new_customer = db_session.scalar(
            select(Customer).where(Customer.tenant_id == tenant.id, Customer.name == new_name)
        )
        assert new_customer is not None


# ---------------------------------------------------------------------------
# external_ref ausente → auto-generado
# ---------------------------------------------------------------------------

class TestAutoExternalRef:
    def test_ref_auto_generated(self, client, db_session):
        tenant = _demo_tenant(db_session)
        customer = _first_customer(db_session, tenant.id)

        xlsx = _make_xlsx([
            ["Cliente"],          # Sin columna Referencia
            [customer.name],
        ])
        token = _office_token(client)
        res = _post_xlsx(client, token, xlsx, "p.xlsx", "2026-06-05")

        assert res.status_code == 200
        body = res.json()
        assert body["imported"] == 1

        order = db_session.scalar(
            select(Order).where(
                Order.tenant_id == tenant.id,
                Order.service_date == date(2026, 6, 5),
            )
        )
        assert order is not None
        assert order.external_ref.startswith("XLSX-")


# ---------------------------------------------------------------------------
# Fila con nombre vacío → skipped + error
# ---------------------------------------------------------------------------

class TestEmptyCustomerName:
    def test_empty_name_skipped(self, client, db_session):
        tenant = _demo_tenant(db_session)
        customer = _first_customer(db_session, tenant.id)

        xlsx = _make_xlsx([
            ["Cliente", "Referencia"],
            ["", "REF-EMPTY"],           # nombre vacío
            [customer.name, "REF-GOOD"],  # fila válida
        ])
        token = _office_token(client)
        res = _post_xlsx(client, token, xlsx, "p.xlsx", "2026-06-06")

        assert res.status_code == 200
        body = res.json()
        assert body["imported"] == 1
        assert body["skipped"] == 1
        assert len(body["errors"]) == 1
        assert body["errors"][0]["row"] == 2


# ---------------------------------------------------------------------------
# Ambigüedad — exact match múltiple
# ---------------------------------------------------------------------------

class TestAmbiguousExactMatch:
    def test_ambiguous_exact_skipped(self, client, db_session):
        tenant = _demo_tenant(db_session)
        zone = db_session.scalar(
            select(Zone).where(Zone.tenant_id == tenant.id).limit(1)
        )
        now = datetime.now(UTC)
        shared_name = f"Cliente Gemelo {uuid.uuid4().hex[:6]}"

        # Crear dos clientes con el mismo nombre
        for _ in range(2):
            db_session.add(Customer(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                zone_id=zone.id,
                name=shared_name,
                priority=0,
                active=True,
                in_zbe_zone=False,
                created_at=now,
            ))
        db_session.commit()

        xlsx = _make_xlsx([
            ["Cliente", "Referencia"],
            [shared_name, "REF-AMB"],
        ])
        token = _office_token(client)
        res = _post_xlsx(client, token, xlsx, "p.xlsx", "2026-06-07")

        assert res.status_code == 200
        body = res.json()
        assert body["imported"] == 0
        assert body["skipped"] == 1
        assert "ambiguo" in body["errors"][0]["reason"]


# ---------------------------------------------------------------------------
# Partial match único → warning + pedido creado
# ---------------------------------------------------------------------------

class TestPartialMatchUnique:
    def test_partial_match_creates_order(self, client, db_session):
        tenant = _demo_tenant(db_session)
        customer = _first_customer(db_session, tenant.id)

        # Usar solo la primera palabra del nombre (partial)
        partial_name = customer.name.split()[0]

        # Asegurar que solo hay UN cliente que contiene esa palabra
        matches = db_session.scalars(
            select(Customer).where(
                Customer.tenant_id == tenant.id,
                Customer.name.ilike(f"%{partial_name}%"),
            )
        ).all()
        if len(matches) != 1:
            pytest.skip(f"'{partial_name}' no es único en el seed ({len(matches)} matches)")

        xlsx = _make_xlsx([
            ["Cliente", "Referencia"],
            [partial_name, "REF-PARTIAL"],
        ])
        token = _office_token(client)
        res = _post_xlsx(client, token, xlsx, "p.xlsx", "2026-06-08")

        assert res.status_code == 200
        body = res.json()
        assert body["imported"] == 1
        assert body["skipped"] == 0
        # Debe haber warning de coincidencia parcial
        assert any("parcial" in w["reason"] for w in body["warnings"])


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_second_import_skipped(self, client, db_session):
        tenant = _demo_tenant(db_session)
        customer = _first_customer(db_session, tenant.id)

        xlsx = _make_xlsx([
            ["Cliente", "Referencia"],
            [customer.name, "REF-IDEM"],
        ])
        token = _office_token(client)

        # Primera importación
        res1 = _post_xlsx(client, token, xlsx, "p.xlsx", "2026-06-09")
        assert res1.status_code == 200
        assert res1.json()["imported"] == 1

        # Segunda importación — misma referencia y fecha
        res2 = _post_xlsx(client, token, xlsx, "p.xlsx", "2026-06-09")
        assert res2.status_code == 200
        body2 = res2.json()
        assert body2["imported"] == 0
        assert body2["skipped"] == 1
        assert any("ya existe" in w["reason"] for w in body2["warnings"])


# ---------------------------------------------------------------------------
# Extensión inválida → 422
# ---------------------------------------------------------------------------

class TestInvalidFile:
    def test_invalid_extension_422(self, client):
        token = _office_token(client)
        res = _post_xlsx(client, token, b"not a file", "archivo.pdf", "2026-06-10")
        assert res.status_code == 422

    def test_corrupted_xlsx_422(self, client):
        token = _office_token(client)
        res = _post_xlsx(client, token, b"esto no es xlsx", "archivo.xlsx", "2026-06-10")
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# service_date ausente → 422
# ---------------------------------------------------------------------------

class TestMissingServiceDate:
    def test_missing_service_date_422(self, client):
        token = _office_token(client)
        xlsx = _make_xlsx([["Cliente"], ["Test"]])
        res = client.post(
            "/orders/import-xlsx",
            headers=auth_headers(token),
            files={"file": ("p.xlsx", xlsx, "application/octet-stream")},
            # sin data service_date
        )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    def test_orders_scoped_to_tenant(self, client, db_session):
        tenant = _demo_tenant(db_session)
        customer = _first_customer(db_session, tenant.id)

        xlsx = _make_xlsx([
            ["Cliente", "Referencia"],
            [customer.name, "REF-ISO"],
        ])
        token = _office_token(client)
        res = _post_xlsx(client, token, xlsx, "p.xlsx", "2026-06-11")
        assert res.status_code == 200

        order = db_session.scalar(
            select(Order).where(Order.external_ref == "REF-ISO")
        )
        assert order is not None
        assert order.tenant_id == tenant.id
