import asyncio
import time
import uuid

import aiohttp
import pytest
from aiohttp import ClientResponseError, ClientConnectionError, RequestInfo

from exceptions.exceptions import NoReferenceImageError
from models.remotes import ImageApiResponse, CheckResult
from asyncio import PriorityQueue
from unittest.mock import ANY, Mock, PropertyMock
from models.enums import CheckStatus
from tests.helpers import get_image
from asynctest import CoroutineMock as AsyncMock, MagicMock, sentinel

sensor_id = uuid.uuid4()
check_id = uuid.uuid4()
collect_type_id = uuid.uuid4()
match_image_id = uuid.uuid4()
image_id = uuid.uuid4()
image_api_json = {
    "x": 120,
    "y": 100,
    "size_x": 0,
    "size_y": 10,
    "rotation": 0.13,
    "shear": 0.17,
    "ping": None,
    "api_version": 2,
    "match_image_id": match_image_id,
    "image_width": 640,
    "image_height": 320,
    "matches": "matches.png",
}
image_api_response = ImageApiResponse(**image_api_json)
client_request_mock = AsyncMock(return_value=image_api_response)
client_get_mock = AsyncMock()
client_post_mock = AsyncMock()
client_insert_image_check_mock = AsyncMock()
client_insert_sensor_ping_mock = AsyncMock()
client_insert_check_mock = AsyncMock()
collector_collect_mock = AsyncMock(
    return_value=(CheckResult(image=get_image("./tests/picture.png"), extension="png"))
)
collector_collect_mock_db = AsyncMock(
    return_value=(CheckResult(image=get_image("./tests/picture.png"), extension="png"))
)
ping_collector_collect_mock = AsyncMock(
    return_value=(CheckResult(check_status=CheckStatus.NOCHANGE))
)

TIMEOUT = 0.01
RETRIES = 2
RETRY_PERIOD = 0.01


@pytest.fixture()
def patcher(mocker):
    def _patch_collector(collector, api_client):
        collector_create_mock = AsyncMock(
            return_value=collector(
                sensor_id=str(sensor_id),
                collect_type_id=collector.collector_type,
                client=api_client,
            )
        )
        mocker.patch.object(collector, "create", collector_create_mock)
        if collector.collector_type == "ping":
            mocker.patch.object(collector, "collect", ping_collector_collect_mock)
        else:
            mocker.patch.object(collector, "collect", collector_collect_mock)
            mocker.patch.object(collector, "collect_from_db", collector_collect_mock)
        return collector_create_mock

    mocker.patch("logging.handlers.RotatingFileHandler")
    mocker.patch("logging.getLogger")
    from image_api_client.client import Client

    mocker.patch.object(Client, "prepare_data_select_api_and_make_request", client_request_mock)
    mocker.patch.object(Client, "get_data", client_get_mock)
    mocker.patch.object(Client, "post_data", client_post_mock)
    mocker.patch.object(Client, "insert_image_check", client_insert_image_check_mock)
    mocker.patch.object(Client, "insert_sensor_ping", client_insert_sensor_ping_mock)
    mocker.patch.object(Client, "generate_check_id", Mock(return_value=check_id))
    mocker.patch.object(Client, "image_id", PropertyMock(return_value=None))
    mocker.patch.object(Client, "insert_image", AsyncMock(return_value=image_id))
    client_insert_image_check_mock.reset_mock()
    client_insert_sensor_ping_mock.reset_mock()
    client = Client(sensor_id)
    return client, _patch_collector


async def throw_in_queue(*args):
    queue = PriorityQueue()
    await queue.put((1, args))
    return queue


async def run_worker(collector, patcher, timeout=TIMEOUT):
    from worker import worker

    client, patch_collector = patcher
    patch_collector(collector, client)
    queue = await throw_in_queue(
        sensor_id,
        collect_type_id,
        collector.collector_type,
        RETRIES,
        None,
        False,
        client,
    )
    try:
        await asyncio.wait_for(worker("test worker", queue, RETRY_PERIOD), timeout=timeout)
    except asyncio.TimeoutError:
        return


@pytest.mark.asyncio
async def test_collect_from_source(mocker):
    from worker import collect_from_source
    from collectors.base_collectors import DBCollector

    mocker.patch.object(DBCollector, "collect_from_db", collector_collect_mock_db)
    from image_api_client.client import Client

    await collect_from_source(
        DBCollector(sensor_id, collect_type_id, Client(sensor_id)), True
    )
    collector_collect_mock_db.assert_awaited()
    mocker.patch.object(DBCollector, "collect", collector_collect_mock)
    await collect_from_source(
        DBCollector(sensor_id, collect_type_id, Client(sensor_id)), False
    )
    collector_collect_mock.assert_awaited()
    from collectors.ping_collector import PingCollector

    mocker.patch.object(PingCollector, "collect", ping_collector_collect_mock)
    await collect_from_source(
        PingCollector(sensor_id, collect_type_id, Client(sensor_id)), True
    )
    ping_collector_collect_mock.assert_awaited()
    await collect_from_source(
        PingCollector(sensor_id, collect_type_id, Client(sensor_id)), False
    )
    ping_collector_collect_mock.assert_awaited()


