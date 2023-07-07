from typing import Type

from collectors.countmax_collector import CountMaxCollector
from collectors.base_collectors import BaseCollector
from collectors.ping_collector import PingCollector
from collectors.rtsp_collector import RtspCollector
from collectors.td_collector import TDCollector
from collectors.ts_collector import TSCollector
from collectors.wecktech_collector import WectechCollector
from collectors.xovis_collector import XovisCollector
from collectors.youtube_collector import YouTubeCollector


class CollectorFactory:
    def __init__(self):
        self._collectors = {}

    def register_collector(
        self, collector_type: str, collector_class: Type[BaseCollector]
    ):
        self._collectors[collector_type] = collector_class

    def get_collector(self, collector_type: str) -> Type[BaseCollector]:
        collector = self._collectors.get(collector_type)
        if collector is None:
            raise ValueError(f"Unknown collector type {collector_type}")
        return collector


factory = CollectorFactory()
factory.register_collector("rtsp", RtspCollector)
factory.register_collector("countmax", CountMaxCollector)
factory.register_collector("ping", PingCollector)
factory.register_collector("td", TDCollector)
factory.register_collector("ts", TSCollector)
factory.register_collector("wectech", WectechCollector)
factory.register_collector("youtube", YouTubeCollector)
factory.register_collector("xovis", XovisCollector)
