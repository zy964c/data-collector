import asyncio
import base64
from typing import Tuple, Type, Union

import aiohttp
import backoff

from collectors import collectors_logger
from collectors.base_collectors import RETRIES, HTTPMixin, DBCollector, BaseCollector
from exceptions.exceptions import ForbiddenError, UnauthorizedError
from image_api_client.client import Client
from models.remotes import CheckResult
from settings.settings import TD_DELAY


class TDCollector(HTTPMixin, DBCollector):
    collector_type = "td"

    @classmethod
    async def create(cls, sensor_id: str, collect_type_id: str, client: Client):
        self: BaseCollector = cls(sensor_id, collect_type_id, client)
        camera_data = await client.get_sensor_data()
        self.ip = camera_data["ip"]
        if camera_data.get("login"):
            self.login = base64.b64encode(camera_data["login"].encode()).decode()
        else:
            self.login = camera_data.get("login")
        if camera_data.get("password"):
            self.password = base64.b64encode(camera_data["password"].encode()).decode()
        else:
            self.password = camera_data.get("password")
        self.port = camera_data["port"]
        return self

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def collect(self) -> Union[CheckResult, None]:
        login_url = f"http://{self.ip}/login"
        image_url = f"http://{self.ip}/video_feed/1?0.04008162014960104"
        try:
            login_form = {"username": self.login, "password": self.password}
            async with aiohttp.ClientSession(
                timeout=self.TIMEOUT, raise_for_status=True
            ) as session:
                async with session.post(login_url, data=login_form) as reg_resp:
                    if reg_resp.status == 200:
                        await asyncio.sleep(TD_DELAY)
                        async with session.get(image_url) as resp:
                            if resp.status == 200:
                                result = CheckResult()
                                result.image, result.extension = (
                                    await resp.read(),
                                    "png",
                                )
                                return result

        except Exception as ex:
            collectors_logger.warning(ex)
            raise ex
