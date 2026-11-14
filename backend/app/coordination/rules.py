"""Common domain rejection, translated to HTTP 409 at the API boundary."""


class Conflict(ValueError):
    pass


def require(condition: bool, message: str):
    if not condition:
        raise Conflict(message)
