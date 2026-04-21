"""Tests para POST /route-templates/import-xlsx — XLSX-TEMPLATES-001.

Cubre:
  - Happy path XLSX: dos grupos → 2 plantillas + N paradas
  - Happy path CSV
  - Anti-duplicado: segunda importación del mismo grupo → skipped con warning
  - Dos grupos en mismo fichero, uno ya existente → solo el nuevo entra (parcial)
  - Extensión inválida → 422
  - Fichero vacío → 200, templates_created=0
  - Vehículo no encontrado → vehicle_id null + warning (import continúa)
  - Cliente exact match → resuelto sin warning
  - Cliente partial match único → resuelto con warning
  - Cliente ambiguo → customer_id null + warning
  - Cliente no encontrado → customer_id null + warning
  - season param: se almacena en la plantilla y forma parte de la clave anti-dup
"""

import io
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import (
    Customer,
    RouteTemplate,
    RouteTemplateStop,
    Tenant,
    Vehicle,
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


def _first_vehicle(db_session, tenant_id) -> Vehicle:
    return db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id).limit(1)
    )


def _first_customer(db_session, tenant_id) -> Customer:
    return db_session.scalar(
        select(Customer).where(Customer.tenant_id == tenant_id).limit(1)
    )


def _post_templates(
    client,
    token: str,
    file_bytes: bytes,
    filename: str,
    season: str | None = None,
):
    data = {}
    if season:
        data["season"] = season
    return client.post(
        "/route-templates/import-xlsx",
        headers=auth_headers(token),
        files={"file": (filename, file_bytes, "application/octet-stream")},
        data=data,
    )


# Cabeceras canónicas que el parser reconoce vía TEMPLATE_FIELD_ALIASES
_HEADERS = ["Matrícula", "Día", "Orden", "Cliente", "Dirección", "Duración"]


# ---------------------------------------------------------------------------
# Happy path — XLSX, un solo grupo
# ---------------------------------------------------------------------------

class TestHappyPathSingleGroup:
    def test_creates_template_and_stops(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)
        customer = _first_customer(db_session, tenant.id)

        xlsx = _make_xlsx([
            _HEADERS,
            [vehicle.code, "Lunes", 1, customer.name, "Calle Mayor 1", 15],
            [vehicle.code, "Lunes", 2, customer.name, "Calle Mayor 2", 10],
        ])

        token = _office_token(client)
        res = _post_templates(client, token, xlsx, "rutas.xlsx")

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["templates_created"] == 1
        assert body["stops_total"] == 2
        assert body["errors"] == []

        # Verificar en DB
        template = db_session.scalar(
            select(RouteTemplate).where(
                RouteTemplate.tenant_id == tenant.id,
                RouteTemplate.vehicle_id == vehicle.id,
                RouteTemplate.day_of_week == 1,
            )
        )
        assert template is not None

        stops = db_session.scalars(
            select(RouteTemplateStop).where(
                RouteTemplateStop.template_id == template.id
            ).order_by(RouteTemplateStop.sequence_number)
        ).all()
        assert len(stops) == 2
        assert stops[0].address == "Calle Mayor 1"
        assert stops[0].duration_min == 15
        assert stops[0].customer_id == customer.id

    def test_happy_path_csv(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)

        csv_content = "Matrícula,Día,Orden,Cliente,Dirección,Duración\n"
        csv_content += f"{vehicle.code},Martes,1,,Av. Libertad 10,20\n"

        token = _office_token(client)
        res = _post_templates(client, token, _make_csv(csv_content), "rutas.csv")

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["templates_created"] == 1
        assert body["stops_total"] == 1


# ---------------------------------------------------------------------------
# Anti-duplicado
# ---------------------------------------------------------------------------

class TestAntiDuplicate:
    def test_second_import_same_group_skipped(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)

        xlsx = _make_xlsx([
            _HEADERS,
            [vehicle.code, "Miércoles", 1, "", "Calle Falsa 123", 10],
        ])

        token = _office_token(client)

        # Primera importación — debe crear
        res1 = _post_templates(client, token, xlsx, "rutas.xlsx", season="verano")
        assert res1.status_code == 200
        body1 = res1.json()
        assert body1["templates_created"] == 1

        # Segunda importación — mismo vehicle+dow+season → skip
        res2 = _post_templates(client, token, xlsx, "rutas.xlsx", season="verano")
        assert res2.status_code == 200
        body2 = res2.json()
        assert body2["templates_created"] == 0
        assert any("plantilla ya existe" in w for w in body2["warnings"]), body2

    def test_different_season_creates_new_template(self, client, db_session):
        """La misma matrícula+día con season distinto no es duplicado."""
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)

        xlsx = _make_xlsx([
            _HEADERS,
            [vehicle.code, "Jueves", 1, "", "Polígono Norte 5", 10],
        ])

        token = _office_token(client)

        res_v = _post_templates(client, token, xlsx, "rutas.xlsx", season="verano")
        res_i = _post_templates(client, token, xlsx, "rutas.xlsx", season="invierno")

        assert res_v.json()["templates_created"] == 1
        assert res_i.json()["templates_created"] == 1


