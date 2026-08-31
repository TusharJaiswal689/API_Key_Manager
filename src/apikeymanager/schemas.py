from pydantic import BaseModel, Field


class apikey_store(BaseModel):
    service: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)


class apikey_retrieve(BaseModel):
    service: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)