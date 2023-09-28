FROM python:3.9-slim-bullseye AS base

RUN set -x

RUN apt-get update \
    && apt-get -y install curl \
    && apt-get -y install net-tools \
    && apt-get -y install procps \
    && apt-get -y install build-essential \
    && apt-get -y install docker.io

FROM base AS promptflow-package
# specific pip version to workaround: https://github.com/conda/conda/issues/10178
RUN pip install --upgrade pip==20.1.1
RUN pip install promptflow[azure] --upgrade \
    && pip install promptflow-tools --upgrade \
    && pip install python-dotenv --upgrade \
    && pip install bs4 --upgrade

RUN set +x

CMD bash