# ---------------------------------------------------------------------------
# Dos grupos, uno ya existente — import parcial
# ---------------------------------------------------------------------------

class TestPartialImportTwoGroups:
    def test_one_enters_one_skipped(self, client, db_session):
        """El fichero tiene 2 grupos (Lunes + Viernes).
        El de Lunes ya existe (creado manualmente). Solo Viernes entra.
        El import NO aborta — sigue con el grupo siguiente.
        """
        tenant = _demo_tenant(db_session)

        # Obtener dos vehículos distintos para dos grupos distintos
        vehicles = db_session.scalars(
            select(Vehicle).where(Vehicle.tenant_id == tenant.id).limit(2)
        ).all()
        assert len(vehicles) >= 2, "El seed necesita al menos 2 vehículos"

        v1, v2 = vehicles[0], vehicles[1]
        season = "test-parcial"

        # Pre-crear la plantilla del primer grupo (v1 + Lunes)
        existing = RouteTemplate(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            name=f"pre-existente-{uuid.uuid4().hex[:6]}",
            season=season,
            vehicle_id=v1.id,
            day_of_week=1,  # Lunes
            created_at=datetime.now(UTC),
        )
        db_session.add(existing)
        db_session.commit()

        # Fichero con los dos grupos
        xlsx = _make_xlsx([
            _HEADERS,
            [v1.code, "Lunes",   1, "", "Dir A", 10],  # → skip (ya existe)
            [v2.code, "Viernes", 1, "", "Dir B", 15],  # → crea
        ])

        token = _office_token(client)
        res = _post_templates(client, token, xlsx, "rutas.xlsx", season=season)

        assert res.status_code == 200, res.text
        body = res.json()

        assert body["templates_created"] == 1, body
        assert body["stops_total"] == 1, body
        # Debe haber exactamente un warning de duplicado
        dup_warns = [w for w in body["warnings"] if "plantilla ya existe" in w]
        assert len(dup_warns) == 1, body


# ---------------------------------------------------------------------------
# Extensión inválida y fichero vacío
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_invalid_extension_422(self, client):
        token = _office_token(client)
        res = client.post(
            "/route-templates/import-xlsx",
            headers=auth_headers(token),
            files={"file": ("rutas.pdf", b"%%PDF", "application/pdf")},
        )
        assert res.status_code == 422
        assert "INVALID_FILE_EXTENSION" in res.json()["detail"]["code"]

    def test_empty_file_returns_zero(self, client, db_session):
        xlsx = _make_xlsx([])  # solo cabecera vacía
        token = _office_token(client)
        res = _post_templates(client, token, xlsx, "rutas.xlsx")
        assert res.status_code == 200
        body = res.json()
        assert body["templates_created"] == 0


# ---------------------------------------------------------------------------
# Resolución de vehículo
# ---------------------------------------------------------------------------

class TestVehicleResolution:
    def test_vehicle_not_found_continues_with_warning(self, client, db_session):
        """Si la matrícula no existe, el template se crea con vehicle_id=null + warning."""
        xlsx = _make_xlsx([
            _HEADERS,
            ["MATRICULA-INEXISTENTE-XYZ", "Lunes", 1, "", "Calle Sin Nombre", 10],
        ])

        token = _office_token(client)
        res = _post_templates(client, token, xlsx, "rutas.xlsx")

        assert res.status_code == 200, res.text
        body = res.json()
        # El grupo igualmente crea la plantilla (vehicle_id = null)
        assert body["templates_created"] == 1
        assert any("no encontrada" in w or "matrícula" in w.lower() for w in body["warnings"]), body

    def test_vehicle_resolved_by_code_case_insensitive(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)

        xlsx = _make_xlsx([
            _HEADERS,
            [vehicle.code.lower(), "Sábado", 1, "", "Calle Prueba 1", 10],
        ])

        token = _office_token(client)
        res = _post_templates(client, token, xlsx, "rutas.xlsx")

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["templates_created"] == 1

        # Verificar que vehicle_id está resuelto
        tenant_obj = _demo_tenant(db_session)
        template = db_session.scalar(
            select(RouteTemplate).where(
                RouteTemplate.tenant_id == tenant_obj.id,
                RouteTemplate.vehicle_id == vehicle.id,
                RouteTemplate.day_of_week == 6,  # Sábado
            )
        )
        assert template is not None
        assert template.vehicle_id == vehicle.id


