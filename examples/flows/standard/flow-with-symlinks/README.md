# Flow with symlinks

When there is a cross flow share scenario in the flow folder, although using symlink can facilitate development, it has the following limitations. It is recommended to use **additional include**.

1. For Windows user, need to Administrator to create symbolic.
2. For Windows user, directly copy the folder with symlinks, it will deep copy the contents to the location.
3. Need to update the git config to support symlinks.

**Requirements**:
-  For Windows user, please creating user permission to [create symbolic links](https://learn.microsoft.com/en-us/windows/security/threat-protection/security-policy-settings/create-symbolic-links).
    1. Open your `Local Security Policy`
    2. Find `Local Policies` -> `User Rights Assignment` -> `Create symbolic links`
    3. Add you user name to this policy then reboot the compute.

**Attention**:
- For git operations, need to set `git config core.symlinks true`

## Tools used in this flow
- LLM Tool
- Python Tool

## What you will learn

In this flow, you will learn
- how to use symlinks in the flow

## Prerequisites

Install prompt-flow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Getting Started

### 1. Create symbolic links in the flow

```bash
python ./create_symlinks.py
```

### 2. Test & run the flow with symlinks

In this sample, this flow will references some files in the [web-classification](../web-classification/README.md) flow. 
You can execute this flow with additional_include locally or submit it to cloud.


#### Test flow with single line data

```bash
# test flow with default input value in flow.dag.yaml
pf flow test --flow .

# test flow with input
pf flow test --flow . --inputs url=https://www.youtube.com/watch?v=o5ZQyXaAv1g answer=Channel evidence=Url

# test node in the flow
pf flow test --flow . --node convert_to_dict --inputs classify_with_llm.output="{\"category\": \"App\", \"evidence\": \"URL\"}"
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
