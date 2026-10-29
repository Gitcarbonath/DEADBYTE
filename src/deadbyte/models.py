from datetime import datetime, timezone
from pydantic import BaseModel, Field

class Evidence(BaseModel):
    evidence_id: str
    kind: str
    path: str
    line: int | None = None
    excerpt: str
    note: str

class Finding(BaseModel):
    title: str
    explanation: str
    confidence: str = "low"
    evidence_ids: list[str] = Field(default_factory=list)
    is_hypothesis: bool = True

class Investigation(BaseModel):
    case_id: str
    target_path: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    file_count: int = 0
    evidence: list[Evidence] = Field(default_factory=list)
    summary: str = ""
    probable_purpose: str = ""
    findings: list[Finding] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    final_transmission: str = ""
    model: str | None = None
    ai_enabled: bool = False
    warnings: list[str] = Field(default_factory=list)
