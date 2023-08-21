# Flow with additional_includes

User sometimes need to reference some common files or folders, this sample demos how to solve the problem using additional_includes. The file or folders in additional includes will be 
copied to the snapshot folder by promptflow when operate this flow.

## Tools used in this flow
- LLM Tool
- Python Tool

## What you will learn

In this flow, you will learn
- how to add additional includes to the flow

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Getting Started

### 1. Add additional includes to flow

You can add this field `additional_includes` into the [`flow.dag.yaml`](flow.dag.yaml). 
The value of this field is a list of the relative file/folder path to the flow folder.

``` yaml
additional_includes:
- ../web-classification/classify_with_llm.jinja2
- ../web-classification/convert_to_dict.py
- ../web-classification/fetch_text_content_from_url.py
- ../web-classification/prepare_examples.py
- ../web-classification/summarize_text_content.jinja2
- ../web-classification/summarize_text_content__variant_1.jinja2
```

### 2. Test & run the flow with additional includes

In this sample, this flow will references some files in the [web-classification](../web-classification/README.md) flow. 
You can execute this flow with additional_include locally or submit it to cloud.


#### Test flow with single line data

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
# test with user specified inputs
pf flow test --flow . --inputs url='https://www.microsoft.com/en-us/d/xbox-wireless-controller-stellar-shift-special-edition/94fbjc7h0h6h'
```


#### Run with multi-line data

```bash
# create run using command line args
pf run create --flow . --data ./data.jsonl --stream
# create run using yaml file
pf run create --file run.yml --stream
```
Note: the snapshot folder in run should contain the additional_includes file.

#### Submit run to cloud

``` bash
# create run
# pfazure run create --flow . --data ./data.jsonl --stream --runtime demo-mir --subscription <your_subscription_id> -g <your_resource_group_name> -w <your_workspace_name>
# pfazure run create --flow . --data ./data.jsonl --stream # serverless compute
# pfazure run create --file run.yml --runtime demo-mir
# pfazure run create --file run.yml --stream # serverless compute
```

Note: the snapshot folder in run should contain the additional_includes file. Click portal_url of the run to view the final snapshot.