def test_can_be_executed():
    from worker import can_be_executed

    assert can_be_executed(None) is True
    future_exec_time = time.time() + 3600
    assert can_be_executed(future_exec_time) is False
    past_exec_time = time.time() - 3600
    assert can_be_executed(past_exec_time) is True
    present_exec_time = time.time()
    assert can_be_executed(present_exec_time) is True


@pytest.mark.asyncio
async def test_wectech_worker(patcher):
    from collectors.wecktech_collector import WectechCollector

    await run_worker(WectechCollector, patcher)
    params = image_api_json
    params["detail"] = None
    params["id"] = check_id
    params["collect_type_id"] = collect_type_id
    params["detail"] = None
    params["image_id"] = image_id
    params["sensor_id"] = sensor_id
    params["check_status"] = None
    client_insert_image_check_mock.assert_awaited_once_with(**params)


@pytest.mark.asyncio
async def test_ping_worker(patcher):
    from collectors.ping_collector import PingCollector

    await run_worker(PingCollector, patcher)
    params = dict()
    params["detail"] = None
    params["id"] = check_id
    params["collect_type_id"] = collect_type_id
    params["image"] = False
    params["sensor_id"] = sensor_id
    params["check_status"] = CheckStatus.NOCHANGE.value
    client_insert_sensor_ping_mock.assert_awaited_once_with(**params)


@pytest.mark.asyncio
async def test_client_response_error_worker(patcher, mocker):
    from collectors.wecktech_collector import WectechCollector
    from exceptions.exceptions import NoReferenceImageError

    exceptions_mapping = {
        ClientResponseError(
            message="encountered client response error",
            request_info=RequestInfo("test.com", "POST", {}, "test.com"),
            history=None,
        ): ("ClientResponseError", CheckStatus.UNAVAILABLE),
        ClientConnectionError: ("ClientConnectionError", CheckStatus.UNAVAILABLE),
        NoReferenceImageError: (NoReferenceImageError().detail, CheckStatus.NOCHANGE),
        asyncio.TimeoutError: ("TimeoutError", CheckStatus.UNAVAILABLE),
        ValueError: (str(ValueError()), CheckStatus.UNAVAILABLE),
    }
    for key, value in exceptions_mapping.items():
        client_request_mock.side_effect = key
        detail, check_status = value
        from image_api_client.client import Client

        mocker.patch.object(Client, "insert_check", client_insert_check_mock)
        await run_worker(WectechCollector, patcher)
        client_insert_check_mock.assert_awaited_once_with(
            ANY, True, collect_type_id, detail, check_status.value, None
        )
        client_insert_check_mock.reset_mock()


@pytest.mark.asyncio
async def test_api_client_error_worker(patcher):
    from collectors.wecktech_collector import WectechCollector
    from exceptions.exceptions import ApiClientError

    client_request_mock.reset_mock()
    client_request_mock.side_effect = ApiClientError
    await run_worker(WectechCollector, patcher)
    assert client_request_mock.await_count == RETRIES


@pytest.mark.asyncio
async def test_can_be_executed_in_worker(patcher, mocker):
    from collectors.wecktech_collector import WectechCollector
    mock = mocker.patch('worker.can_be_executed')
    mock.return_value = False
    await run_worker(WectechCollector, patcher, timeout=0.5)
    assert len(mock.call_args_list) > 1


@pytest.mark.asyncio
async def test_image_id_is_not_none(patcher, mocker):
    from collectors.wecktech_collector import WectechCollector
    mocker.patch('image_api_client.client.Client.prepare_data_select_api_and_make_request',
                 new=Mock(side_effect=NoReferenceImageError))
    mocker.patch('image_api_client.client.Client.image_id', new=PropertyMock(return_value=image_id))
    await run_worker(WectechCollector, patcher)
    params = dict()
    params["id"] = check_id
    params["collect_type_id"] = collect_type_id
    params["detail"] = NoReferenceImageError().detail
    params["image_id"] = image_id
    params["sensor_id"] = sensor_id
    params["check_status"] = CheckStatus.NOCHANGE.value
    params = dict(params, **ImageApiResponse.parse_obj(dict()).dict())
    client_insert_image_check_mock.assert_awaited_once_with(**params)


@pytest.mark.asyncio
async def test_insert_check_exception(patcher, mocker):
    from collectors.wecktech_collector import WectechCollector
    mock = AsyncMock(side_effect=aiohttp.ClientError)
    mocker.patch('image_api_client.client.Client.insert_check', new=mock)
    await run_worker(WectechCollector, patcher)
    mock.assert_awaited()


@pytest.mark.asyncio
async def test_empty_queue(patcher, mocker):
    from collectors.wecktech_collector import WectechCollector
    mock = MagicMock(side_effect=asyncio.QueueEmpty)
    mocker.patch('asyncio.Queue.get_nowait', new=mock)
    await run_worker(WectechCollector, patcher, timeout=1.5)
    assert len(mock.call_args_list) > 1


@pytest.mark.asyncio
async def test_create_workers(mocker):
    from worker import create_workers
    workers_count = 10
    create_task_mock, gather_mock = AsyncMock(), AsyncMock()
    mocker.patch('asyncio.create_task', new=create_task_mock)
    mocker.patch('asyncio.gather', new=gather_mock)
    create_task_mock.return_value = sentinel.some_object
    with pytest.raises(Exception):
        await asyncio.wait_for(create_workers(asyncio.PriorityQueue, workers_count, 60),
                               timeout=0.2)
    assert len(gather_mock.call_args[0]) == workers_count
