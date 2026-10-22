"""Strict validation primitives shared by every structured contract."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Finite = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,15}$")]


class StrictModel(BaseModel):
    """Reject unknown fields at every graph boundary."""

    model_config = ConfigDict(extra="forbid")
