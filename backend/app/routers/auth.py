from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import unauthorized
from app.models import User
from app.schemas import LoginRequest, TokenResponse
from app.security import create_access_token, verify_password


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise unauthorized("INVALID_CREDENTIALS", "Credenciales inválidas")

    token = create_access_token(str(user.id), str(user.tenant_id), user.role.value)
    return TokenResponse(access_token=token)
