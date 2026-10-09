from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def validation_error(request, error: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
                for item in error.errors()
            ]
        },
    )
