from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class SessionCreateRequest(ApiModel):
    clientSessionId: str = Field(min_length=1, max_length=128)
    mode: Literal["education", "experience"] = "education"
    deviceId: str | None = Field(default=None, max_length=128)
    traineeId: str | None = Field(default=None, max_length=128)
    courseId: str | None = Field(default=None, max_length=128)
    scenarioId: str = Field(default="hno3_leak_indoor_tank", min_length=1, max_length=128)
    contentVersion: str | None = Field(default=None, max_length=64)
    startedAt: str | None = Field(default=None, max_length=64)

    @field_validator("clientSessionId", "deviceId", "traineeId", "courseId", "scenarioId", "contentVersion")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class SessionEvent(ApiModel):
    eventId: str | None = Field(default=None, max_length=128)
    t: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    at: str | None = Field(default=None, max_length=64)
    type: str | None = Field(default=None, max_length=64)
    phase: str | None = Field(default=None, max_length=128)
    step: str | None = Field(default=None, max_length=128)
    code: str | None = Field(default=None, max_length=128)
    severity: str | None = Field(default=None, max_length=32)
    payload: dict[str, Any] = Field(default_factory=dict)


class EventBatchRequest(ApiModel):
    batchSeq: int = Field(ge=1)
    sentAt: str | None = Field(default=None, max_length=64)
    events: list[SessionEvent] = Field(default_factory=list, max_length=2048)


class CompleteResult(ApiModel):
    passed: bool = False
    durationSec: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    reachedPhase: str | None = Field(default=None, max_length=128)
    reachedStep: str | None = Field(default=None, max_length=128)
    blockingViolations: int = Field(default=0, ge=0)
    warnViolations: int = Field(default=0, ge=0)


class CompleteRequest(ApiModel):
    reason: str | None = Field(default=None, max_length=64)
    endedAt: str | None = Field(default=None, max_length=64)
    result: CompleteResult = Field(default_factory=CompleteResult)
