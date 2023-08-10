#!/usr/bin/env bash

foo() {


    pip install -r requirements.txt
    cat .env
    pf flow test --flow .
    pf flow test --flow . --inputs text="Hello World!"
    pf flow test --flow . --node llm --inputs prompt="Write a simple Hello World program that displays the greeting message when executed."
    pf run create --flow . --data ./data.jsonl --stream
    pf run list
    name=$(pf run list -r 1 | jq '.[:1] | .[] | .name' | tr -d '"')
    pf run show --name $name
    pf run show-details --name $name
    pf run visualize --name $name
    pf connection create --file azure_openai.yml --set api_key=$1 api_base=$2
    pf connection show -n azure_open_ai_connection
    pf flow test --flow . --environment-variables AZURE_OPENAI_API_KEY=$1 AZURE_OPENAI_API_BASE=$2
    pf run create --flow . --data ./data.jsonl --stream --environment-variables AZURE_OPENAI_API_KEY=$1 AZURE_OPENAI_API_BASE=$2
    pf run create --file run.yml --stream
    name=$(pf run list -r 1 | jq '.[:1] | .[] | .name' | tr -d '"')
    pf run show-details --name $name
    az account set -s $3
    az configure --defaults group=$4 workspace=$5
    pfazure run create --flow . --data ./data.jsonl --environment-variables AZURE_OPENAI_API_KEY=$1 AZURE_OPENAI_API_BASE=$2 --stream --runtime demo-mir
    pfazure run create --file run.yml --stream --runtime demo-mir
    pfazure run list -r 3
    name=$(pfazure run list -r 1 | jq '.[:1] | .[] | .name' | tr -d '"')
    pfazure run show --name $name
    pfazure run show-details --name $name
    pfazure run visualize --name $name
}