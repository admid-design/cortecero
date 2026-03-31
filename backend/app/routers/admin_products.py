import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import conflict, not_found, unprocessable
from app.models import Product, UserRole
from app.schemas import ProductCreateRequest, ProductOut, ProductsListResponse, ProductUpdateRequest


router = APIRouter(prefix="/admin/products", tags=["Admin Products"])


def _normalize_non_empty(value: str, *, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise unprocessable("INVALID_PRODUCT", f"{field} no puede estar vacío")
    return normalized


@router.get("", response_model=ProductsListResponse)
def list_products(
    active: bool | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> ProductsListResponse:
    query = select(Product).where(Product.tenant_id == current.tenant_id)
    if active is not None:
        query = query.where(Product.active == active)

    rows = list(db.scalars(query.order_by(Product.created_at.desc())))
    return ProductsListResponse(items=[ProductOut.model_validate(row) for row in rows], total=len(rows))


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> ProductOut:
    sku = _normalize_non_empty(payload.sku, field="sku")
    name = _normalize_non_empty(payload.name, field="name")
    uom = _normalize_non_empty(payload.uom, field="uom")
    barcode = payload.barcode.strip() if payload.barcode is not None else None
    if barcode == "":
        barcode = None

    existing = db.scalar(
        select(Product).where(
            Product.tenant_id == current.tenant_id,
            Product.sku == sku,
        )
    )
    if existing:
        raise conflict("RESOURCE_CONFLICT", "Ya existe un producto con ese SKU")

    row = Product(
        tenant_id=current.tenant_id,
        sku=sku,
        name=name,
        barcode=barcode,
        uom=uom,
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo crear el producto") from exc

    db.refresh(row)
    return ProductOut.model_validate(row)


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> ProductOut:
    row = db.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == current.tenant_id))
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Producto no encontrado")

    if not payload.model_fields_set:
        raise unprocessable("INVALID_STATE_TRANSITION", "No hay cambios para aplicar")

    if "sku" in payload.model_fields_set:
        if payload.sku is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "sku no puede ser null")
        sku = _normalize_non_empty(payload.sku, field="sku")
        if sku != row.sku:
            existing = db.scalar(
                select(Product).where(
                    Product.tenant_id == current.tenant_id,
                    Product.sku == sku,
                    Product.id != row.id,
                )
            )
            if existing:
                raise conflict("RESOURCE_CONFLICT", "Ya existe un producto con ese SKU")
            row.sku = sku

    if "name" in payload.model_fields_set:
        if payload.name is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "name no puede ser null")
        row.name = _normalize_non_empty(payload.name, field="name")

    if "uom" in payload.model_fields_set:
        if payload.uom is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "uom no puede ser null")
        row.uom = _normalize_non_empty(payload.uom, field="uom")

    if "barcode" in payload.model_fields_set:
        if payload.barcode is None:
            row.barcode = None
        else:
            barcode = payload.barcode.strip()
            row.barcode = barcode or None

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo actualizar el producto") from exc

    db.refresh(row)
    return ProductOut.model_validate(row)


@router.post("/{product_id}/deactivate", response_model=ProductOut)
def deactivate_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> ProductOut:
    row = db.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == current.tenant_id))
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Producto no encontrado")

    if not row.active:
        raise unprocessable("INVALID_STATE_TRANSITION", "El producto ya está desactivado")

    row.active = False
    db.commit()
    db.refresh(row)
    return ProductOut.model_validate(row)
