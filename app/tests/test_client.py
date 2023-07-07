import base64
import json
import os
import uuid
from unittest.mock import MagicMock, Mock

import aiohttp
import pytest
from aiohttp import web
from aiohttp.web_exceptions import HTTPInternalServerError, HTTPBadRequest

from exceptions.exceptions import NoReferenceImageError, ApiClientError
from models.remotes import ImageApiResponse
import settings
from asynctest import CoroutineMock as AsyncMock
from tests.helpers import get_image

TEST_IMAGE = get_image("./tests/picture.png")
REF_IMAGE = TEST_IMAGE
EXT = "png"
NEW_IMAGE_ID = uuid.uuid4()


@pytest.fixture()
def setup(mocker):
    def _setup(
            ref_mock=None,
            patch_get_image=True,
            patch_get_reference_image_id=True,
            patch_insert_image=True,
            patch_insert_reference_image=True,
    ):
        from image_api_client.client import Client

        ref_return = [
            {
                "sensor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "image_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "image_url": "string",
                "date_created": "2020-03-18T11:20:30.411Z",
                "created_by": "string",
                "mask": [{"x1": 0, "y1": 0, "x2": 0, "y2": 0}],
            }
        ]
        if not ref_mock:
            ref_mock = AsyncMock(return_value=ref_return)
        get_im_mock = AsyncMock(return_value=REF_IMAGE)
        insert_im_mock = AsyncMock(return_value=NEW_IMAGE_ID)
        insert_reference_im_mock = AsyncMock()
        if patch_get_reference_image_id:
            mocker.patch.object(Client, "get_reference_image_id", ref_mock)
        if patch_get_image:
            mocker.patch.object(Client, "get_image", get_im_mock)
        if patch_insert_image:
            mocker.patch.object(Client, "insert_image", insert_im_mock)
        if patch_insert_reference_image:
            mocker.patch.object(
                Client, "insert_reference_image", insert_reference_im_mock
            )
        return Client

    return _setup


@pytest.fixture()
async def setup_server(aiohttp_server):
    server = None

    async def make_server(resp, mock=None, port=8080, **kwargs):
        async def handler(request):
            try:
                if mock:
                    mock()
                if resp is None:
                    return HTTPInternalServerError(
                        body=json.dumps({"detail": "image_api_error"}),
                        content_type="application/json",
                    )
                elif callable(resp):
                    if isinstance(resp(), Exception):
                        raise resp
                if request.can_read_body:
                    received_args = await request.json()
                    if received_args == kwargs:
                        return web.json_response(resp)
                    else:
                        return HTTPBadRequest(
                            body=json.dumps(
                                {"detail": "wrong incoming parameters supplied"}
                            ),
                            content_type="application/json",
                        )
            except Exception as e:
                raise HTTPInternalServerError(text=str(e))

        async def get_image_handler(request):
            return web.Response(body=resp)

        async def get_handler(request):
            return web.json_response(resp)

        async def get_reference_image_id_handler(request):
            try:
                sensor_id = request.query["sensor_id"]
                if sensor_id == kwargs["sensor_id"]:
                    return web.json_response(resp)
                else:
                    return HTTPBadRequest(
                        body=json.dumps(
                            {"detail": "incorrect incoming parameters supplied"}
                        ),
                        content_type="application/json",
                    )
            except Exception as e:
                raise HTTPInternalServerError(text=str(e))

        async def get_sensor_data_handler(request):
            try:
                sensor_id = request.query["camera_id"]
                if sensor_id == kwargs["camera_id"]:
                    return web.json_response(resp)
                else:
                    return HTTPBadRequest(
                        body=json.dumps(
                            {"detail": "incorrect incoming parameters supplied"}
                        ),
                        content_type="application/json",
                    )
            except Exception as e:
                raise HTTPInternalServerError(text=str(e))

        async def token_handler(request):
            try:
                data = await request.post()
                username = data["username"]
                password = data["password"]
                if username == kwargs["username"] and password == kwargs["password"]:
                    return web.json_response(resp)
                else:
                    return HTTPBadRequest(
                        body=json.dumps(
                            {"detail": "incorrect incoming parameters supplied"}
                        ),
                        content_type="application/json",
                    )
            except Exception as e:
                raise HTTPInternalServerError(text=str(e))

        nonlocal server
        app = web.Application(client_max_size=10000000)
        app.add_routes(
            [
                web.post("/{api_version}/movement", handler),
                web.get("", get_image_handler),
                web.post("/api/v1/images/reference/", handler),
                web.get("/api/v1/images/reference/", get_reference_image_id_handler),
                web.post("/api/v1/images/", handler),
                web.get("/api/v1/images/", get_reference_image_id_handler),
                web.get("/api/v1/cameras/", get_sensor_data_handler),
                web.get("/api/v1/collects/", get_handler),
                web.post("/api/v1/checks/insert_ping_check", handler),
                web.post("/api/v1/checks/insert_check", handler),
                web.post("/api/v1/auth/token", token_handler)
            ]
        )
        server = await aiohttp_server(app, port=port)
        return server

    yield make_server
    if server is not None:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("image", ["app/tests/picture.png", b"image"])
