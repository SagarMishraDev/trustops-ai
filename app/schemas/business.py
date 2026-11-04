from pydantic import BaseModel, Field


class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)


class BusinessCreated(BaseModel):
    id: int
    name: str
    api_key: str
    webhook_secret: str
    note: str = ("Save the API key and webhook secret now - neither is shown again. "
                 "The API key is stored only as a hash; the webhook secret is your HMAC signing key.")
