# Flow with additional_includes

Sometimes some common files or folders on other top level folders. In this case, use additional includes to set the additional file or folders used by the flow. The file or folders in additional includes will be copied to the snapshot folder by the promptflow-sdk when operate this flow.

## Tools used in this flow
- LLM Tool
- Python Tool

## What you will learn

In this flow, you will learn
- how to add additional includes to the flow

## Prerequisites

Install prompt-flow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Getting Started

### 1. Add additional includes to flow

You can add this field `additional_includes` into the `flow.dag.yaml`. The value of this field is a list of the relative file/folder path to the flow folder.

``` yaml
additional_includes:
 - your/local/path1
 - your/local/path2
```

### 2. Operate the flow

In this sample, this flow will references some files in [web-classification flow](../web-classification/README.md). You can execute this flow with additional_include locally or submit it to cloud.


#### Test flow with single line data

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```


#### Run with multi-line data

```bash
# create run using command line args
pf run create --flow . --data ./data.jsonl --stream
# create run using yaml file
pf run create --file run.yml --stream
```

#### Submit run to cloud

``` bash
# create run
pfazure run create --flow . --data ./data.jsonl --stream --runtime demo-mir --subscription <subscription-id> -g <resource-group-name> -w <workspace-name>
pfazure run create --flow . --data ./data.jsonl --stream # serverless compute
pfazure run create --file run.yml --runtime demo-mir
pfazure run create --file run.yml --stream # serverless compute
```