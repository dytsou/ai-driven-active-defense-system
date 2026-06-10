from pydantic import BaseModel, Field


class RegisterStartResponse(BaseModel):
    status: str
    registration_token: str | None = None
    nycu_authorization_url: str | None = None
    message: str | None = None


class RegisterLineStartRequest(BaseModel):
    registration_token: str


class RegisterLineStartResponse(BaseModel):
    status: str
    line_authorization_url: str | None = None
    message: str | None = None


class RegisterCompleteRequest(BaseModel):
    registration_token: str


class RegisterStatusResponse(BaseModel):
    status: str
    step: str | None = None
    username: str | None = None
    email_masked: str | None = None
    line_official_account_url: str | None = None
    message: str | None = None
