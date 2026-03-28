from fastapi import HTTPException, status


def api_error(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def not_found(code: str, message: str) -> HTTPException:
    return api_error(status.HTTP_404_NOT_FOUND, code, message)


def conflict(code: str, message: str) -> HTTPException:
    return api_error(status.HTTP_409_CONFLICT, code, message)


def forbidden(code: str, message: str) -> HTTPException:
    return api_error(status.HTTP_403_FORBIDDEN, code, message)


def unauthorized(code: str, message: str) -> HTTPException:
    return api_error(status.HTTP_401_UNAUTHORIZED, code, message)


def unprocessable(code: str, message: str) -> HTTPException:
    return api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, code, message)
