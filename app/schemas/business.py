from pydantic import BaseModel, Field


class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)


class BusinessCreated(BaseModel):
    id: int
    name: str
    api_key: str  # shown ONCE at creation; only its hash is stored
    note: str = "Save this API key now. It will not be shown again - only its hash is stored."
