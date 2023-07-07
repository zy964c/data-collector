import io
import time
from typing import Tuple, Union

import PIL
import aiohttp
import backoff
from PIL import Image

from collectors.base_collectors import RETRIES, HTTPMixin, DBCollector, ImageManipulatorMixin
from models.remotes import CheckResult


class CountMaxCollector(DBCollector, HTTPMixin, ImageManipulatorMixin):
    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def collect(self) -> Union[None, Tuple[bytes, str]]:
        ts = int(time.time())
        params = {"passwd": self.password, "nct": ts}
        url = f"http://{self.ip}/api/scene/rectl"
        async with aiohttp.ClientSession(
                timeout=self.TIMEOUT
        ) as session:
            async with session.get(url, params=params, raise_for_status=True) as resp:
                if resp.status == 200:
                    result = CheckResult()
                    data = await resp.read()
                    image_bmp = Image.open(io.BytesIO(data))
                    image_jpg = self.to_bytes(image=image_bmp, out_ext='png')
                    result.image, result.extension = (
                        image_jpg,
                        "png",
                    )
                    return result
