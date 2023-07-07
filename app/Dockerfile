FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8-slim
EXPOSE 80
RUN apt-get update
RUN apt-get install ffmpeg libsm6 libxext6  -y
COPY ./app/requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install -r requirements.txt
COPY ./app /app