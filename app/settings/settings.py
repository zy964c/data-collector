from os import environ
from get_docker_secret import get_docker_secret


TOKEN = ""
TOKEN_TYPE = ""
TOKEN_TIMEOUT = int(environ.get("token_timeout"))
LOGIN = get_docker_secret("camguard_login")
PASSWORD = get_docker_secret("camguard_password")
CAMERA_GUARD_BASE = environ.get("camera_guard_base")
DEBUG = bool(int(environ.get("DEBUG", 0)))
API_VERSIONS = [2]
AWS_ACCESS_KEY_ID = get_docker_secret("sensors_aws_access_key_id", autocast_name=False)
AWS_SECRET_ACCESS_KEY = get_docker_secret("sensors_aws_secret_access_key", autocast_name=False)
AWS_BUCKET_NAME = environ.get("s3_bucket")
S3_ENDPOINT = environ.get("S3_ENDPOINT", "http://10.10.77.29:9001")
YOUTUBE_DELAY = int(environ.get("youtube_delay"))
PROXY = environ.get("proxy")
WECTECH_DELAY = int(environ.get("wectech_delay", 10))
TD_DELAY = int(environ.get("td_delay", 10))
QUEUE_SIZE = int(environ.get("task_queue_size"))
RETRIES_NUMBER = int(environ.get("retries_number"))
RETRIES_PERIOD = int(environ.get("retries_period"))
