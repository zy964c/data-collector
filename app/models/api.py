from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class Item(BaseModel):
    sensor_id: UUID
    collect_type_id: Optional[UUID]
    use_db: Optional[bool] = False
