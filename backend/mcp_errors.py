"""Safe, typed error isolation for MCP handlers, without leaking submitted graphs or secrets."""

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import asyncpg
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from backend.project_models import ProjectFailure

Parameters = ParamSpec("Parameters")
ResponseValue = TypeVar("ResponseValue")
LOGGER = logging.getLogger("circuit-lab.mcp")


def guard_handler(handler: Callable[Parameters, Awaitable[ResponseValue]]) -> Callable[Parameters, Awaitable[ResponseValue]]:
    """Preserve SDK schemas/signatures and turn expected failure domains into honest safe errors."""
    @wraps(handler)
    async def guarded(*arguments: Parameters.args, **keywords: Parameters.kwargs) -> ResponseValue:
        try:
            return await handler(*arguments, **keywords)
        except ProjectFailure as failure:
            raise ToolError(failure.message) from failure
        except ValidationError as failure:
            raise ToolError("Invalid circuit input or evidence; reread capabilities and validate") from failure
        except (asyncpg.PostgresError, OSError, TimeoutError) as failure:
            LOGGER.error("MCP dependency unavailable handler=%s kind=%s", handler.__name__, type(failure).__name__)
            raise ToolError("Circuit storage or identity is unavailable; no success is claimed") from failure
    return guarded
