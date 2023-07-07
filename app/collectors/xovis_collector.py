import io
import aiohttp
import backoff
import time

from collectors.base_collectors import RETRIES, HTTPMixin, DBCollector, ImageManipulatorMixin
from models.remotes import CheckResult
from typing import Tuple, Union
from PIL import Image


class XovisCollector(DBCollector, HTTPMixin, ImageManipulatorMixin):
    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def collect(self) -> Union[None, Tuple[bytes, str]]:
        ts = int(time.time())
        token = ''
        url = f"http://{self.ip}/api/auth/token"
        if self.login in ('Администратор', 'Administrator'):
            self.login = 'admin'
        auth = aiohttp.BasicAuth(self.login, self.password)
        async with aiohttp.ClientSession(
            timeout=self.TIMEOUT, raise_for_status=True
        ) as session:
            async with session.get(url, auth=auth) as resp:
                if resp.status == 200:
                    token = await resp.text()
            params = {"packed": "false", "nct": ts}
            url = f"http://{self.ip}/api/validation"
            headers = {'Authorization': f'Bearer {token}'}
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    result = CheckResult()
                    data = await resp.read()
                    image_bmp = Image.open(io.BytesIO(data))
                    image_png = self.to_bytes(image=image_bmp, out_ext='png')
                    result.image, result.extension = (
                        image_png,
                        "png",
                    )
                    return result
