"""Domain errors raised from services; mapped to HTTP responses in the API layer."""

from __future__ import annotations


class AppError(Exception):
    status_code: int = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class BadRequestError(AppError):
    status_code = 400
