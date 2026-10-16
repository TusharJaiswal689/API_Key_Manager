from pydantic import BaseModel, Field


class apikey_credentials(BaseModel):
    service: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)

class apikey_credentials_update(BaseModel):
    service: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    new_service: str | None = Field(default=None, min_length=1)
    new_username: str | None = Field(default=None, min_length=1)