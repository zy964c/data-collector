import asyncio
import uuid
from unittest.mock import AsyncMock

import aiobotocore
import aiohttp
import pytest
import numpy

from PIL import Image
from asynctest import CoroutineMock, MagicMock, patch, create_autospec, ANY, DEFAULT
from exceptions.exceptions import SourceUnavailableException, CollectorTimeoutError, ForbiddenError
from models.enums import CheckStatus
from models.remotes import CheckResult
from aiohttp import ClientResponseError


class TestCollectorFactory:
    @pytest.fixture
    def collector_factory(self):
        from collectors.factories import CollectorFactory
        from collectors.youtube_collector import YouTubeCollector
        from collectors.ts_collector import TSCollector
        from collectors.rtsp_collector import RtspCollector
        from collectors.ping_collector import PingCollector
        from collectors.countmax_collector import CountMaxCollector
        from collectors.wecktech_collector import WectechCollector
        from collectors.td_collector import TDCollector

        factory = CollectorFactory()
        factory.register_collector("wechtech", WectechCollector)
        factory.register_collector("countmax", CountMaxCollector)
        factory.register_collector("td", TDCollector)
        factory.register_collector("rtsp", RtspCollector)
        factory.register_collector("ping", PingCollector)
        factory.register_collector("ts", TSCollector)
        factory.register_collector("youtube", YouTubeCollector)
        return factory

    def test_collector_factory(self, collector_factory):
        from collectors.td_collector import TDCollector

        assert collector_factory.get_collector("td") == TDCollector
        with pytest.raises(ValueError):
            collector_factory.get_collector("dummy")


@pytest.mark.asyncio
class TestBaseCollector:
    error = aiohttp.ClientResponseError(request_info=aiohttp.RequestInfo(url='',
                                                                         method='GET',
                                                                         headers={}), history=())

    @pytest.fixture()
    def sensor_id(self):
        return uuid.uuid4()

    @pytest.fixture()
    def client(self, mocker, sensor_id):
        client_response = CoroutineMock(
            return_value={
                "ip": "test.com/video",
                "port": "80",
                "login": "test",
                "password": "test_password",
            }
        )
        client_get_reference_image_id = CoroutineMock(
            side_effect=[
                [
                    {
                        "sensor_id": "940ce133-2d8c-4695-ad89-a64ceaf7e621",
                        "image_id": "a0a81a0e-c5c6-43ac-8d64-b7038ba1f163",
                        "image_url": "http://10.10.77.29:9001/malltech/a0a81a0e-c5c6-43ac-8d64-b7038ba1f163.png",
                        "date_created": "2020-03-05T06:53:32.692941",
                    }
                ],
                None,
            ]
        )
        from image_api_client.client import Client

        mocker.patch.object(Client, "get_sensor_data", client_response)
        mocker.patch.object(
            Client, "get_reference_image_id", client_get_reference_image_id
        )
        return Client(sensor_id)

    @pytest.fixture()
    def aiohttp_mocks(self, mocker):
        mock_get = MagicMock()
        mock_post = MagicMock()
        mocker.patch('aiohttp.ClientSession.get', new=mock_get)
        mocker.patch('aiohttp.ClientSession.post', new=mock_post)
        yield mock_get, mock_post
        mock_get.reset_mock()
        mock_post.reset_mock()

    async def get_collector_instance(self, klass, sensor_id, client=None):
        from image_api_client.client import Client

        if not client:
            return await klass.create(
                sensor_id=str(sensor_id),
                collect_type_id="testid",
                client=Client(sensor_id),
            )
        else:
            return await klass.create(
                sensor_id=str(sensor_id), collect_type_id="testid", client=client
            )

    @pytest.fixture()
    async def collector(self, sensor_id, client):
        async def _collector(collector_class):
            return await self.get_collector_instance(collector_class, sensor_id, client)

        return _collector

    @pytest.fixture()
    def image(self) -> Image:
        return Image.new("RGB", (60, 30), color=(73, 109, 137))

    async def test_base_collector(self, collector):
        from collectors.base_collectors import BaseCollector
        collector = await collector(BaseCollector)
        with pytest.raises(NotImplementedError):
            await collector.collect()


