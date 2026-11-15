"""
AIIS Backend V2 - Application Exceptions
========================================
Hierarchy of custom application exceptions for structured error handling.
"""

from typing import Any, Optional


class AppException(Exception):
    """Base application exception."""

    status_code: int = 500
    error_code: str = "INTERNAL_SERVER_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Any] = None,
    ):
        super().__init__(message or self.message)
        if message:
            self.message = message
        if error_code:
            self.error_code = error_code
        if status_code:
            self.status_code = status_code
        self.details = details


class ValidationException(AppException):
    status_code = 400
    error_code = "VALIDATION_ERROR"
    message = "Request validation failed."


class UnauthorizedException(AppException):
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "Authentication required."


class ForbiddenException(AppException):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "You do not have permission to perform this action."


class NotFoundException(AppException):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Requested resource was not found."


class ConflictException(AppException):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource state conflict."


class ServiceUnavailableException(AppException):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"
    message = "External service is currently unavailable."


class DatabaseException(AppException):
    status_code = 500
    error_code = "DATABASE_ERROR"
    message = "A database operation failed."

