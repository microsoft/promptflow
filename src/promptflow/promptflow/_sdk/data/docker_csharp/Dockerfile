# syntax=docker/dockerfile:1
FROM docker.io/continuumio/miniconda3:latest AS base

WORKDIR /

COPY ./flow /flow
COPY ./promptflow-0.0.1-py3-none-any.whl /promptflow-0.0.1-py3-none-any.whl

# create conda environment
RUN conda create -n promptflow-serve python=3.9.16 pip=23.0.1 -q -y && \
    conda run -n promptflow-serve \
    pip install promptflow-0.0.1-py3-none-any.whl \
    promptflow-tools && \
    conda run -n promptflow-serve pip install keyrings.alt && \
    conda run -n promptflow-serve pip install gunicorn==20.1.0 && \
    conda run -n promptflow-serve pip cache purge && \
    conda clean -a -y


RUN apt-get update && apt-get install -y runit

COPY ./connections /connections


FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build
WORKDIR /app


COPY --from=base / /app

WORKDIR /app/flow
ENV ASPNETCORE_URLS=http://+:8080
ENV DOTNET_USE_POLLING_FILE_WATCHER=true
EXPOSE 8080
ENTRYPOINT ["dotnet", "Promptflow.DotnetService.dll", "-y", "flow.dag.yaml", "-a", ".", "-c", "", "-p", "8080", "-l", "", "-s"]