class TestTDCollector(TestBaseCollector):
    @pytest.mark.asyncio
    async def test_create(self, mocker, sensor_id):
        from image_api_client.client import Client

        client_response = CoroutineMock(
            return_value={
                "ip": "test.com/video",
                "port": "80",
                "login": "test",
                "password": "test_password",
            }
        )
        mocker.patch.object(Client, "get_sensor_data", client_response)
        from collectors.td_collector import TDCollector

        td = await self.get_collector_instance(TDCollector, sensor_id)
        assert td.login == "dGVzdA=="
        assert td.password == "dGVzdF9wYXNzd29yZA=="
        client_response = CoroutineMock(
            return_value={
                "ip": "test.com/video",
                "port": "80",
                "login": None,
                "password": None,
            }
        )
        mocker.patch.object(Client, "get_sensor_data", client_response)
        from collectors.td_collector import TDCollector

        td = await self.get_collector_instance(TDCollector, sensor_id)
        assert td.login is None
        assert td.password is None

    @pytest.mark.parametrize("status", [200])
    async def test_td_collector(self, collector, image, status, aiohttp_mocks):
        from collectors.td_collector import TDCollector
        from collectors.base_collectors import ImageManipulatorMixin
        collector = await collector(TDCollector)
        image_bytes = ImageManipulatorMixin.to_bytes(image, "png")
        mock_get, mock_post = aiohttp_mocks
        mock_get.return_value.__aenter__.return_value.status = status
        mock_post.return_value.__aenter__.return_value.status = status
        mock_get.return_value.__aenter__.return_value.read = CoroutineMock(return_value=image_bytes)
        if status == 200:
            assert await collector.collect() == CheckResult(image=image_bytes, extension="png")
            mock_post.assert_called_with(f"http://{collector.ip}/login",
                                         data={"username": collector.login, "password": collector.password})
            mock_get.assert_called_with(f"http://{collector.ip}/video_feed/1?0.04008162014960104")


@pytest.mark.asyncio
class TestCVCollector(TestBaseCollector):
    async def test_bgr_to_rgb(self, collector, image: Image):
        from collectors.base_collectors import CVCollector
        import numpy

        collector = await collector(CVCollector)
        assert (
                collector.bgr_to_rgb(collector.bytes_to_image(numpy.array(image))).mode
                == "RGB"
        )

    async def test_to_bytes(self, collector, image: Image):
        from collectors.base_collectors import CVCollector

        collector = await collector(CVCollector)
        assert type(collector.to_bytes(image, "png")) == bytes

    async def test_bytes_to_image(self, collector, image: Image):
        from collectors.base_collectors import CVCollector

        collector = await collector(CVCollector)
        from PIL.Image import Image

        assert type(collector.bytes_to_image(numpy.array(image))) == Image

    @pytest.mark.parametrize("case", [*range(4)])
    async def test_get_frame(self, collector, image: Image, mocker, case):
        from collectors.base_collectors import CVCollector

        collector = await collector(CVCollector)
        mock = mocker.patch(
            "collectors.base_collectors.VideoCaptureThreading"
        )
        coroutine_mock = mock.return_value.__aenter__ = CoroutineMock()
        coroutine_mock.return_value.read.return_value = (
            "",
            numpy.array(image),
        )
        mock.return_value.__aexit__ = CoroutineMock(return_value=None)
        if not case:
            assert await collector.get_frame("url") == (
                collector.to_bytes(collector.bgr_to_rgb(image), "PNG"),
                "png",
            )
        elif case == 1:
            mock = mocker.patch(
                "collectors.base_collectors.VideoCaptureThreading"
            )
            coroutine_mock = mock.return_value.__aenter__ = CoroutineMock()
            coroutine_mock.return_value.read.return_value = (
                "",
                None,
            )
            mock.return_value.__aexit__ = CoroutineMock(return_value=None)
            with pytest.raises(SourceUnavailableException):
                await collector.get_frame("url")
        elif case == 2:
            mock = mocker.patch(
                "collectors.base_collectors.VideoCaptureThreading"
            )
            coroutine_mock = mock.return_value.__aenter__ = CoroutineMock()
            coroutine_mock.return_value.isOpened.return_value = False
            mock.return_value.__aexit__ = CoroutineMock(return_value=None)
            with pytest.raises(SourceUnavailableException):
                await collector.get_frame("url")
        else:
            mocker.patch(
                "collectors.base_collectors.CVCollector.to_bytes"
            ).return_value = None
            with pytest.raises(SourceUnavailableException):
                await collector.get_frame("url")


