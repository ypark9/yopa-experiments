"""Pydantic models of the kind people already have, one 'ordinary' line each."""
from typing import Literal, Optional
from pydantic import AnyUrl, BaseModel, Field

class Baseline(BaseModel):
    category: Literal["billing", "technical", "account"]
    escalate: bool
    reason: str

class WithGe(BaseModel):          # one line: confidence must be 0..1
    category: Literal["billing", "technical", "account"]
    confidence: float = Field(ge=0, le=1)

class WithMaxLength(BaseModel):   # one line: keep the summary short
    summary: str = Field(max_length=200)

class WithOptional(BaseModel):    # one line: field may be missing
    category: Literal["billing", "technical", "account"]
    order_id: Optional[str] = None

class WithMap(BaseModel):         # one line: free-form tag map
    category: Literal["billing", "technical", "account"]
    tags: dict[str, str]

class WithMinItems(BaseModel):    # one line: at least two next steps
    steps: list[str] = Field(min_length=2)

class Node(BaseModel):            # one line: a tree
    label: str
    children: list["Node"] = []

class WithPattern(BaseModel):     # one line: ticket id format
    ticket: str = Field(pattern=r"^TCK-\d{6}$")

class WithFormat(BaseModel):      # one line: a URL field (pydantic emits format: uri)
    link: AnyUrl

CASES = [Baseline, WithGe, WithMaxLength, WithOptional, WithMap, WithMinItems, Node, WithPattern, WithFormat]
