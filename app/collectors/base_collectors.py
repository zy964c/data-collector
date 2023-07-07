import aiobotocore
import aiohttp
import io
from os import environ

from botocore.exceptions import ClientError

from collectors import collectors_logger
from collectors.capture.video import VideoCaptureThreading
from exceptions.exceptions import SourceUnavailableException
from PIL import Image
from typing import Union, Tuple
from image_api_client.client import Client
from botocore.config import Config

from models.remotes import CheckResult
from settings import settings


RETRIES = int(environ.get("http_client_retries_number", default=5))


class BaseCollector:
    ip = None
    login = None
    password = None
    port = None
    collector_type = "base"

    def __init__(self, sensor_id: str, collect_type_id: str, client: Client) -> None:
        self.sensor_id = sensor_id
        self.collect_type_id = collect_type_id
        self.client = client

    @classmethod
    async def create(cls, sensor_id: str, collect_type_id: str, client: Client):
        self: BaseCollector = cls(sensor_id, collect_type_id, client)
        camera_data = await client.get_sensor_data()
        self.ip = camera_data["ip"]
        self.login = camera_data["login"]
        self.password = camera_data["password"]
        self.port = camera_data["port"]
        return self

    def collect(self) -> CheckResult:
        raise NotImplementedError


class HTTPMixin:
    TIMEOUT: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
        total=float(environ.get("sensor_timeout", default=10))
    )


class ImageManipulatorMixin:
    @staticmethod
    def bytes_to_image(images_bytes) -> Image:
        return Image.fromarray(images_bytes, mode="RGB")

    @staticmethod
    def bgr_to_rgb(image: Image) -> Image:
        b, g, r = image.split()
        dst = Image.merge("RGB", (r, g, b))
        return dst

    @staticmethod
    def to_bytes(image: Image, out_ext: str) -> bytes:
        f = io.BytesIO()
        image.save(f, out_ext)
        return f.getvalue()


class CVCollector(BaseCollector, ImageManipulatorMixin):
    collector_type = "cv"

    @staticmethod
    async def get_frame(url) -> Tuple[bytes, str]:
        ext = "PNG"
        async with VideoCaptureThreading(url) as vcap:
            if not vcap.isOpened():
                raise SourceUnavailableException(detail=f"Can not connect to {url}")
            ret, image = vcap.read()
            if image is None:
                raise SourceUnavailableException(detail=f"Can not connect to {url}")
        rgb_frame = CVCollector.bgr_to_rgb(CVCollector.bytes_to_image(image))
        image_bytes = CVCollector.to_bytes(rgb_frame, ext)
        collectors_logger.debug("Video capture was completed")
        if image_bytes:
            return image_bytes, ext.lower()
        raise SourceUnavailableException(detail=f"Can not connect to {url}")


class DBCollector(BaseCollector):
    collector_type = "db"

    async def collect_from_db(self) -> Union[CheckResult, None]:
        image_ids = await self.client.get_reference_image_id(reference=False)
        if image_ids:
            image_id = image_ids[0]["image_id"]
            image_ext = image_ids[0]["image_url"].split(".")[-1]
            ref_image_url = ".".join([image_id, image_ext])
            image_bytes = await self._get_file(ref_image_url)
            self.client.image_id = image_id
            result = CheckResult()
            result.image, result.extension = image_bytes, image_ext
            return result

    async def _get_file(self, filename: str) -> Union[bytes, None]:
        session = aiobotocore.get_session()
        async with session.create_client(
            "s3",
            region_name="msk",
            endpoint_url=settings.S3_ENDPOINT,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            use_ssl=False,
            config=Config(proxies={}),
        ) as client:
            try:
                response = await client.get_object(
                    Bucket=settings.AWS_BUCKET_NAME, Key=filename
                )
                async with response["Body"] as stream:
                    return await stream.read()
            except ClientError as ex:
                if ex.response['Error']['Code'] == 'NoSuchKey':
                    collectors_logger.warning(f"{filename}: {ex}")
                    return None
