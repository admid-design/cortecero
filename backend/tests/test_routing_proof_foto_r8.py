"""
R8-POD-FOTO — Proof of Delivery: foto con Cloudflare R2

Cubre:
  - POST /stops/{id}/proof-upload-url  happy path → presigned URL + object_key
  - POST /stops/{id}/proof-upload-url  stop en estado incorrecto → 409
  - POST /stops/{id}/proof-upload-url  R2 no configurado → 503
  - PATCH /stops/{id}/proof/photo      happy path → photo_url escrita en proof
  - PATCH /stops/{id}/proof/photo      proof no existe → 404
  - PATCH /stops/{id}/proof/photo      object_key de otro tenant → 422
  - PATCH /stops/{id}/proof/photo      overwrite → gana el último object_key
  - GET   /stops/{id}/proof            devuelve photo_url tras PATCH

R2 se mockea completamente — no requiere credenciales reales.
"""

import uuid
from datetime import UTC, date, datetime, time
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.models import (
    Customer,
    Driver,
    Order,
    OrderIntakeType,
    OrderStatus,
    Plan,
    PlanStatus,
    Route,
    RouteStatus,
    RouteStop,
    RouteStopStatus,
    SourceChannel,
    StopProof,
    Tenant,
    User,
    UserRole,
    Vehicle,
    Zone,
)
from app.security import hash_password
from tests.helpers import auth_headers, login_as


# ── Constantes de mock ────────────────────────────────────────────────────────

FAKE_UPLOAD_URL = "https://fake-r2.example.com/presigned-put?X-Amz-Signature=abc"
FAKE_R2_PUBLIC_URL = "https://pub-fake.r2.dev"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _logistics_token(client, tenant_slug: str = "demo-cortecero") -> str:
    return login_as(client, tenant_slug=tenant_slug, email="logistics@demo.cortecero.app", password="logistics123")


def _demo_tenant(db_session) -> Tenant:
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None
    return tenant


def _build_route_with_stop(
    db_session,
    tenant_id: uuid.UUID,
    *,
    stop_status: RouteStopStatus = RouteStopStatus.arrived,
) -> tuple[Route, RouteStop]:
    now = datetime.now(UTC)
    svc_date = date.today()

    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id, Vehicle.active.is_(True))
    )
    assert vehicle is not None

    driver = db_session.scalar(
        select(Driver).where(Driver.tenant_id == tenant_id, Driver.is_active.is_(True))
    )
    assert driver is not None

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant_id))
    assert zone is not None

    customer = db_session.scalar(select(Customer).where(Customer.tenant_id == tenant_id))
    assert customer is not None

    plan = Plan(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_date=svc_date,
        zone_id=zone.id,
        status=PlanStatus.locked,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.flush()

    route = Route(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        plan_id=plan.id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        service_date=svc_date,
        status=RouteStatus.in_progress,
        created_at=now,
        updated_at=now,
    )
    db_session.add(route)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer.id,
        zone_id=zone.id,
        external_ref=f"ORD-FOTO-{uuid.uuid4().hex[:6].upper()}",
        status=OrderStatus.dispatched,
        intake_type=OrderIntakeType.new_order,
        source_channel=SourceChannel.office,
        service_date=svc_date,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=now,
        ingested_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(order)
    db_session.flush()

    stop = RouteStop(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        route_id=route.id,
        order_id=order.id,
        sequence_number=1,
        status=stop_status,
        arrived_at=now if stop_status in (RouteStopStatus.arrived, RouteStopStatus.completed) else None,
        completed_at=now if stop_status == RouteStopStatus.completed else None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(stop)
    db_session.commit()
    db_session.refresh(stop)
    return route, stop


def _create_proof(db_session, tenant_id: uuid.UUID, stop: RouteStop) -> StopProof:
    """Crea un StopProof directamente en DB para tests de PATCH."""
    now = datetime.now(UTC)
    proof = StopProof(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        route_stop_id=stop.id,
        route_id=stop.route_id,
        proof_type="signature",
        signature_data="data:image/png;base64,abc==",
        photo_url=None,
        signed_by="Test Driver",
        captured_at=now,
        created_at=now,
    )
    db_session.add(proof)
    db_session.commit()
    db_session.refresh(proof)
    return proof


def _mock_r2_client(presigned_url: str = FAKE_UPLOAD_URL) -> MagicMock:
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = presigned_url
    return mock_client


# ── Tests: POST /proof-upload-url ─────────────────────────────────────────────


def test_proof_upload_url_happy_path(client, db_session):
    """Genera presigned URL con object_key que incluye el tenant_id."""
    tenant = _demo_tenant(db_session)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)
    token = _logistics_token(client)

    mock_client = _mock_r2_client()
    with patch("app.routers.routing._get_r2_client", return_value=mock_client):
        resp = client.post(
            f"/stops/{stop.id}/proof-upload-url",
            headers=auth_headers(token),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["upload_url"] == FAKE_UPLOAD_URL
    assert str(tenant.id) in data["object_key"]
    assert str(stop.id) in data["object_key"]
    assert data["object_key"].endswith(".jpg")
    assert data["expires_in"] == 300


def test_proof_upload_url_stop_completed(client, db_session):
    """También acepta parada en estado completed."""
    tenant = _demo_tenant(db_session)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.completed)
    token = _logistics_token(client)

    mock_client = _mock_r2_client()
    with patch("app.routers.routing._get_r2_client", return_value=mock_client):
        resp = client.post(
            f"/stops/{stop.id}/proof-upload-url",
            headers=auth_headers(token),
        )

    assert resp.status_code == 200


def test_proof_upload_url_stop_wrong_status(client, db_session):
    """Stop en estado 'pending' → 409 STOP_NOT_ARRIVED."""
    tenant = _demo_tenant(db_session)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.pending)
    token = _logistics_token(client)

    mock_client = _mock_r2_client()
    with patch("app.routers.routing._get_r2_client", return_value=mock_client):
        resp = client.post(
            f"/stops/{stop.id}/proof-upload-url",
            headers=auth_headers(token),
        )

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "STOP_NOT_ARRIVED"


