import asyncio
from os import environ
from collectors.base_collectors import BaseCollector
from exceptions.exceptions import CollectorTimeoutError
from models.enums import CheckStatus
from models.remotes import CheckResult


class PingCollector(BaseCollector):
    TIMEOUT_PING: float = float(environ.get("ping_timeout", default=10))
    collector_type = "ping"

    async def collect(self) -> CheckResult:
        result = CheckResult(check_status=CheckStatus.UNAVAILABLE)
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), self.TIMEOUT_PING
            )
        except (TimeoutError, OSError, asyncio.TimeoutError):
            raise CollectorTimeoutError(status=404, detail="Порт не доступен")
        else:
            if writer:
                writer.close()
                result.check_status = CheckStatus.NOCHANGE
        return result
