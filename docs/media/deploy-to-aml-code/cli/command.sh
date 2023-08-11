# register flow as a model
az ml model create --file model.yaml

# create online endpoint
az ml online-endpoint create --file endpoint.yaml

# create online deployment with 0 traffic
az ml online-deployment create --file deployment.yaml

# create online deployment with 100% traffic
az ml online-deployment create --file deployment.yaml --all-traffic

# set traffic of the deployment
az ml online-endpoint update --name basic-chat-endpoint --traffic "blue=100"

# invoke the endpoint
az ml online-endpoint invoke --name basic-chat-endpoint --request-file sample-request.json