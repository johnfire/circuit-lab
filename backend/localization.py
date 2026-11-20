"""Structured display messages; electrical models and numeric evidence have no locale."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, model_validator

LOCALES = Path(__file__).resolve().parents[1] / "locales"


def read_catalogue(language: str) -> dict[str, str]:
    decoded: object = json.loads((LOCALES / language / "messages.json").read_text())
    if not isinstance(decoded, dict) or not all(isinstance(key, str) and isinstance(value, str)
                                              for key, value in decoded.items()):
        raise ValueError("Invalid translation catalogue")
    return decoded


CATALOGUES = {language: read_catalogue(language) for language in ("en", "de")}


class LocalizedText(BaseModel):
    """Message identity and arguments travel with immutable English report fields."""

    key: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,180}$")
    values: dict[str, str | int | float | LocalizedText] = Field(default_factory=dict, max_length=20)


def render_message(reference: LocalizedText, language: str = "en") -> str:
    catalogue = CATALOGUES[language if language in CATALOGUES else "en"]
    template = catalogue.get(reference.key, CATALOGUES["en"][reference.key])
    values = {key: render_message(value, language) if isinstance(value, LocalizedText) else str(value)
              for key, value in reference.values.items()}
    return re.sub(r"\{\{([a-zA-Z0-9_]+)\}\}", lambda match: values[match[1]], template)


class LocalizedString(str):
    """Backwards-compatible English string carrying structured presentation metadata."""

    reference: LocalizedText

    def __new__(cls, reference: LocalizedText) -> Self:
        instance = super().__new__(cls, render_message(reference))
        instance.reference = reference
        return instance

    def __add__(self, other: str) -> LocalizedString:
        return text("common.concatenate", first=self, second=other)

    def __radd__(self, other: str) -> LocalizedString:
        return text("common.concatenate", first=other, second=self)


def text(key: str, **values: str | int | float | LocalizedText) -> LocalizedString:
    arguments = {name: value.reference if isinstance(value, LocalizedString) else value
                 for name, value in values.items()}
    return LocalizedString(LocalizedText(key=key, values=arguments))


def catalogue_value(key: str, original: str) -> str:
    return text(key) if key in CATALOGUES["en"] else original


class LocalizationMetadata(BaseModel):
    """Capture references before Pydantic serializes the legacy string fields."""

    warning_messages: list[LocalizedText | None] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def capture_warnings(cls, submitted: object) -> object:
        if isinstance(submitted, dict) and "warning_messages" not in submitted:
            warnings = submitted.get("warnings", [])
            if not isinstance(warnings, list):
                return submitted
            return {**submitted, "warning_messages": [warning.reference if isinstance(warning, LocalizedString)
                                                       else None for warning in warnings]}
        return submitted
