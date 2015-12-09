import httplib
import json


class APIException(Exception):
    """
    Class to report errors in opsrest.
    """
    status_code = httplib.BAD_REQUEST
    status = httplib.responses[status_code]

    def __init__(self, detail=None):
        self.detail = detail

    def __str__(self):
        return json.dumps(self.detail)


class DataValidationFailed(APIException):
    status_code = httplib.BAD_REQUEST
    status = httplib.responses[status_code]


class ParseError(APIException):
    status_code = httplib.BAD_REQUEST
    status = httplib.responses[status_code]


class AuthenticationFailed(APIException):
    status_code = httplib.UNAUTHORIZED
    status = httplib.responses[status_code]


class NotAuthenticated(APIException):
    status_code = httplib.UNAUTHORIZED
    status = httplib.responses[status_code]


class NotFound(APIException):
    status_code = httplib.NOT_FOUND
    status = httplib.responses[status_code]


class MethodNotAllowed(APIException):
    status_code = httplib.METHOD_NOT_ALLOWED
    status = httplib.responses[status_code]
