#!/usr/bin/env bash
set -xe

pip install -r requirements.txt
cat .env
pf flow test --flow .
pf flow test --flow . --inputs text="Hello World!"
pf run create --flow . --data ./data.jsonl --stream
pf run list
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("basic_default")) | .name'| head -n 1 | tr -d '"')
pf run show --name $name
pf run show-details --name $name
pf run visualize --name $name
pf connection create --file azure_openai.yml --set api_key=$aoai_api_key api_base=$aoai_api_endpoint
pf connection show -n azure_open_ai_connection
pf flow test --flow . --environment-variables AZURE_OPENAI_API_KEY='${azure_open_ai_connection.api_key}' AZURE_OPENAI_API_BASE='${azure_open_ai_connection.api_base}'
pf run create --flow . --data ./data.jsonl --stream --environment-variables AZURE_OPENAI_API_KEY='${azure_open_ai_connection.api_key}' AZURE_OPENAI_API_BASE='${azure_open_ai_connection.api_base}'
pf run create --file run.yml --stream
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("basic_default")) | .name'| head -n 1 | tr -d '"')
pf run show-details --name $name
az account set -s $test_workspace_sub_id
az configure --defaults group=$test_workspace_rg workspace=$test_workspace_name
pfazure run create --flow . --data ./data.jsonl --environment-variables AZURE_OPENAI_API_KEY='${azure_open_ai_connection.api_key}' AZURE_OPENAI_API_BASE='${azure_open_ai_connection.api_base}' --stream --runtime demo-mir
pfazure run create --file run.yml --stream --runtime demo-mir
pfazure run list -r 3
name=$(pfazure run list -r 100 | jq '.[] | select(.name | contains("basic_default")) | .name'| head -n 1 | tr -d '"')
pfazure run show --name $name
pfazure run show-details --name $name
pfazure run visualize --name $name