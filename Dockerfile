ARG PYTHON_VERSION=3.12

FROM python:$PYTHON_VERSION-slim

RUN apt-get update && apt-get upgrade -y

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install -r requirements.txt

COPY assets ./assets
COPY *.py ./

CMD uvicorn main:app --host $COLUNCH_HOST --port $COLUNCH_PORT
