from settings import settings

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "class": "logging.Formatter",
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "use_colors": None,
        }
    },
    "handlers": {
        "default": {"formatter": "default", "class": "logging.StreamHandler"},
    },
    "loggers": {
        "": {"handlers": ["default"], "level": "INFO"},  # root logger
        "collector_app": {
            "handlers": ["default"],
            "level": "DEBUG" if settings.DEBUG else "INFO",
            "propagate": False,
        },
        "aiohttp.client": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
