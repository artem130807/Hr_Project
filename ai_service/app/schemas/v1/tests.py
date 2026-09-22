from pydantic import BaseModel, ConfigDict, Field


class TestGenerateSchema(BaseModel):
    __test__ = False
    topic: str
    formatted_vacancy: str


class TestQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    __test__ = False
    text: str


class TestGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    __test__ = False
    name: str
    description: str
    instruction: str
    questions: list[TestQuestion]
