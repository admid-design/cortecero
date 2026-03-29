import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import conflict, not_found, unprocessable
from app.models import User, UserRole
from app.schemas import UserCreateRequest, UserOut, UsersListResponse, UserUpdateRequest
from app.security import hash_password


router = APIRouter(prefix="/admin/users", tags=["Admin Users"])


def _active_admin_count(db: Session, tenant_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count(User.id)).where(
                User.tenant_id == tenant_id,
                User.role == UserRole.admin,
                User.is_active.is_(True),
            )
        )
        or 0
    )


@router.get("", response_model=UsersListResponse)
def list_users(
    is_active: bool | None = None,
    role: UserRole | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> UsersListResponse:
    query = select(User).where(User.tenant_id == current.tenant_id)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if role is not None:
        query = query.where(User.role == role)

    rows = list(db.scalars(query.order_by(User.created_at.desc())))
    return UsersListResponse(items=[UserOut.model_validate(row) for row in rows], total=len(rows))


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> UserOut:
    normalized_email = payload.email.strip().lower()
    existing = db.scalar(
        select(User).where(
            User.tenant_id == current.tenant_id,
            func.lower(User.email) == normalized_email,
        )
    )
    if existing:
        raise conflict("RESOURCE_CONFLICT", "Ya existe un usuario con ese email")

    row = User(
        tenant_id=current.tenant_id,
        email=normalized_email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole(payload.role),
        is_active=payload.is_active,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo crear el usuario") from exc

    db.refresh(row)
    return UserOut.model_validate(row)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> UserOut:
    row = db.scalar(select(User).where(User.id == user_id, User.tenant_id == current.tenant_id))
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Usuario no encontrado")

    if not payload.model_fields_set:
        raise unprocessable("INVALID_STATE_TRANSITION", "No hay cambios para aplicar")

    next_role = row.role
    if "role" in payload.model_fields_set:
        if payload.role is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "El rol no puede ser null")
        next_role = UserRole(payload.role)

    next_is_active = row.is_active
    if "is_active" in payload.model_fields_set:
        if payload.is_active is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "El estado activo no puede ser null")
        next_is_active = payload.is_active

    current_is_active_admin = row.role == UserRole.admin and row.is_active
    next_is_active_admin = next_role == UserRole.admin and next_is_active
    if current_is_active_admin and not next_is_active_admin:
        if _active_admin_count(db, current.tenant_id) <= 1:
            raise unprocessable(
                "INVALID_STATE_TRANSITION",
                "No se puede desactivar o degradar el último admin activo del tenant",
            )

    if "email" in payload.model_fields_set:
        if payload.email is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "El email no puede ser null")
        normalized_email = payload.email.strip().lower()
        if normalized_email != row.email:
            existing = db.scalar(
                select(User).where(
                    User.tenant_id == current.tenant_id,
                    func.lower(User.email) == normalized_email,
                    User.id != row.id,
                )
            )
            if existing:
                raise conflict("RESOURCE_CONFLICT", "Ya existe un usuario con ese email")
            row.email = normalized_email

    if "full_name" in payload.model_fields_set:
        if payload.full_name is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "El nombre no puede ser null")
        row.full_name = payload.full_name

    if "role" in payload.model_fields_set:
        row.role = next_role

    if "password" in payload.model_fields_set:
        if payload.password is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "La password no puede ser null")
        row.password_hash = hash_password(payload.password)

    if "is_active" in payload.model_fields_set:
        row.is_active = next_is_active

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo actualizar el usuario") from exc

    db.refresh(row)
    return UserOut.model_validate(row)
