from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class InputMode(str, Enum):
    auto = "auto"
    raw = "raw"
    derived = "derived"


class SegmentationConfig(BaseModel):
    nucleus_channel: int = Field(default=0, ge=0, le=31)
    protein_channel: int = Field(default=2, ge=0, le=31)
    gaussian_kernel: int = Field(default=5, ge=1, le=51)
    gaussian_sigma: float = Field(default=1.0, gt=0, le=20)
    opening_kernel: int = Field(default=3, ge=1, le=51)
    closing_kernel: int = Field(default=5, ge=1, le=51)
    min_nucleus_area: int = Field(default=100, ge=1, le=10_000_000)
    pixel_size: float | None = Field(default=None, gt=0)
    pixel_unit: str = Field(default="µm", min_length=1, max_length=16)
    input_mode: InputMode = InputMode.auto

    @field_validator("gaussian_kernel", "opening_kernel", "closing_kernel")
    @classmethod
    def odd_kernel(cls, value: int) -> int:
        if value % 2 == 0:
            raise ValueError("O tamanho do kernel deve ser ímpar")
        return value


class EditRequest(BaseModel):
    operation: Literal["hide", "exclude", "restore", "edit_contour"]
    nucleus_ids: list[int] = Field(default_factory=list)
    base_revision: int = Field(ge=0)
    polygon: list[list[float]] | None = None
    nucleus_id: int | None = Field(default=None, ge=1)

    @field_validator("polygon")
    @classmethod
    def polygon_points(cls, value: list[list[float]] | None) -> list[list[float]] | None:
        if value is not None and (len(value) < 3 or any(len(point) != 2 for point in value)):
            raise ValueError("O contorno deve ter pelo menos três pontos [x, y]")
        return value


class RevisionRequest(BaseModel):
    base_revision: int = Field(ge=0)


class ReprocessRequest(BaseModel):
    config: SegmentationConfig | None = None
    base_revision: int = Field(ge=0)


class ImageDescriptor(BaseModel):
    name: str
    role: Literal["nucleus", "protein"]
    width: int | None = None
    height: int | None = None
    channels: int | None = None
    dtype: str | None = None
    derived: bool = False


class JobResponse(BaseModel):
    job_id: str
    session_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    message: str = ""
    error: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    job_id: str
    status: str
    revision: int
    config: SegmentationConfig
    warnings: list[str] = Field(default_factory=list)
    images: list[ImageDescriptor] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: Any
