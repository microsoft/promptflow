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


**Run dag flow** with docker run by flask serving engine:
`docker run -p 8080:8080 -e OPEN_AI_CONNECTION_API_KEY=<secret-value> -e PROMPTFLOW_WORKER_NUM=<expect-worker-num> -e PROMPTFLOW_WORKER_THREADS=<expect-thread-num-per-worker> <image_name>`
example:
`docker run -p 8080:8080 -e OPEN_AI_CONNECTION_API_KEY=111 -e PROMPTFLOW_WORKER_NUM=1 -e PROMPTFLOW_WORKER_THREADS=1 dag_flow_image`

**Run flex flow** with docker run by flask serving engine:
`docker run -p 8080:8080 -e PROMPTFLOW_WORKER_NUM=<expect-worker-num> -e PROMPTFLOW_WORKER_THREADS=<expect-thread-num-per-worker> -e PF_FLOW_INIT_CONFIG=<init config with json string> <image_name>`
example:
`docker run -p 8080:8080 -e PROMPTFLOW_WORKER_NUM=1 -e PROMPTFLOW_WORKER_THREADS=1 -e PF_FLOW_INIT_CONFIG='{"model_config": {"api_key": "111", "azure_endpoint": "https://test.openai.azure.com/", "azure_deployment": "gpt-35-turbo"}}' flex_flow_image`


Test the endpoint:
After start the service, you can use curl to test it: `curl http://localhost:8080/score --data <dict_data> `


Please refer to [official doc](https://microsoft.github.io/promptflow/how-to-guides/deploy-a-flow/deploy-using-docker.html)
for more details about how to use the exported dockerfile and scripts.
