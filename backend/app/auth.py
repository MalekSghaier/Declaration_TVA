from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Company, RefreshToken, User
from app.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
REFRESH_COOKIE = "refresh_token"


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str


class MeOut(BaseModel):
    id: int
    email: str
    company_id: int
    company_status: str


def _issue_refresh_cookie(response: Response, db: Session, user_id: int) -> None:
    raw, hashed = new_refresh_token()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_DAYS)
    db.add(RefreshToken(user_id=user_id, token_hash=hashed, expires_at=expires))
    db.commit()
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.REFRESH_TOKEN_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/api/auth",
    )


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: Credentials, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet email est déjà utilisé")
    company = Company()
    db.add(company)
    db.flush()
    user = User(email=email, password_hash=hash_password(data.password), company_id=company.id)
    db.add(user)
    db.commit()
    _issue_refresh_cookie(response, db, user.id)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(data: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email ou mot de passe incorrect")
    _issue_refresh_cookie(response, db, user.id)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/refresh", response_model=TokenOut)
def refresh(request: Request, db: Session = Depends(get_db)):
    raw = request.cookies.get(REFRESH_COOKIE)
    row = (
        db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
        if raw
        else None
    )
    if not row or row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expirée")
    return TokenOut(access_token=create_access_token(row.user_id))


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        db.execute(delete(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
        db.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.get(Company, user.company_id)
    return MeOut(
        id=user.id,
        email=user.email,
        company_id=company.id,
        company_status=company.status,
    )