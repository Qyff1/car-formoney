# -*- coding: utf-8 -*-
"""登录与当前用户。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginRequest, UserOut
from ..security import create_access_token, verify_password
from ..serializers import user_to_dict

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    record_audit(db, user, "login", "user", user.id)
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.username, user.role),
        "token_type": "bearer",
        "user": user_to_dict(user),
    }


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    data = user_to_dict(user)
    return UserOut(**data)