@pytest.mark.asyncio
class TestDBCollector(TestBaseCollector):
    @pytest.mark.parametrize("case", [*range(2)])
    async def test_get_file(self, collector, image, mocker, case):
        from collectors.base_collectors import DBCollector, ImageManipulatorMixin

        db_collector = await collector(DBCollector)
        image_bytes = ImageManipulatorMixin.to_bytes(image, "png")
        get_session_mock = MagicMock()
        read_mock = MagicMock()
        get_object_mock = CoroutineMock()
        if case:
            get_object_mock.return_value = {"Body": read_mock}
            get_object_mock.side_effect = None
        else:
            from botocore.exceptions import ClientError
            get_object_mock.side_effect = ClientError(error_response={"Error": {"Code": "NoSuchKey", "Message": "Not Found"}},
                                                      operation_name="my_operation",)
        read_result_mock = CoroutineMock(return_value=image_bytes)
        read_mock.__aenter__.return_value.read = read_result_mock
        boto_mock = mocker.patch("collectors.base_collectors.aiobotocore")
        boto_mock.get_session.return_value = get_session_mock
        get_session_mock.create_client.return_value.__aenter__.return_value.get_object = (
            get_object_mock
        )
        if case:
            assert await db_collector._get_file("filename") == image_bytes
            get_object_mock.assert_awaited_with(Bucket="bucket", Key="filename")
            get_session_mock.create_client.assert_called()
            read_result_mock.assert_awaited()
        else:
            assert await db_collector._get_file("filename") is None

    async def test_collect_from_db(self, collector, image, mocker):
        from collectors.base_collectors import DBCollector

        db_collector = await collector(DBCollector)
        from collectors.base_collectors import ImageManipulatorMixin
        image_bytes = ImageManipulatorMixin.to_bytes(image, "png")
        get_file_mock = CoroutineMock(return_value=image_bytes)
        mocker.patch.object(db_collector, "_get_file", get_file_mock)
        assert await db_collector.collect_from_db() == CheckResult(
            image=image_bytes, extension="png"
        )
        get_file_mock.assert_awaited_once_with(
            "a0a81a0e-c5c6-43ac-8d64-b7038ba1f163.png"
        )
        assert await db_collector.collect_from_db() is None


@pytest.mark.asyncio
class TestCountMaxCollectors(TestBaseCollector):
    @pytest.mark.parametrize("status", [200])
    async def test_countmax_collector(self, collector, image, aiohttp_mocks, status):
        from collectors.countmax_collector import CountMaxCollector
        from collectors.base_collectors import ImageManipulatorMixin
        collector = await collector(CountMaxCollector)
        image_bytes = ImageManipulatorMixin.to_bytes(image, "png")
        mock_get, _ = aiohttp_mocks
        mock_get.return_value.__aenter__.return_value.status = status
        mock_get.return_value.__aenter__.return_value.read = CoroutineMock(return_value=image_bytes)
        if status == 200:
            assert await collector.collect() == CheckResult(image=image_bytes, extension="png")
            mock_get.assert_called_with(f"http://{collector.ip}/api/scene/rectl",
                                        params={"passwd": collector.password,
                                                "nct": ANY}, raise_for_status=True)


@pytest.mark.asyncio
class TestWectechCollector(TestBaseCollector):
    @pytest.mark.parametrize("status", [200])
    async def test_wectech_collector(self, collector, image, aiohttp_mocks, status):
        from collectors.wecktech_collector import WectechCollector
        from collectors.base_collectors import ImageManipulatorMixin
        collector = await collector(WectechCollector)
        image_bytes = ImageManipulatorMixin.to_bytes(image, "png")
        mock_get, mock_post = aiohttp_mocks
        mock_get.return_value.__aenter__.return_value.status = status
        mock_post.return_value.__aenter__.return_value.status = status
        mock_get.return_value.__aenter__.return_value.read = CoroutineMock(return_value=image_bytes)
        if status == 200:
            assert await collector.collect() == CheckResult(image=image_bytes, extension="jpg")
            mock_post.assert_called_with(f"http://{collector.ip}/registerClient.cgi",
                                         data="uid=9475608a80164b5b&image1=2")
            mock_get.assert_called_with(f"http://{collector.ip}/rightImage.jpg",
                                        params={"_time": ANY})


@pytest.mark.asyncio
class TestPingCollectors(TestBaseCollector):
    async def test_ping_collectors(self, collector, mocker):
        from collectors.ping_collector import PingCollector
        collector = await collector(PingCollector)
        mock = mocker.patch('asyncio.wait_for', new=CoroutineMock())
        mock.return_value = MagicMock(), MagicMock()
        assert await collector.collect() == CheckResult(check_status=CheckStatus.NOCHANGE)
        mock.assert_awaited_once_with(ANY, collector.TIMEOUT_PING)
        mock.return_value = MagicMock(), None
        assert await collector.collect() == CheckResult(check_status=CheckStatus.UNAVAILABLE)
        errors = (TimeoutError, OSError, asyncio.TimeoutError)
        for error in errors:
            mock.side_effect = error
            with pytest.raises(CollectorTimeoutError):
                await collector.collect()
        mock.side_effect = aiohttp.ClientConnectionError
        with pytest.raises(aiohttp.ClientConnectionError):
            await collector.collect()


