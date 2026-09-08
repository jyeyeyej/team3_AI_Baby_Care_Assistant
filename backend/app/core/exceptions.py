"""Domain errors with stable API error codes."""


class ApplicationError(Exception):
    status_code = 400
    error_code = "INVALID_REQUEST"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.error_code)


class NotFoundError(ApplicationError):
    status_code = 404


class ConflictError(ApplicationError):
    status_code = 409


class ExternalServiceError(ApplicationError):
    status_code = 503
    error_code = "EXTERNAL_API_ERROR"
