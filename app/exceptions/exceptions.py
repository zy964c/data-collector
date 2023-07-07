import re

from models.enums import CheckStatus


class CollectorError(Exception):
    """Base class for other exceptions"""

    def __init__(self, status: int = None, detail: str = None) -> None:
        self.status = status
        self.detail = detail

    def _hide_credentials(self, detail) -> str:
        if detail and type(detail) == str:
            p = re.compile(r"/.+:.+@")
            matches = p.findall(detail)
            if matches:
                return detail.replace(matches[0], "//*:*@")
        return detail

    def __str__(self):
        return self._hide_credentials(self.detail)


class IncorrectPathError(CollectorError):
    pass


class SourceUnavailableException(CollectorError):
    def __init__(self, detail: str = None) -> None:
        self.status = CheckStatus.UNAVAILABLE
        self.detail = detail


class ApiClientError(CollectorError):
    def __init__(
        self,
        status: int = CheckStatus.BAD_QUALITY,
        detail: str = "Image Api Client error",
    ) -> None:
        self.status = status
        self.detail = detail


class CollectorTimeoutError(CollectorError):
    pass


class NoReferenceImageError(CollectorError):
    def __init__(
        self,
        status: int = CheckStatus.NOCHANGE,
        detail: str = "No reference image for camera",
    ) -> None:
        self.status = status
        self.detail = detail


class ForbiddenError(CollectorError):
    def __init__(
            self,
            status: int = CheckStatus.FORBIDDEN,
            detail: str = "Wrong credentials",
    ) -> None:
        self.status = status
        self.detail = detail


class UnauthorizedError(CollectorError):
    def __init__(
            self,
            status: int = CheckStatus.FORBIDDEN,
            detail: str = "Unauthorized",
    ) -> None:
        self.status = status
        self.detail = detail
