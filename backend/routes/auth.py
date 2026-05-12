"""Auth routes for shared password login."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.auth import generate_token, validate_token, invalidate_token

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    message: str


class LogoutRequest(BaseModel):
    token: str


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    token = generate_token(req.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid password")
    return LoginResponse(token=token, message="Login successful")


@router.post("/logout")
def logout(req: LogoutRequest):
    invalidate_token(req.token)
    return {"message": "Logged out successfully"}


@router.get("/validate")
def validate(token: str):
    if not validate_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"valid": True}