from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    full_name: str
    email: str
    phone: str | None = None
    password: str
    referral_code: str | None = None


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    avatar_url: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    phone: str
    otp: str
    new_password: str


class UserProfileResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: str | None = None
    avatar_url: str | None = None
    role: str
    referral_code: str | None = None
    wallet_balance: float
    is_verified: bool

    class Config:
        from_attributes = True
