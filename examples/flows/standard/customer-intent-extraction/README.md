# Customer Intent Extraction

This sample is using OpenAI chat model(ChatGPT/GPT4) to identify customer intent from customer's question.

By going through this sample you will learn how to create a flow from existing working code (written in LangChain in this case).

This is the [existing code](./intent.py).

## Prerequisites
Install promptflow sdk and other dependencies:

```bash
pip install -r requirements.txt
```

Ensure you have put your azure open ai endpoint key in .env file.

```bash
cat .env
```

## Run flow

1. init flow directory - create promptflow folder from existing python file
```bash
pf flow init --flow . --entry intent.py --function extract_intent --prompt-template chat_prompt=user_intent_zero_shot.jinja2
```
The generated files:
- extract_intent_tool.py: Wrap the func `extract_intent` in the `intent.py` script into a [Python Tool](https://promptflow.azurewebsites.net/tools-reference/python-tool.html).
- flow.dag.yaml: Describes the DAG(Directed Acyclic Graph) of this flow.
- .gitignore: File/folder in the flow to be ignored.

2. create needed custom connection
```bash
pf connection create -f .env --name custom_connection
```

3. test flow with single line input
```bash
pf flow test --flow . --inputs ./data/sample.json
```

4. run with multiple lines input
```bash
pf run create --flow . --data ./data --column-mapping history='${data.history}' customer_info='${data.customer_info}'
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

5. list/show 

```bash
# list created run
pf run list
# get a sample completed run name
name=$(pf run list | jq '.[] | select(.name | contains("customer_intent_extraction")) | .name'| head -n 1 | tr -d '"')
# show run
pf run show --name $name
# show specific run detail, top 3 lines
pf run show-details --name $name -r 3
```

6. evaluation

```bash
# create evaluation run
pf run create --flow ../../evaluation/eval-classification-accuracy --data ./data --column-mapping groundtruth='${data.intent}' prediction='${run.outputs.output}' --run $name
```

```bash
# get the evaluation run in previous step
eval_run_name=$(pf run list | jq '.[] | select(.name | contains("eval_classification_accuracy")) | .name'| head -n 1 | tr -d '"')
# show run
pf run show --name $eval_run_name
# show run output
pf run show-details --name $eval_run_name -r 3
```

6. visualize
```bash
# visualize in browser
pf run visualize --name $eval_run_name # your evaluation run name
```

## Deploy 

### Serve as a local test app

```bash
pf flow serve --source . --port 5123 --host localhost
```
Visit http://localhost:5213 to access the test app.

### Export

#### Export as docker
```bash
# pf flow export --source . --format docker --output ./package
```