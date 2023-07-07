import asyncio
import concurrent
import cv2

from functools import partial
from os import environ
from exceptions.exceptions import SourceUnavailableException


RETRIES_NUMBER = int(environ.get("retries_number"))


class VideoCaptureThreading:
    def __init__(self, src=0, width=640, height=480):
        self.src = src
        self.width = width
        self.height = height
        self.grabbed, self.frame = None, None
        self.cap = None

    async def start(self):
        await self.update()
        return self

    async def update(self):
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            self.cap = await loop.run_in_executor(pool, partial(cv2.VideoCapture, self.src))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            for i in range(RETRIES_NUMBER):
                self.grabbed, self.frame = await loop.run_in_executor(
                    pool, self.cap.read)
                if self.frame is not None:
                    break
                await asyncio.sleep(RETRIES_NUMBER)

    def read(self):
        if self.frame is None:
            raise SourceUnavailableException(
                f"No frames was gotten from the source {self.src}"
            )
        frame = self.frame.copy()
        grabbed = self.grabbed
        return grabbed, frame

    def isOpened(self):
        return self.cap.isOpened()

    async def __aenter__(self):
        return await self.start()

    async def __aexit__(self, exec_type, exc_value, traceback):
        self.cap.release()
