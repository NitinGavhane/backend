from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    fullName: str
    email: str
    phone: str = ""
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class TokenResponse(BaseModel):
    accessToken: str
    refreshToken: str
    user: dict


class RefreshTokenRequest(BaseModel):
    refreshToken: str
