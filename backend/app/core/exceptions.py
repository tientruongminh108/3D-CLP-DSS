class DSSException(Exception):
    def __init__(self, message: str, code: str = "DSS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(DSSException):
    def __init__(self, message: str, field: str = None):
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field


class SolverError(DSSException):
    def __init__(self, message: str):
        super().__init__(message, "SOLVER_ERROR")


class NotFoundError(DSSException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(f"{resource} not found: {identifier}", "NOT_FOUND")
        self.resource = resource
        self.identifier = identifier


class ConflictError(DSSException):
    def __init__(self, message: str):
        super().__init__(message, "CONFLICT")