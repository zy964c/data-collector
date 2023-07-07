import asyncio
import time
from typing import Union
import aiohttp
import backoff

from collectors import collectors_logger
from collectors.base_collectors import RETRIES, HTTPMixin, DBCollector
from exceptions.exceptions import ForbiddenError, UnauthorizedError
from models.remotes import CheckResult
from settings.settings import WECTECH_DELAY


class WectechCollector(HTTPMixin, DBCollector):

    collector_type = "wectech"

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def collect(self) -> Union[None, CheckResult]:
        ts = int(time.time())
        register_url = f"http://{self.ip}/registerClient.cgi"
        image_url = f"http://{self.ip}/rightImage.jpg"
        try:
            params = {"_time": ts}
            auth = aiohttp.BasicAuth(self.login, self.password)
            async with aiohttp.ClientSession(
                timeout=self.TIMEOUT, auth=auth, raise_for_status=True
            ) as session:
                async with session.post(
                    register_url, data="uid=9475608a80164b5b&image1=2"
                ) as reg_resp:
                    if reg_resp.status == 200:
                        await asyncio.sleep(WECTECH_DELAY)
                        async with session.get(image_url, params=params) as resp:
                            if resp.status == 200:
                                result = CheckResult()
                                result.image, result.extension = (
                                    await resp.read(),
                                    "jpg",
                                )
                                return result

        except Exception as ex:
            collectors_logger.warning(ex)
            raise ex
