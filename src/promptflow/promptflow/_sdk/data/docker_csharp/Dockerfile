# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build

WORKDIR /
COPY ./flow /flow
COPY ./connections /connections

FROM mcr.microsoft.com/dotnet/aspnet:6.0 AS runtime
COPY --from=build / /

WORKDIR /flow
ENV IS_IN_DOCKER="true"
EXPOSE 8080
ENTRYPOINT ["dotnet", "Promptflow.DotnetService.dll", "-y", "flow.dag.yaml", "-a", ".", "-c", "", "-p", "8080", "-l", "", "-s"]