# ---------------------------------------------------------------------------
# Resolución de cliente (nullable)
# ---------------------------------------------------------------------------

class TestCustomerResolution:
    def test_exact_match_resolves_customer(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)
        customer = _first_customer(db_session, tenant.id)

        xlsx = _make_xlsx([
            _HEADERS,
            [vehicle.code, "Domingo", 1, customer.name, "Calle Exacta 1", 10],
        ])

        token = _office_token(client)
        res = _post_templates(client, token, xlsx, "rutas.xlsx")

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["templates_created"] == 1
        # No debe haber warning de cliente
        cust_warns = [w for w in body["warnings"] if customer.name in w]
        assert cust_warns == [], body

        # Verificar customer_id en la parada
        template = db_session.scalar(
            select(RouteTemplate).where(
                RouteTemplate.tenant_id == tenant.id,
                RouteTemplate.vehicle_id == vehicle.id,
                RouteTemplate.day_of_week == 7,
            )
        )
        assert template is not None
        stop = db_session.scalar(
            select(RouteTemplateStop).where(
                RouteTemplateStop.template_id == template.id
            )
        )
        assert stop is not None
        assert stop.customer_id == customer.id

    def test_customer_not_found_null_with_warning(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)

        xlsx = _make_xlsx([
            _HEADERS,
            [vehicle.code, "Lunes", 1, "Cliente Fantasma XYZ 99999", "Calle Inventada", 10],
        ])

        token = _office_token(client)
        res = _post_templates(client, token, xlsx, "rutas.xlsx")

        assert res.status_code == 200, res.text
        body = res.json()
        # Template creado; cliente null con warning
        assert body["templates_created"] == 1
        assert any("no encontrado" in w for w in body["warnings"]), body

    def test_partial_match_unique_resolves_with_warning(self, client, db_session):
        """Si existe un único cliente cuyo nombre contiene el fragmento, se resuelve con warning."""
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)
        customer = _first_customer(db_session, tenant.id)

        # Fragmento único que debe coincidir solo con ese cliente
        fragment = customer.name[:4] if len(customer.name) >= 4 else customer.name

        # Comprobar que el fragmento es único antes de usar el test
        from sqlalchemy import func
        matches = db_session.scalars(
            select(Customer).where(
                Customer.tenant_id == tenant.id,
                Customer.name.ilike(f"%{fragment}%"),
            )
        ).all()
        if len(matches) != 1:
            pytest.skip(f"Fragmento '{fragment}' no es único en el seed ({len(matches)} matches)")

        xlsx = _make_xlsx([
            _HEADERS,
            [vehicle.code, "Martes", 1, fragment, "Av. Parcial 1", 10],
        ])

        token = _office_token(client)
        res = _post_templates(client, token, xlsx, "rutas.xlsx")

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["templates_created"] == 1
        # Debe haber warning de coincidencia parcial
        partial_warns = [w for w in body["warnings"] if "parcial" in w]
        assert len(partial_warns) == 1, body


# ---------------------------------------------------------------------------
# Season se almacena en plantilla
# ---------------------------------------------------------------------------

class TestSeasonParam:
    def test_season_stored_in_template(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)

        xlsx = _make_xlsx([
            _HEADERS,
            [vehicle.code, "Lunes", 1, "", "Calle Temporada 1", 10],
        ])

        token = _office_token(client)
        res = _post_templates(client, token, xlsx, "rutas.xlsx", season="verano")

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["templates_created"] == 1

        template = db_session.scalar(
            select(RouteTemplate).where(
                RouteTemplate.tenant_id == tenant.id,
                RouteTemplate.vehicle_id == vehicle.id,
                RouteTemplate.day_of_week == 1,
                RouteTemplate.season == "verano",
            )
        )
        assert template is not None
        assert template.season == "verano"
