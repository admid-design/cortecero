from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import unauthorized
from app.models import Tenant, User
from app.schemas import LoginRequest, TokenResponse
from app.security import create_access_token, verify_password


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == payload.tenant_slug))
    if not tenant:
        raise unauthorized("INVALID_CREDENTIALS", "Credenciales inválidas")

    normalized_email = payload.email.strip().lower()
    user = db.scalar(
        select(User).where(
            User.tenant_id == tenant.id,
            func.lower(User.email) == normalized_email,
        )
    )
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise unauthorized("INVALID_CREDENTIALS", "Credenciales inválidas")

    token = create_access_token(str(user.id), str(user.tenant_id), user.role.value)
    return TokenResponse(access_token=token)
