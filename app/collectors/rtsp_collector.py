import logging
import urllib
from urllib.parse import urlparse

from aiortsp.rtsp.connection import RTSPConnection
from aiortsp.rtsp.errors import RTSPResponseError, RTSPConnectionError
from aiortsp.rtsp.session import RTSPMediaSession
from aiortsp.transport import transport_for_scheme

from collectors.base_collectors import CVCollector, DBCollector
from exceptions.exceptions import ForbiddenError, SourceUnavailableException, UnauthorizedError
from models.remotes import CheckResult

logger = logging.getLogger("collector_app.RtspCollector")


class RtspCollector(CVCollector, DBCollector):
    collector_type = "rtsp"

    async def __send_describe(self, media_url):
        """
        Used to check if login and password are valid
        """
        p_url = urlparse(media_url)
        async with RTSPConnection(
                p_url.hostname, p_url.port or 554,
                p_url.username, urllib.parse.unquote(p_url.password),
                logger=logger
        ) as conn:
            transport_class = transport_for_scheme(p_url.scheme)
            async with transport_class(conn, logger=logger) as transport:
                async with RTSPMediaSession(conn, media_url, transport=transport, logger=logger) as sess:
                    await sess._send('DESCRIBE', headers={
                        'Accept': 'application/sdp'
                    })

    async def test_connection(self, url):
        try:
            await self.__send_describe(url)
            return True
        except RTSPResponseError as err:
            logger.error(err)
            if err.reason().get('status') == 401:
                raise UnauthorizedError()
        except RTSPConnectionError as err:
            raise SourceUnavailableException(detail=str(err))

    def prepare_rtsp_url(self) -> str:
        if self.login and self.password:
            url = f"{self.login}:{urllib.parse.quote(self.password)}@{self.ip}:{554}/Streaming/Channels/101"
        else:
            url = f"{self.ip}:{554}/Streaming/Channels/101"
        return f'rtsp://{url}'

    async def collect(self) -> CheckResult:
        url = self.prepare_rtsp_url()
        await self.test_connection(url)
        result = CheckResult()
        result.image, result.extension = await self.get_frame(url)
        return result
