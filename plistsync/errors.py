from eyconf.validation import ConfigurationError, MultiConfigurationError
from requests import Response

__all__ = [
    "ConfigurationError",
    "MultiConfigurationError",
    "NotFoundError",
    "ResponseError",
]


class NotFoundError(Exception):
    def __init__(self, message="Resource not found", resource=None):
        self.message = message
        self.resource = resource
        super().__init__(self.message)

    def __str__(self):
        if self.resource:
            return f"{self.message}: {self.resource}"
        return self.message


class ResponseError(Exception):
    def __init__(self, response: Response, message=""):
        self.response = response
        self.message = (
            f"ResponseError: {message} ({response.status_code} {response.text})"
        )
        super().__init__(self.message)

    def __str__(self):
        return self.message
