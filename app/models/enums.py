from enum import Enum


class CheckStatus(Enum):
    IN_PROGRESS = None
    NOCHANGE = 0
    UNAVAILABLE = 1
    MOVE_FOUND = 2
    BAD_QUALITY = 4
    FORBIDDEN = 5
