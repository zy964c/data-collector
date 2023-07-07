from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from models.enums import CheckStatus


class ImageApiResponse(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    size_x: Optional[float] = None
    size_y: Optional[float] = None
    rotation: Optional[float] = None
    shear: Optional[float] = None
    ping: Optional[bool] = None
    api_version: int = 2
    match_image_id: Optional[UUID] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    matches: Optional[str] = None


class CheckResult(BaseModel):
    check_status: Optional[CheckStatus] = CheckStatus.IN_PROGRESS
    image: Optional[bytes] = None
    extension: Optional[str] = None
