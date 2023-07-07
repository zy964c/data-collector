import asyncio
import logging
import time
from typing import Type

from aiohttp import ClientResponseError, ClientConnectionError

from collectors.base_collectors import DBCollector, BaseCollector
from collectors.factories import factory
from exceptions.exceptions import (
    ApiClientError,
    SourceUnavailableException,
    NoReferenceImageError, ForbiddenError, UnauthorizedError,
)
from image_api_client.client import Client
from models.enums import CheckStatus
from models.remotes import CheckResult

logger = logging.getLogger("collector_app.workers")


async def collect_from_source(collector: Type[BaseCollector], use_db: bool):
    if issubclass(type(collector), DBCollector) and use_db:
        return await collector.collect_from_db()
    else:
        try:
            return await collector.collect()
        except ClientResponseError as ex:
            if ex.status == 401:
                auth_type = ex.headers.get("WWW-Authenticate")
                detail = f'Unauthorized, type of authentication: {auth_type}'
                raise UnauthorizedError(detail=detail)
            elif ex.status == 403:
                raise ForbiddenError()
            else:
                raise ex


def can_be_executed(exec_time) -> bool:
    if exec_time:
        now = time.time()
        if int(exec_time) > now:
            return False
    return True


async def worker(
        name: str, job_queue: asyncio.PriorityQueue, retry_period: float
) -> None:
    while True:
        try:
            res = job_queue.get_nowait()[1]
        except asyncio.QueueEmpty:
            await asyncio.sleep(1)
            continue
        sensor_id, collect_type_id, collect_type, retry_count, exec_time, use_db, client = res
        image_api_client: Client = client
        if not can_be_executed(exec_time):
            job_queue.put_nowait((100, res))
            job_queue.task_done()
            await asyncio.sleep(0.1)
            continue
        logger.info(
            f"Worker {name}. Making requests for the following collect types: {collect_type}"
        )
        collector = factory.get_collector(collect_type)
        detail, image_id, response = None, None, None
        check_result = CheckResult()
        try:
            collector = await collector.create(
                sensor_id, collect_type_id, image_api_client
            )
            check_result = await collect_from_source(collector, use_db)
            if check_result.image:
                try:
                    reference_image, masks = await image_api_client.get_reference_image()
                    response = await image_api_client.prepare_data_select_api_and_make_request(
                        check_result.image,
                        reference_image,
                        masks
                    )
                except NoReferenceImageError:
                    await image_api_client.insert_first_reference_image(check_result.image,
                                                                        check_result.extension)
                    raise
                finally:
                    image_id = image_api_client.image_id
                    if not image_id:
                        image_id = await image_api_client.insert_image(
                            check_result.image, check_result.extension
                        )
            else:
                logger.warning("Could not find image in check result")
        except (ClientConnectionError, asyncio.TimeoutError, ClientResponseError) as e:
            detail = type(e).__name__
            check_result.check_status = CheckStatus.UNAVAILABLE
            logger.warning(f"Http error. {e}")
        except (NoReferenceImageError, SourceUnavailableException, ForbiddenError, UnauthorizedError) as e:
            detail = e.detail
            check_result.check_status = e.status
            logger.warning(str(e))
        except ApiClientError as e:
            detail = e.detail
            check_result.check_status = e.status
            retry_count -= 1
            if retry_count > 0:
                job_queue.put_nowait(
                    (
                        100,
                        (
                            sensor_id,
                            collect_type_id,
                            collect_type,
                            retry_count,
                            time.time() + retry_period,
                            use_db,
                            image_api_client,
                        ),
                    )
                )
        except Exception as e:
            detail = str(e)
            check_result.check_status = CheckStatus.UNAVAILABLE
            logger.exception(e)
        try:
            if detail:
                detail = detail[:500]
            await image_api_client.insert_check(
                image_id,
                check_result.image is not None,
                collect_type_id if collect_type_id else None,
                detail,
                check_result.check_status.value,
                response,
            )
            logger.info(f"{name} completed")
        except Exception as e:
            logger.exception(e)
        finally:
            job_queue.task_done()


async def create_workers(
        task_queue: asyncio.PriorityQueue, workers_count: int, retry_period: int
) -> None:
    while True:
        tasks = set()
        for i in range(workers_count):
            task = asyncio.create_task(worker(f"worker-{i}", task_queue, retry_period))
            logger.debug(f"Created task: {task}")
            tasks.add(task)
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.warning("All workers have died")
        await asyncio.sleep(0.1)
