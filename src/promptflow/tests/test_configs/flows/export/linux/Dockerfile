# syntax=docker/dockerfile:1
FROM docker.io/continuumio/miniconda3:latest

WORKDIR /

COPY ./flow /flow

# create conda environment, and use as default python environment
ENV CONDA_ENVIRONMENT_PATH=/opt/conda/envs/promptflow-serve
ENV CONDA_DEFAULT_ENVIRONMENT=$CONDA_ENVIRONMENT_PATH
ENV PATH $CONDA_DEFAULT_ENVIRONMENT/bin:$PATH
RUN conda create -n promptflow-serve python=3.9.16 pip=23.0.1 -q -y && \
    conda run -n promptflow-serve \
    pip install -r /flow/requirements_txt && \
    conda run -n promptflow-serve pip install keyrings.alt && \
    conda run -n promptflow-serve pip cache purge && \
    conda clean -a -y

RUN conda run -n promptflow-serve sh /flow/setup.sh

EXPOSE 8080

COPY ./connections/* /connections/
COPY ./start.sh /
CMD ["bash", "./start.sh"]
