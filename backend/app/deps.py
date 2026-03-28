import uuid
from typing import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import forbidden, unauthorized
from app.models import User, UserRole
from app.security import decode_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class CurrentUser:
    def __init__(self, user: User):
        self.id: uuid.UUID = user.id
        self.tenant_id: uuid.UUID = user.tenant_id
        self.role: UserRole = user.role
        self.email: str = user.email


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> CurrentUser:
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise unauthorized("INVALID_TOKEN", "Token inválido") from exc

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if not user_id or not tenant_id:
        raise unauthorized("INVALID_TOKEN", "Token incompleto")

    user = db.scalar(
        select(User).where(
            User.id == uuid.UUID(user_id),
            User.tenant_id == uuid.UUID(tenant_id),
            User.is_active.is_(True),
        )
    )
    if not user:
        raise unauthorized("INVALID_TOKEN", "Usuario no válido")

    return CurrentUser(user)


def require_roles(*roles: UserRole) -> Callable[[CurrentUser], CurrentUser]:
    def _check(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current.role not in roles:
            raise forbidden("RBAC_FORBIDDEN", "No tienes permisos para esta acción")
        return current

    return _check
