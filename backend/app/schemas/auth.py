import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,32}$")


def normalize_username(raw: str) -> str:
    """NFKC folds look-alikes (full-width letters, etc.) so they cannot create a second account."""
    return unicodedata.normalize("NFKC", raw).strip().lower()


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # no way to smuggle in role, is_active, subject_ref, ...


class RegisterRequest(_Strict):
    display_name: str = Field(max_length=120)
    username: str = Field(max_length=64)
    password: str = Field(max_length=128)
    confirm_password: str = Field(max_length=128)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 60:
            raise ValueError("Display name must be 1 to 60 characters.")
        if any(unicodedata.category(ch)[0] == "C" for ch in v):
            raise ValueError("Display name contains invalid characters.")
        return v

    @field_validator("username")
    @classmethod
    def clean_username(cls, v: str) -> str:
        v = normalize_username(v)
        if not USERNAME_RE.match(v):
            raise ValueError("Username must be 3 to 32 characters: letters, numbers, underscore or dot.")
        return v

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class LoginRequest(_Strict):
    username: str = Field(max_length=64)
    password: str = Field(max_length=128)

    @field_validator("username")
    @classmethod
    def clean_username(cls, v: str) -> str:
        return normalize_username(v)


class RecoverRequest(_Strict):
    username: str = Field(max_length=64)
    recovery_code: str = Field(max_length=64)
    new_password: str = Field(max_length=128)
    confirm_password: str = Field(max_length=128)

    @field_validator("username")
    @classmethod
    def clean_username(cls, v: str) -> str:
        return normalize_username(v)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    display_name: str
    username: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RecoveryTokenResponse(TokenResponse):
    recovery_code: str  # shown exactly once


class ChangePasswordRequest(_Strict):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)
    confirm_password: str = Field(max_length=128)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class PasswordConfirmRequest(_Strict):
    password: str = Field(max_length=128)
