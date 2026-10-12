"""Provider-neutral batch input. Concrete provider configuration belongs to hosts."""
from pydantic import BaseModel


class TestInput(BaseModel):
    test_name: str
    prompt: str
