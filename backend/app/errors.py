"""Błędy domenowe. Każdy niesie kod HTTP, a zamianę na odpowiedź API robi jeden handler w main.py."""


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class BadRequest(AppError):
    status_code = 400


class Forbidden(AppError):
    status_code = 403


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    status_code = 409


class PayloadTooLarge(AppError):
    status_code = 413


class Unprocessable(AppError):
    status_code = 422


class BadGateway(AppError):
    status_code = 502


class ServiceUnavailable(AppError):
    status_code = 503
