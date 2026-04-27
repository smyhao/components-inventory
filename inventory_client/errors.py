from __future__ import annotations

from typing import Any


EXIT_BUSINESS = 1
EXIT_ARGUMENT = 2
EXIT_NETWORK = 3
EXIT_AUTH = 4
EXIT_FILE_IO = 5
EXIT_UNEXPECTED = 6


class ClientError(Exception):
    """Base class for CLI-visible client errors."""

    exit_code = EXIT_UNEXPECTED

    def __init__(self, message: str, *, response: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.response = response


class BusinessError(ClientError):
    exit_code = EXIT_BUSINESS


class ArgumentUsageError(ClientError):
    exit_code = EXIT_ARGUMENT


class ApiError(BusinessError):
    pass


class NetworkError(ClientError):
    exit_code = EXIT_NETWORK


class AuthError(ClientError):
    exit_code = EXIT_AUTH


class FileIoError(ClientError):
    exit_code = EXIT_FILE_IO


class UnexpectedResponseError(ClientError):
    exit_code = EXIT_UNEXPECTED
