FROM python:3.9-slim-bullseye AS base

RUN set -x

RUN apt-get update \
    && apt-get -y install curl \
    && apt-get -y install net-tools \
    && apt-get -y install procps \
    && apt-get -y install build-essential \
    && apt-get -y install docker.io

# Install notebook depenency
RUN pip install ipython ipykernel
RUN ipython kernel install --user --name promptflow

# FROM base AS promptflow
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN set +x

CMD bash
