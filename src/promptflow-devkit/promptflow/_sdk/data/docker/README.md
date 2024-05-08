Exported Dockerfile & its dependencies are located in the same folder. The structure is as below:
- flow: the folder contains all the flow files
  - ...
- connections: the folder contains yaml files to create all related connections
  - ...
- runit: the folder contains all the runit scripts
  - ...
- Dockerfile: the dockerfile to build the image
- start.sh: the script used in `CMD` of `Dockerfile` to start the service
- settings.json: a json file to store the settings of the docker image
- README.md: the readme file to describe how to use the dockerfile


Build Docker image:
`docker build <build_output> -t <image_name>`


Run with docker run by flask serving engine:
`docker run -p 8080:8080 -e OPEN_AI_CONNECTION_API_KEY=<secret-value> -e PROMPTFLOW_WORKER_NUM=<expect-worker-num> -e PROMPTFLOW_WORKER_THREADS=<expect-thread-num-per-worker> <image_name>`


Test the endpoint:
After start the service, you can use curl to test it: `curl http://localhost:8080/score --data <dict_data> `


Please refer to [official doc](https://microsoft.github.io/promptflow/how-to-guides/deploy-a-flow/deploy-using-docker.html)
for more details about how to use the exported dockerfile and scripts.
