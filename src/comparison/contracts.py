from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Source(Contract):
    url: str = Field(min_length=8, max_length=2048)
    label: str = Field(default='', max_length=120)

    @field_validator('url')
    @classmethod
    def http_url(cls, value):
        p = urlsplit(value.strip())
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
            raise ValueError('Indica una URL HTTP(S) sin credenciales.')
        _ = p.port
        return value.strip()


class Limits(Contract):
    max_pages: int | None = Field(default=5, ge=1, le=100)
    max_hops: int | None = Field(default=2, ge=0, le=8)
    same_host_only: bool = True
    capture_seconds: int = Field(default=180, ge=5, le=600)
    processing_seconds: int = Field(default=120, ge=5, le=600)


class ComparisonRequest(Contract):
    contract_version: Literal['1.0'] = '1.0'
    sources: list[Source] = Field(min_length=2, max_length=2)
    limits: Limits = Field(default_factory=Limits)
    interpreter: Literal['declared', 'jev'] = 'declared'
    review_recognition: Literal['off', 'lexical', 'e5'] = 'e5'


class ImportSource(Contract):
    label: str = Field(default='', max_length=120)
    payload: JsonValue


class ImportRequest(Contract):
    contract_version: Literal['1.0'] = '1.0'
    sources: list[ImportSource] = Field(min_length=2, max_length=2)
    interpreter: Literal['declared', 'jev'] = 'declared'
    review_recognition: Literal['off', 'lexical', 'e5'] = 'e5'
    limits: Limits = Field(default_factory=Limits)


class SourceState(Contract):
    url: str
    label: str
    status: str
    capture_status: str
    processing_status: str
    stop_reason: str | None = None
    processing_stop_reason: str | None = None
    started_at: str | None = None
    capture_finished_at: str | None = None
    finished_at: str | None = None
    progress: dict[str, JsonValue] = Field(default_factory=dict)
    result_available: bool
    artifacts: list[Literal['capture', 'import', 'input', 'output', 'presentation', 'usage']]


class ComparisonState(Contract):
    contract_version: Literal['1.0']
    comparison_id: str
    status: Literal['queued', 'running', 'done', 'partial', 'failed', 'cancelled', 'interrupted']
    phase: str
    created_at: str
    finished_at: str | None
    imported: bool
    synthetic: bool = False
    sources: list[SourceState] = Field(min_length=2, max_length=2)
    events: list[dict[str, str]]
