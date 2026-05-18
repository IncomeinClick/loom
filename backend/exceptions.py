from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class NotFoundError(HTTPException):
    def __init__(self, resource: str, id: str):
        super().__init__(status_code=404, detail=f"{resource} '{id}' not found")


class ConflictError(HTTPException):
    def __init__(self, message: str):
        super().__init__(status_code=409, detail=message)


class ValidationError(HTTPException):
    def __init__(self, message: str):
        super().__init__(status_code=422, detail=message)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)[:500], "type": type(exc).__name__},
    )
