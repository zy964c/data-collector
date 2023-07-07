from typing import Union

import pafy
from collectors import collectors_logger
from collectors.base_collectors import CVCollector, DBCollector
from models.remotes import CheckResult


class YouTubeCollector(CVCollector, DBCollector):
    collector_type = "youtube"

    async def collect(self) -> Union[CheckResult, None]:
        the_best_stream = None
        max_pixels = 0
        if "https" not in self.ip:
            self.ip = f"https://{self.ip}"
        collectors_logger.info(self.ip)
        p = pafy.new(self.ip)
        for stream in p.streams:
            total_pixels = int(stream.dimensions[0]) * int(stream.dimensions[1])
            if total_pixels > max_pixels:
                the_best_stream = stream
        if the_best_stream:
            collectors_logger.info(the_best_stream.url)
            result = CheckResult()
            result.image, result.extension = await CVCollector.get_frame(the_best_stream.url)
            return result
