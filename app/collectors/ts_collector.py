from typing import Union

import aiohttp

from collectors import collectors_logger
from collectors.base_collectors import CVCollector, HTTPMixin, DBCollector
from exceptions.exceptions import ForbiddenError, UnauthorizedError
from models.remotes import CheckResult


class TSCollector(CVCollector, HTTPMixin, DBCollector):
    collector_type = "ts"

    async def collect(self) -> Union[CheckResult, None]:
        video = ""
        path = self.ip.split("/")
        playlist_url = f'https://{path[0]}:{self.port}/{"/".join(path[1:])}'
        collectors_logger.info(playlist_url)
        headers = {
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
            " Chrome/79.0.3945.130 Safari/537.36",
            "Accept": "*/*",
            "Origin": "https://www.webcamtaxi.com",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Referer": "https://www.webcamtaxi.com/en/russia/sochi/shopping-mall.html",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "ru,en-US;q=0.9,en;q=0.8,ru-RU;q=0.7",
        }
        async with aiohttp.ClientSession(
            timeout=self.TIMEOUT, raise_for_status=True
        ) as session:
            async with session.get(playlist_url, headers=headers, ssl=False) as resp:
                if resp.status == 200:
                    playlist = await resp.text()
                    entries = playlist.split("\n")[::-1]
                    collectors_logger.debug(entries)
                    for entry in entries:
                        if entry and not entry.startswith('#'):
                            video = entry.strip()
                            break
                    url = f"https://{path[0]}:{self.port}/{path[1]}/{video}"
                    collectors_logger.info(url)
                    result = CheckResult()
                    result.image, result.extension = await self.get_frame(url)
                    return result
