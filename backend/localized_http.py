"""Keep legacy HTTP error details while adding safe, structured presentation messages."""

import json

from fastapi import HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.localization import CATALOGUES, LocalizedString, LocalizedText, text


class LocalizedHTTPFailure(HTTPException):
    def __init__(self, status: int, detail: str, reference: LocalizedText) -> None:
        self.reference = reference
        super().__init__(status_code=status, detail=detail)


def exception_reference(failure: Exception) -> LocalizedText | None:
    return failure.args[0].reference if failure.args and isinstance(failure.args[0], LocalizedString) else None


def http_failure(status: int, failure: Exception, prefix: str = "") -> LocalizedHTTPFailure:
    reference = exception_reference(failure) or fallback_reference(status)
    return LocalizedHTTPFailure(status, prefix + str(failure), reference)


def fallback_reference(status: int) -> LocalizedText:
    keys = {401: "http.sign_in", 403: "http.denied", 404: "http.not_found", 409: "http.conflict",
            413: "http.too_large", 422: "http.validation", 429: "http.busy"}
    return text(keys.get(status, "http.unavailable")).reference


async def http_exception_response(request: Request, failure: StarletteHTTPException) -> JSONResponse:
    reference = failure.reference if isinstance(failure, LocalizedHTTPFailure) else fallback_reference(failure.status_code)
    return JSONResponse({"detail": failure.detail, "message": reference.model_dump(),
                         "correlation_id": getattr(request.state, "correlation_id", "unknown")},
                        status_code=failure.status_code, headers=failure.headers)


async def validation_exception_response(request: Request, failure: RequestValidationError) -> JSONResponse:
    original = await request_validation_exception_handler(request, failure)
    payload = json.loads(bytes(original.body))
    references = []
    for error in failure.errors()[:3]:
        cause = error.get("ctx", {}).get("error")
        reference = exception_reference(cause) if isinstance(cause, Exception) else None
        if reference is None:
            key = "validation." + str(error["type"])
            if key not in CATALOGUES["en"]:
                key = "validation.invalid"
            field = ".".join(str(part) for part in error["loc"] if part != "body") or "circuit"
            reference = text(key, field=field).reference
        references.append(reference.model_dump())
    payload["messages"] = references
    payload["correlation_id"] = getattr(request.state, "correlation_id", "unknown")
    return JSONResponse(payload, status_code=422)
