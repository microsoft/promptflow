FROM python:3.9-slim-bullseye AS base

RUN set -x

RUN apt-get update \
    && apt-get -y install curl \
    && apt-get -y install net-tools \
    && apt-get -y install procps \
    && apt-get -y install build-essential \
    && apt-get -y install docker.io

# specific pip version to workaround: https://github.com/conda/conda/issues/10178
RUN pip install --upgrade pip==20.1.1
RUN pip install ipython ipykernel
RUN ipython kernel install --user --name aml

# FROM base AS promptflow
COPY default_requirements.txt .
RUN pip install -r default_requirements.txt
COPY ../src/promptflow/dev_requirements.txt .
RUN pip install -r dev_requirements.txt
COPY ../src/promptflow-tools/requirements.txt .
RUN pip install -r requirements.txt

RUN set +x

CMD bash