def test_proof_upload_url_r2_not_configured(client, db_session):
    """Sin credenciales R2 → 503 R2_NOT_CONFIGURED."""
    tenant = _demo_tenant(db_session)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)
    token = _logistics_token(client)

    from app.routers import routing as routing_module
    from fastapi import HTTPException

    def _raise_503():
        raise HTTPException(
            status_code=503,
            detail={"code": "R2_NOT_CONFIGURED", "message": "Almacenamiento de fotos no configurado"},
        )

    with patch("app.routers.routing._get_r2_client", side_effect=_raise_503):
        resp = client.post(
            f"/stops/{stop.id}/proof-upload-url",
            headers=auth_headers(token),
        )

    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "R2_NOT_CONFIGURED"


# ── Tests: PATCH /proof/photo ─────────────────────────────────────────────────


def test_patch_proof_photo_happy_path(client, db_session):
    """Confirmar foto: photo_url construida por backend con R2_PUBLIC_URL + object_key."""
    tenant = _demo_tenant(db_session)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)
    _create_proof(db_session, tenant.id, stop)
    token = _logistics_token(client)

    object_key = f"{tenant.id}/{stop.route_id}/{stop.id}/{uuid.uuid4()}.jpg"

    with patch("app.routers.routing.settings") as mock_settings:
        mock_settings.r2_public_url = FAKE_R2_PUBLIC_URL
        mock_settings.r2_bucket_name = "cortecero-pod-photos"
        resp = client.patch(
            f"/stops/{stop.id}/proof/photo",
            json={"object_key": object_key},
            headers=auth_headers(token),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["photo_url"] == f"{FAKE_R2_PUBLIC_URL}/{object_key}"


def test_patch_proof_photo_proof_not_found(client, db_session):
    """Sin StopProof previo → 404 PROOF_NOT_FOUND."""
    tenant = _demo_tenant(db_session)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)
    token = _logistics_token(client)

    object_key = f"{tenant.id}/{stop.route_id}/{stop.id}/{uuid.uuid4()}.jpg"

    with patch("app.routers.routing.settings") as mock_settings:
        mock_settings.r2_public_url = FAKE_R2_PUBLIC_URL
        mock_settings.r2_bucket_name = "cortecero-pod-photos"
        resp = client.patch(
            f"/stops/{stop.id}/proof/photo",
            json={"object_key": object_key},
            headers=auth_headers(token),
        )

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROOF_NOT_FOUND"


def test_patch_proof_photo_invalid_object_key(client, db_session):
    """object_key de otro tenant → 422 INVALID_OBJECT_KEY."""
    tenant = _demo_tenant(db_session)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)
    _create_proof(db_session, tenant.id, stop)
    token = _logistics_token(client)

    other_tenant_id = uuid.uuid4()
    object_key = f"{other_tenant_id}/{stop.route_id}/{stop.id}/{uuid.uuid4()}.jpg"

    with patch("app.routers.routing.settings") as mock_settings:
        mock_settings.r2_public_url = FAKE_R2_PUBLIC_URL
        mock_settings.r2_bucket_name = "cortecero-pod-photos"
        resp = client.patch(
            f"/stops/{stop.id}/proof/photo",
            json={"object_key": object_key},
            headers=auth_headers(token),
        )

    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_OBJECT_KEY"


def test_patch_proof_photo_overwrite(client, db_session):
    """Segundo PATCH sobreescribe photo_url — gana el último object_key."""
    tenant = _demo_tenant(db_session)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)
    _create_proof(db_session, tenant.id, stop)
    token = _logistics_token(client)

    key_1 = f"{tenant.id}/{stop.route_id}/{stop.id}/{uuid.uuid4()}.jpg"
    key_2 = f"{tenant.id}/{stop.route_id}/{stop.id}/{uuid.uuid4()}.jpg"

    with patch("app.routers.routing.settings") as mock_settings:
        mock_settings.r2_public_url = FAKE_R2_PUBLIC_URL
        mock_settings.r2_bucket_name = "cortecero-pod-photos"

        client.patch(
            f"/stops/{stop.id}/proof/photo",
            json={"object_key": key_1},
            headers=auth_headers(token),
        )
        resp2 = client.patch(
            f"/stops/{stop.id}/proof/photo",
            json={"object_key": key_2},
            headers=auth_headers(token),
        )

    assert resp2.status_code == 200
    assert resp2.json()["photo_url"] == f"{FAKE_R2_PUBLIC_URL}/{key_2}"


def test_get_proof_returns_photo_url_after_patch(client, db_session):
    """GET /proof devuelve photo_url después de un PATCH exitoso."""
    tenant = _demo_tenant(db_session)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)
    _create_proof(db_session, tenant.id, stop)
    token = _logistics_token(client)

    object_key = f"{tenant.id}/{stop.route_id}/{stop.id}/{uuid.uuid4()}.jpg"

    with patch("app.routers.routing.settings") as mock_settings:
        mock_settings.r2_public_url = FAKE_R2_PUBLIC_URL
        mock_settings.r2_bucket_name = "cortecero-pod-photos"
        client.patch(
            f"/stops/{stop.id}/proof/photo",
            json={"object_key": object_key},
            headers=auth_headers(token),
        )

    resp = client.get(f"/stops/{stop.id}/proof", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["photo_url"] == f"{FAKE_R2_PUBLIC_URL}/{object_key}"