async def test_request(setup, setup_server, image):
    camera_api_resp = {
        "x": 0,
        "y": 0,
        "size_x": 0,
        "size_y": 0,
        "rotation": 0,
        "shear": 0,
        "matches": base64.b64encode(REF_IMAGE).decode("utf-8"),
    }
    from image_api_client.client import get_im_size

    client = setup()
    client = client(uuid.uuid4())
    masks = [{"x1": 0, "y1": 0, "x2": 0, "y2": 0}]
    if isinstance(image, bytes):
        image_width, image_height = None, None
    else:
        image = get_image("./tests/picture.png")
        image_width, image_height = get_im_size(image)
    await setup_server(
        camera_api_resp,
        ref_image=base64.b64encode(REF_IMAGE).decode("utf-8"),
        test_image=base64.b64encode(image).decode("utf-8"),
        return_matches=True,
        mask=masks,
    )
    response = await client.prepare_data_select_api_and_make_request(test_image=image,
                                                                     reference_image=REF_IMAGE,
                                                                     masks=masks)
    assert response == ImageApiResponse(
        image_height=image_height,
        image_width=image_width,
        **camera_api_resp,
        match_image_id=NEW_IMAGE_ID
    )


@pytest.mark.asyncio
async def test_request_no_ref_image(setup):
    ref_mock = AsyncMock(return_value=None)
    client = setup(ref_mock=ref_mock)
    client = client(uuid.uuid4())
    with pytest.raises(NoReferenceImageError):
        await client.get_reference_image()


@pytest.mark.asyncio
async def test_request_api_client_error(setup, setup_server):
    client = setup()
    client = client(uuid.uuid4())
    count_calls_mock = MagicMock()
    for response in [None, aiohttp.ClientError]:
        server = await setup_server(response, mock=count_calls_mock)
        with pytest.raises(ApiClientError):
            await client.prepare_data_select_api_and_make_request(test_image=TEST_IMAGE,
                                                                  reference_image=REF_IMAGE,
                                                                  masks=[{"x1": 0, "y1": 0, "x2": 0, "y2": 0}]
                                                                  )
        assert count_calls_mock.call_count == len(settings.settings.API_VERSIONS)
        count_calls_mock.reset_mock()
        await server.close()


@pytest.mark.asyncio
async def test_get_image(setup, setup_server):
    client = setup(patch_get_image=False)
    client = client(uuid.uuid4())
    image_bytes = b"image"
    await setup_server(image_bytes)
    response = await client.get_image(os.getenv("camera_guard_base"))
    assert response == image_bytes


@pytest.mark.asyncio
@pytest.mark.parametrize("reference", [True, False])
async def test_get_reference_image_id(setup, setup_server, reference):
    client = setup(patch_get_reference_image_id=False)
    sensor_id = uuid.uuid4()
    client = client(sensor_id)
    image_id = str(uuid.uuid4())
    resp = {"image_id": image_id}
    await setup_server(resp, sensor_id=str(sensor_id))
    response = await client.get_reference_image_id(reference=reference)
    assert response == resp


@pytest.mark.asyncio
async def test_insert_reference_image(setup, setup_server):
    client = setup(patch_insert_reference_image=False)
    sensor_id = uuid.uuid4()
    client = client(sensor_id)
    image_id = uuid.uuid4()
    await setup_server(
        {"image_id": str(image_id)}, sensor_id=sensor_id, image_id=str(image_id)
    )
    response = await client.insert_reference_image(image_id=image_id)
    assert response is None


