from datetime import UTC, datetime

from app.models import Product, Tenant, User, UserRole
from app.security import hash_password
from tests.helpers import auth_headers, login_as


def test_list_products_is_tenant_scoped_and_readable_by_office(client, db_session):
    tenant_b = Tenant(
        name="Tenant B Products",
        slug="tenant-b-products",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(tenant_b)
    db_session.flush()
    db_session.add(
        Product(
            tenant_id=tenant_b.id,
            sku="SKU-EXTERNO",
            name="Producto Externo",
            barcode="EXT001",
            uom="unit",
            active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    res = client.get("/admin/products", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert all(item["sku"] != "SKU-EXTERNO" for item in items)


def test_create_product_requires_admin_role(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    res = client.post(
        "/admin/products",
        json={"sku": "SKU-A", "name": "Producto A", "barcode": "A001", "uom": "unit"},
        headers=auth_headers(token),
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "RBAC_FORBIDDEN"


def test_create_update_deactivate_product_and_sku_conflict(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    create_res = client.post(
        "/admin/products",
        json={"sku": "SKU-R7-001", "name": "Producto R7", "barcode": "R7001", "uom": "unit"},
        headers=auth_headers(token),
    )
    assert create_res.status_code == 201, create_res.text
    product_id = create_res.json()["id"]

    update_res = client.patch(
        f"/admin/products/{product_id}",
        json={"name": "Producto R7 Editado", "uom": "box"},
        headers=auth_headers(token),
    )
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["name"] == "Producto R7 Editado"
    assert update_res.json()["uom"] == "box"

    create_second_res = client.post(
        "/admin/products",
        json={"sku": "SKU-R7-002", "name": "Producto R7 2", "barcode": "R7002", "uom": "unit"},
        headers=auth_headers(token),
    )
    assert create_second_res.status_code == 201, create_second_res.text
    second_id = create_second_res.json()["id"]

    duplicate_res = client.patch(
        f"/admin/products/{second_id}",
        json={"sku": "SKU-R7-001"},
        headers=auth_headers(token),
    )
    assert duplicate_res.status_code == 409
    assert duplicate_res.json()["detail"]["code"] == "RESOURCE_CONFLICT"

    deactivate_ok = client.post(f"/admin/products/{product_id}/deactivate", headers=auth_headers(token))
    assert deactivate_ok.status_code == 200, deactivate_ok.text
    assert deactivate_ok.json()["active"] is False

    deactivate_again = client.post(f"/admin/products/{product_id}/deactivate", headers=auth_headers(token))
    assert deactivate_again.status_code == 422
    assert deactivate_again.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_update_product_is_tenant_filtered(client, db_session):
    tenant_b = Tenant(
        name="Tenant B Products 2",
        slug="tenant-b-products-2",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(tenant_b)
    db_session.flush()
    db_session.add(
        User(
            tenant_id=tenant_b.id,
            email="admin@tenantb-products.cortecero.app",
            full_name="Tenant B Admin",
            password_hash=hash_password("adminb123"),
            role=UserRole.admin,
            is_active=True,
            created_at=datetime.now(UTC),
        )
    )
    product_b = Product(
        tenant_id=tenant_b.id,
        sku="SKU-TB-001",
        name="Producto Tenant B",
        barcode="TB001",
        uom="unit",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(product_b)
    db_session.commit()

    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    res = client.patch(
        f"/admin/products/{product_b.id}",
        json={"name": "No permitido"},
        headers=auth_headers(token),
    )
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "ENTITY_NOT_FOUND"

