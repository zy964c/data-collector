import numpy
import pytest

from exceptions.exceptions import SourceUnavailableException


@pytest.mark.asyncio
class TestVideoCaptureThreading:

    @pytest.mark.parametrize("url", ['./collectors/capture/tests/test_video.mov', ''])
    async def test_read(self, url):
        from collectors.capture.video import VideoCaptureThreading
        if url:
            async with VideoCaptureThreading(url) as vcap:
                ret, image = vcap.read()
                assert vcap.isOpened()
                assert await vcap.start() is not None
            assert type(image) == numpy.ndarray
        else:
            with pytest.raises(SourceUnavailableException):
                async with VideoCaptureThreading(url) as vcap:
                    vcap.read()