@pytest.mark.asyncio
async def test_insert_image(setup, setup_server, mocker):
    client = setup(patch_insert_image=False)
    client = client(uuid.uuid4())
    image = b"image"
    image_id = uuid.uuid4()
    await setup_server(
        {"image_id": str(image_id)},
        id=str(image_id),
        image=base64.b64encode(image).decode("utf-8"),
        ext="jpg",
    )
    mock = Mock(return_value=image_id)
    mocker.patch.object(uuid, "uuid4", mock)
    response = await client.insert_image(image=image)
    assert response == image_id


@pytest.mark.asyncio
async def test_get_sensor_data(setup, setup_server):
    client = setup()
    sensor_id = uuid.uuid4()
    client = client(sensor_id)
    resp = {
        "id": "0aa469ff-2d15-4deb-9eda-c08395741caf",
        "name": "Wectech",
        "group_id": "16d2402b-bc74-45c9-9bde-61cf70b29aaf",
        "ip": "10.24.21.61",
        "maintenance": False,
        "port": 80,
        "login": None,
        "password": "6E5Mk21",
        "mask_point1": None,
        "mask_point2": None,
        "has_collectors": True
    }
    await setup_server(resp, camera_id=str(client.sensor_id))
    response = await client.get_sensor_data()
    assert response == resp


@pytest.mark.asyncio
async def test_get_collect_types(setup, setup_server):
    client = setup()
    sensor_id = uuid.uuid4()
    client = client(sensor_id)
    resp = [
        {
            "id": "0d195f8f-4bcb-49d8-aa7c-5b8450c2424b",
            "name": "TD-2000",
            "collect_type": "td"
        }]
    await setup_server(resp)
    response = await client.get_collect_types()
    assert response == resp


@pytest.mark.asyncio
@pytest.mark.parametrize("has_image", [False, True])
async def test_insert_check(setup, setup_server, mocker, has_image):
    client = setup()
    sensor_id = uuid.uuid4()
    client = client(sensor_id)
    check_id = uuid.uuid4()
    collect_type_id = uuid.uuid4()
    image_id = uuid.uuid4()
    detail = ''
    check_status = 0
    resp = {}
    image_analize = ImageApiResponse.parse_obj(dict())
    mocker.patch('image_api_client.client.Client.generate_check_id').return_value = check_id
    if not has_image:
        await setup_server(resp, id=str(check_id),
                           sensor_id=str(client.sensor_id),
                           collect_type_id=str(collect_type_id),
                           detail=detail,
                           check_status=check_status,
                           image_id=str(image_id),
                           image=False)
    else:
        await setup_server(resp, id=str(check_id),
                           sensor_id=str(client.sensor_id),
                           collect_type_id=str(collect_type_id),
                           detail=detail,
                           check_status=check_status,
                           image_id=str(image_id),
                           **image_analize.dict())
    response = await client.insert_check(image_id=image_id,
                                         has_image=has_image,
                                         collect_type_id=collect_type_id,
                                         detail=detail,
                                         check_status=check_status,
                                         image_analize=image_analize)
    assert response == resp


@pytest.mark.asyncio
@pytest.mark.parametrize("password", ['correct', 'incorrect'])
async def test_get_token(setup_server, mocker, password):
    from image_api_client.client import get_token
    timeout = 0
    access_token = 'token_value'
    token_type = 'some_token_type'
    settings_attrs = {'LOGIN': 'admin',
                      'PASSWORD': password,
                      'CAMERA_GUARD_BASE': 'http://127.0.0.1:8080'}
    settings_mock = Mock(**settings_attrs)
    mocker.patch('image_api_client.client.settings', new=settings_mock)
    mocker.patch('image_api_client.client.asyncio.sleep').side_effect = OSError
    request_args = {"username": "admin", "password": "correct"}
    await setup_server({"access_token": access_token,
                        "token_type": token_type}, **request_args)
    if password == 'correct':
        with pytest.raises(OSError):
            await get_token(timeout)
        assert settings_mock.TOKEN == access_token
        assert settings_mock.TOKEN_TYPE == token_type
    else:
        with pytest.raises(OSError):
            await get_token(timeout)
        assert settings_mock.TOKEN != access_token
        assert settings_mock.TOKEN_TYPE != token_type
