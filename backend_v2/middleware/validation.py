"""
AIIS Backend V2 - Validation Middleware
=======================================
Request payload validation decorator using schema validators.
"""

import functools
import logging
from typing import Callable, Any, Type
from flask import request
from backend_v2.utils.exceptions import ValidationException

logger = logging.getLogger("aiis.middleware.validation")


def validate_json_body(schema_cls: Type[Any]) -> Callable[..., Any]:
    """
    Decorator to parse and validate incoming JSON request bodies against a schema.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            data = request.get_json(silent=True)
            if data is None:
                raise ValidationException("Request body must be a valid JSON object.")

            # Validate using schema class's validate method if implemented
            if hasattr(schema_cls, "validate"):
                is_valid, error_msg = schema_cls.validate(data)
                if not is_valid:
                    raise ValidationException(error_msg or "Schema validation failed.")

            return func(*args, **kwargs)

        return wrapper

    return decorator

