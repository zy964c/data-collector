import asyncio
import json
import random
import aiohttp
import base64
import logging
import backoff
import uuid

from functools import partial
from io import BytesIO
from os import environ
from exceptions.exceptions import ApiClientError, NoReferenceImageError
from typing import Dict, Tuple, List, Optional
from uuid import UUID
from models.encoders import UUIDEncoder
from models.remotes import ImageApiResponse
from settings import settings
from PIL import Image

IMAGE_API_URL = environ.get("image_api_url")
CAMERA_GUARD_BASE = settings.CAMERA_GUARD_BASE

client_logger = logging.getLogger("collector_app.client_logger")

RETRIES = int(environ.get("http_client_retries_number", default=5))


def strip_image_prefix(base64_data: str):
    # data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD
    split_data = base64_data.split(",")
    if len(split_data) == 2:
        return split_data[1]
    else:
        return base64_data


def image_from_string(base64_data: str):
    return base64.b64decode(strip_image_prefix(base64_data))


def get_im_size(image: bytes) -> Tuple[int, int]:
    try:
        f = BytesIO(image)
        im = Image.open(f)
        return im.size
    except Exception as e:
        client_logger.exception(e)
        return None, None


class Client:
    TIMEOUT = aiohttp.ClientTimeout(
        total=float(environ.get("sensor_timeout", default=10))
    )
    TOKEN = None

    def __init__(self, sensor_id: UUID) -> None:
        self.sensor_id = sensor_id
        self._image_id = None
        self.headers = {"Authorization": f"{settings.TOKEN_TYPE} {settings.TOKEN}"}
        self.comp = random.random()

    def __lt__(self, y):
        return self.comp < y.comp

    @property
    def image_id(self) -> str:
        return self._image_id

    @image_id.setter
    def image_id(self, image_id):
        self._image_id = image_id

    async def post_data(self, url, payload={}):
        client_logger.debug(f"POST for {url}")
        async with aiohttp.ClientSession(
                timeout=Client.TIMEOUT,
                headers=self.headers,
                json_serialize=partial(json.dumps, cls=UUIDEncoder),
        ) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    client_logger.warning(
                        f"Got response with status {resp.status} and body {await resp.text()}"
                    )

    async def get_data(self, url, params=None) -> ImageApiResponse:
        client_logger.debug(f"GET for {url}")
        async with aiohttp.ClientSession(
                timeout=Client.TIMEOUT, headers=self.headers
        ) as session:
            async with session.get(url, params=params) as resp:
                return await resp.json()

    async def insert_first_reference_image(self, image, ext):
        self._image_id = await self.insert_image(image, ext=ext)
        await self.insert_reference_image(self._image_id)

    async def get_reference_image(self):
        reference_image_ids = await self.get_reference_image_id()
        if not reference_image_ids:
            raise NoReferenceImageError()
        client_logger.debug(reference_image_ids)
        reference_image = await self.get_image(reference_image_ids[0]["image_url"])
        masks = reference_image_ids[0].get("mask")
        client_logger.debug(f"MASKS: {masks}")
        return reference_image, masks

    async def request_to_detector_api(self,
                                      data: dict,
                                      api_version: int,
                                      height: int,
                                      width: int) -> ImageApiResponse:
        url = f"{IMAGE_API_URL}{api_version}/movement"
        client_logger.debug(url)
        async with aiohttp.ClientSession(timeout=Client.TIMEOUT) as session:
            async with session.post(url, json=data, ssl=False) as resp:
                resp_json = await resp.json()
                if resp.status != 200:
                    detail = resp_json.get("detail", "image_api_error")
                    raise ApiClientError(detail=detail)
                resp = ImageApiResponse(image_height=height,
                                        image_width=width,
                                        **resp_json)
                if resp.matches:
                    img = image_from_string(resp.matches)
                    resp.match_image_id = await self.insert_image(
                        image=img
                    )
                return resp

    def __prepare_movement_request_data(self, reference_image, test_image, masks):
        data_api = {
            "ref_image": base64.b64encode(reference_image).decode("utf-8"),
            "test_image": base64.b64encode(test_image).decode("utf-8"),
            "return_matches": True,
            "mask": []
        }
        if masks:
            data_api["mask"] = masks
        return data_api

    async def prepare_data_select_api_and_make_request(self,
                                                       test_image: bytes,
                                                       reference_image: bytes,
                                                       masks: List) -> ImageApiResponse:
        image_width, image_height = get_im_size(test_image)
        data_api = self.__prepare_movement_request_data(reference_image, test_image, masks)
        for api_version in settings.API_VERSIONS:
            try:
                image_api_response = await self.request_to_detector_api(data_api,
                                                                        api_version,
                                                                        image_height,
                                                                        image_width)
            except aiohttp.ClientError as e:
                client_logger.exception(e)
                if api_version != settings.API_VERSIONS[-1]:
                    continue
                detail = "image_api_error"
                raise ApiClientError(detail=detail)
        return image_api_response

    @staticmethod
    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def get_image(url: str) -> bytes:
        try:
            async with aiohttp.ClientSession(timeout=Client.TIMEOUT) as session:
                async with session.get(url) as resp:
                    return await resp.read()
        except Exception as e:
            client_logger.exception(e)

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def get_reference_image_id(self, reference=True) -> Dict:
        """
        If reference is False this function returns the last image which is not necessary set as reference
        """
        url = f"{CAMERA_GUARD_BASE}/api/v1/images/"
        if reference:
            url += "reference/"
        params = {"sensor_id": str(self.sensor_id)}
        return await self.get_data(url, params)

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def insert_image(self, image: bytes, ext: str = "jpg") -> UUID:
        image_id = uuid.uuid4()
        url = f"{CAMERA_GUARD_BASE}/api/v1/images/"
        payload = {
            "id": image_id,
            "image": base64.b64encode(image).decode("utf-8"),
            "ext": ext,
        }
        await self.post_data(url, payload)
        return image_id

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def insert_reference_image(self, image_id: UUID) -> None:
        url = f"{CAMERA_GUARD_BASE}/api/v1/images/reference/"
        payload = {"sensor_id": self.sensor_id, "image_id": image_id}
        await self.post_data(url, payload)

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def get_sensor_data(self) -> Dict:
        url = f"{CAMERA_GUARD_BASE}/api/v1/cameras/"
        payload = {"camera_id": str(self.sensor_id)}
        return await self.get_data(url, payload)

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def get_collect_types(self) -> List[Dict]:
        url = f"{CAMERA_GUARD_BASE}/api/v1/collects/"
        return await self.get_data(url)

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def insert_image_check(self, **kwargs) -> None:
        url = f"{CAMERA_GUARD_BASE}/api/v1/checks/insert_check"
        return await self.post_data(url, kwargs)

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_tries=RETRIES, jitter=None
    )
    async def insert_sensor_ping(self, **kwargs) -> None:
        url = f"{CAMERA_GUARD_BASE}/api/v1/checks/insert_ping_check"
        return await self.post_data(url, kwargs)

    @staticmethod
    def generate_check_id() -> UUID:
        # For mock
        return uuid.uuid4()

    async def insert_check(
            self,
            image_id: Optional[UUID],
            has_image: bool,
            collect_type_id: Optional[UUID],
            detail,
            check_status,
            image_analize: ImageApiResponse = None,
    ):
        payload = {
            "id": self.generate_check_id(),
            "sensor_id": self.sensor_id,
            "collect_type_id": collect_type_id,
            "detail": detail,
            "check_status": check_status,
        }
        if image_id:
            payload["image_id"] = image_id
        if has_image:
            if not image_analize:
                image_analize = ImageApiResponse.parse_obj(dict())
            payload = dict(payload, **image_analize.dict())
            return await self.insert_image_check(**payload)
        else:
            payload["image"] = has_image
            return await self.insert_sensor_ping(**payload)


async def get_token(timeout):
    while True:
        auth = {"username": settings.LOGIN, "password": settings.PASSWORD}
        form = aiohttp.FormData(fields=auth)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            async with aiohttp.ClientSession(
                    timeout=Client.TIMEOUT, headers=headers
            ) as session:
                async with session.post(
                        f"{settings.CAMERA_GUARD_BASE}/api/v1/auth/token", data=form()
                ) as resp:
                    if resp.status == 200:
                        resp_json = await resp.json()
                        settings.TOKEN = resp_json["access_token"]
                        settings.TOKEN_TYPE = resp_json["token_type"]
                        client_logger.info("Obtained new token")
        except Exception as e:
            client_logger.exception(e)
        finally:
            await asyncio.sleep(timeout)
