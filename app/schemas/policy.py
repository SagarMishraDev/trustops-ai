from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    rule_text: str = Field(min_length=5)
    enabled: bool = True


class PolicyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    rule_text: str | None = Field(default=None, min_length=5)
    enabled: bool | None = None


class PolicyOut(BaseModel):
    id: int
    title: str
    description: str | None
    rule_text: str
    enabled: bool

    @classmethod
    def from_model(cls, p) -> "PolicyOut":
        return cls(id=p.id, title=p.title, description=p.description,
                   rule_text=p.rule_text, enabled=p.enabled)


class EvidenceCreate(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=3)
    source: str = Field(default="manual", max_length=100)


class EvidenceOut(BaseModel):
    id: int
    topic: str
    content: str
    source: str

    @classmethod
    def from_model(cls, e) -> "EvidenceOut":
        return cls(id=e.id, topic=e.topic, content=e.content, source=e.source)
