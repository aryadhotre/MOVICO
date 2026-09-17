"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_helper import create_access_token, get_current_user, get_password_hash, verify_password
from app.config.settings import settings
from app.database.connection import get_db
from app.database.models import User
from app.database.schemas import Token, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


class AuthResult(Token):
    """A token plus the user it belongs to, so sign-up needs one round trip."""

    user: UserResponse


def _issue(user: User) -> dict:
    return {
        "access_token": create_access_token(data={"sub": user.username}),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user,
    }


@router.post("/register", response_model=AuthResult, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Creates an account and signs the user straight in.

    Returning a token here means the client does not have to immediately POST to
    ``/login`` with credentials it already has.
    """
    # Usernames and emails are compared case-insensitively so "Arya" and "arya"
    # cannot both be registered and then confuse login.
    clash = db.execute(
        select(User).where(
            (func.lower(User.username) == payload.username.lower())
            | (func.lower(User.email) == payload.email.lower())
        )
    ).scalar_one_or_none()
    if clash is not None:
        field = "Username" if clash.username.lower() == payload.username.lower() else "Email"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"{field} is already registered"
        )

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue(user)


@router.post("/login", response_model=AuthResult)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Exchanges credentials for a bearer token."""
    user = db.execute(
        select(User).where(func.lower(User.username) == form_data.username.lower())
    ).scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue(user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
