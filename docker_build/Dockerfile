FROM continuumio/miniconda3

WORKDIR /

# Disable pip install cache
ENV PIP_NO_CACHE_DIR=1

# Create conda environment with python 3.9, and use as default python environment
ENV CONDA_ENVIRONMENT_PATH=/azureml-envs/prompt-flow/executor
ENV CONDA_DEFAULT_ENVIRONMENT=$CONDA_ENVIRONMENT_PATH
ENV PATH $CONDA_DEFAULT_ENVIRONMENT/bin:$PATH
COPY ./conda_dependencies.yaml .
RUN conda env create -p $CONDA_ENVIRONMENT_PATH -f conda_dependencies.yaml -q && \
    rm conda_dependencies.yaml && \
    conda clean -a -y

# Install promptflow package
COPY ./promptflow-0.0.1-py3-none-any.whl ./
RUN pip install "./promptflow-0.0.1-py3-none-any.whl[executor-service]" \
    && rm promptflow-0.0.1-py3-none-any.whl

# Install extra requirements
COPY ./extra_requirements.txt ./
RUN pip install -r extra_requirements.txt

ENV APP_PORT 8000

CMD ["sh", "-c", "exec uvicorn promptflow.executor._service.app:app --host 0.0.0.0 --port $APP_PORT"]
