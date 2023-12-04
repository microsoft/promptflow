# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build

WORKDIR /
COPY ./flow /flow
COPY ./connections /connections
COPY ./start.sh /start.sh

FROM mcr.microsoft.com/dotnet/aspnet:6.0 AS runtime
COPY --from=build / /

ENV IS_IN_DOCKER="true"
EXPOSE 8080

RUN apt-get update && apt-get install -y runit
# reset runsvdir
RUN rm -rf /var/runit
COPY ./runit /var/runit
# grant permission
RUN chmod -R +x /var/runit

CMD ["bash", "./start.sh"]
