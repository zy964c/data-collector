import json
import uuid

import pytest
from fastapi.testclient import TestClient
from models.api import Item
from models.encoders import UUIDEncoder
from asynctest import CoroutineMock as AsyncMock, sentinel

from models.remotes import ImageApiResponse

sensor_id = uuid.uuid4()
collect_type_id = uuid.uuid4()


image_api_response = ImageApiResponse()
client_get_collect_types_mock = AsyncMock(
    return_value=[{"id": str(collect_type_id), "collect_type": "wectech"}]
)


@pytest.fixture()
def patch_client(mocker):
    mocker.patch("logging.handlers.RotatingFileHandler")
    mocker.patch("logging.getLogger")
    mocker.patch("logging.config.dictConfig")
    from image_api_client.client import Client

    mocker.patch.object(Client, "get_collect_types", client_get_collect_types_mock)
    client = Client(sensor_id)
    return client


def test_collector_start(mocker, patch_client):
    from main import app

    client = TestClient(app)
    body = {"sensor_id": sensor_id, "collect_type_id": collect_type_id, "use_db": False}
    item = Item(**body)
    response = client.post("/api/v1/collector_start/", data=item.json())
    assert response.status_code == 200
    assert response.json() == json.loads(json.dumps(body, cls=UUIDEncoder))


@pytest.mark.asyncio
async def test_startup_event(patch_client, mocker):
    from main import startup_event, environ
    mocker.patch.dict(environ, {})
    ensure_future_mock = mocker.patch('asyncio.ensure_future')
    mocker.patch('main.create_workers').return_value = sentinel.some_object
    mocker.patch('main.get_token').return_value = sentinel.another_object
    await startup_event()
    assert len(ensure_future_mock.call_args_list) == 2
    assert environ["http_proxy"] == "10.10.256.4"
