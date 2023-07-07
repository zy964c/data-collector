import asyncio
import uvicorn
from logging.config import dictConfig
import logging
from fastapi import FastAPI

from image_api_client.client import Client, get_token
from os import environ
from models.api import Item
from settings import settings
from settings.settings import RETRIES_NUMBER, QUEUE_SIZE, RETRIES_PERIOD
from worker import create_workers
from logging_conf import LOGGING_CONFIG

QUEUE = asyncio.PriorityQueue()
QUEUE_PRIORITY = {"ping": 0, "wectech": 4, "ftp": 3, "countmax": 1, "rtsp": 2, "xovis": 5}

dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("collector_app")

config = {"version": "v1",
          "openapi_url": "/api/v1/openapi.json",
          "docs_url": "/api/v1/docs",
          "title": "Collector app"
          }

if settings.DEBUG:
    config["openapi_prefix"] = "/collector"

app = FastAPI(**config)


@app.get("/ping", status_code=200, include_in_schema=False)
async def ping():
    return {'result': True}


@app.post("/api/v1/collector_start/", response_model=Item)
async def collector_start(item: Item):
    logger.debug(item)
    global QUEUE
    collect_type = None
    client = Client(item.sensor_id)
    collect_types = await client.get_collect_types()
    logger.debug(collect_types)
    for col_type in collect_types:
        if col_type["id"] == str(item.collect_type_id):
            collect_type = col_type["collect_type"]
            break
    await QUEUE.put(
        (
            QUEUE_PRIORITY.get(collect_type, 100),
            (
                item.sensor_id,
                item.collect_type_id,
                collect_type,
                RETRIES_NUMBER,
                None,
                item.use_db,
                client,
            ),
        )
    )
    return item


@app.on_event("startup")
async def startup_event():
    logger.info("Starting data-collector...")
    environ["http_proxy"] = settings.PROXY
    [
        asyncio.ensure_future(coro)
        for coro in [
            create_workers(
                task_queue=QUEUE, workers_count=QUEUE_SIZE, retry_period=RETRIES_PERIOD
            ),
            get_token(settings.TOKEN_TIMEOUT),
        ]
    ]


if settings.DEBUG:
    uvicorn.run(
        app, host="0.0.0.0", port=8003, loop="asyncio", log_config=LOGGING_CONFIG
    )