@pytest.mark.asyncio
class TestTsCollectors(TestBaseCollector):
    @pytest.mark.parametrize("status", [200])
    async def test_ts_collector(self, collector, image, status, aiohttp_mocks, mocker):
        from collectors.ts_collector import TSCollector
        from collectors.base_collectors import ImageManipulatorMixin
        playlist = """#EXTM3U
                    #EXT-X-TARGETDURATION:7
                    #EXT-X-VERSION:3
                    #EXT-X-MEDIA-SEQUENCE:310827
                    #EXT-X-PROGRAM-DATE-TIME:2020-04-16T11:14:59Z
                    #EXTINF:6.000,
                    2020/04/16/11/14/59-06000.ts
                    #EXTINF:6.000,
                    2020/04/16/11/15/05-06000.ts
                    #EXTINF:6.009,
                    2020/04/16/11/15/11-06009.ts
                    #EXTINF:6.000,
                    2020/04/16/11/15/17-06000.ts"""
        collector = await collector(TSCollector)
        path = collector.ip.split("/")
        image_bytes = ImageManipulatorMixin.to_bytes(image, "png")
        mock_get, _ = aiohttp_mocks
        mock_get.return_value.__aenter__.return_value.status = status
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(return_value=playlist)
        if status == 200:
            mock_get_frame = mocker.patch('collectors.ts_collector.TSCollector.get_frame')
            mock_get_frame.return_value = image_bytes, 'png'
            assert await collector.collect() == CheckResult(image=image_bytes, extension="png")
            mock_get.assert_called_with(f'https://{path[0]}:{collector.port}/{"/".join(path[1:])}',
                                        headers=ANY, ssl=False)
            mock_get_frame.assert_called_with(f"https://{path[0]}:{collector.port}/"
                                              f"{path[1]}/2020/04/16/11/15/17-06000.ts")


@pytest.mark.asyncio
class TestRTSPCollectors(TestBaseCollector):
    async def test_prepare_rtsp_url(self, collector):
        from collectors.rtsp_collector import RtspCollector
        collector = await collector(RtspCollector)
        assert collector.prepare_rtsp_url() ==\
               f"rtsp://{collector.login}:{collector.password}@{collector.ip}:{554}/Streaming/Channels/101"
        collector.login = None
        assert collector.prepare_rtsp_url() == \
               f"rtsp://{collector.ip}:{554}/Streaming/Channels/101"

    async def test_rtsp_collector(self, image, collector, mocker):
        from collectors.rtsp_collector import RtspCollector
        from collectors.base_collectors import ImageManipulatorMixin
        collector = await collector(RtspCollector)
        image_bytes = ImageManipulatorMixin.to_bytes(image, "png")
        mocker.patch('collectors.rtsp_collector.RtspCollector.get_frame',
                     new=CoroutineMock(return_value=(image_bytes, 'png')))
        mocker.patch('collectors.rtsp_collector.RtspCollector.test_connection',
                     new=CoroutineMock(return_value=True))
        assert await collector.collect() == CheckResult(image=image_bytes, extension="png")


@pytest.mark.asyncio
class TestYoutubeCollectors(TestBaseCollector):
    async def test_youtube_collector(self, image, collector, mocker):
        from collectors.youtube_collector import YouTubeCollector
        from collectors.base_collectors import ImageManipulatorMixin
        collector = await collector(YouTubeCollector)
        image_bytes = ImageManipulatorMixin.to_bytes(image, "png")
        mock_pafy = mocker.patch('pafy.new')
        stream_low = MagicMock(dimensions=(640, 480), url='low_resolution')
        stream_hd = MagicMock(dimensions=(1920, 1080), url='high_resolution')
        mock_pafy.return_value.streams = [stream_low, stream_hd]
        mock_get_frame = mocker.patch('collectors.youtube_collector.CVCollector.get_frame')
        mock_get_frame.return_value = image_bytes, 'png'
        assert await collector.collect() == CheckResult(image=image_bytes, extension="png")
        mock_get_frame.assert_called_with('high_resolution')
        assert "https" in collector.ip
        mock_pafy.return_value.streams = []
        assert await collector.collect() is None
