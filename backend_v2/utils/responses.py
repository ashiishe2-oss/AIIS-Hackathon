"""
AIIS Backend V2 - Response Utilities
====================================
Standardized JSON response envelope helpers for consistent API responses.
"""

from typing import Any, Dict, Optional, Tuple
from flask import jsonify, Response


def api_response(
    success: bool = True,
    data: Optional[Any] = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> Tuple[Response, int]:
    """
    Construct a standardized API JSON response tuple (Response, status_code).
    """
    payload: Dict[str, Any] = {"success": success}

    if data is not None:
        payload["data"] = data

    if message is not None:
        payload["message"] = message

    if meta is not None:
        payload["meta"] = meta

    if error is not None:
        payload["error"] = error

    return jsonify(payload), status_code


def success_response(
    data: Optional[Any] = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> Tuple[Response, int]:
    """Helper for successful responses."""
    return api_response(
        success=True,
        data=data,
        message=message,
        meta=meta,
        status_code=status_code,
    )


def error_response(
    message: str,
    code: str = "INTERNAL_SERVER_ERROR",
    details: Optional[Any] = None,
    status_code: int = 500,
) -> Tuple[Response, int]:
    """Helper for standardized error responses."""
    error_payload: Dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error_payload["details"] = details

    return api_response(
        success=False,
        error=error_payload,
        status_code=status_code,
    )
