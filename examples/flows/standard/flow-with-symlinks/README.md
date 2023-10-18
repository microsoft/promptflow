# Flow with symlinks

User sometimes need to reference some common files or folders, this sample demos how to solve the problem using symlinks. 
But it has the following limitations. It is recommended to use **additional include**. 
Learn more: [flow-with-additional-includes](../flow-with-additional-includes/README.md)

1. For Windows user, by default need Administrator role to create symlinks.
2. For Windows user, directly copy the folder with symlinks, it will deep copy the contents to the location.
3. Need to update the git config to support symlinks.

**Notes**:
-  For Windows user, please grant user permission to [create symbolic links without administrator role](https://learn.microsoft.com/en-us/windows/security/threat-protection/security-policy-settings/create-symbolic-links).
    1. Open your `Local Security Policy`
    2. Find `Local Policies` -> `User Rights Assignment` -> `Create symbolic links`
    3. Add you user name to this policy then reboot the compute.

**Attention**:
- For git operations, need to set: `git config core.symlinks true`

## Tools used in this flow
- LLM Tool
- Python Tool

## What you will learn

In this flow, you will learn
- how to use symlinks in the flow

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Getting Started

### 1. Create symbolic links in the flow

```bash
python ./create_symlinks.py
```

### 2. Test & run the flow with symlinks

In this sample, this flow will references some files in the [web-classification](../web-classification/README.md) flow, and assume you already have required connection setup.
You can execute this flow or submit it to cloud.


#### Test flow with single line data

```bash
# test flow with default input value in flow.dag.yaml
pf flow test --flow .

# test flow with input
pf flow test --flow . --inputs url=https://www.youtube.com/watch?v=o5ZQyXaAv1g answer=Channel evidence=Url

# test node in the flow
pf flow test --flow . --node convert_to_dict --inputs classify_with_llm.output='{"category": "App", "evidence": "URL"}'
```


#### Run with multi-line data

```bash
# create run using command line args
pf run create --flow . --data ./data.jsonl --column-mapping url='${data.url}' --stream
# create run using yaml file
pf run create --file run.yml --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](../../../../docs/how-to-guides/use-column-mapping.md) for default behavior when `column-mapping` not provided in CLI.


#### Submit run to cloud

``` bash
# create run
pfazure run create --flow . --data ./data.jsonl --column-mapping url='${data.url}' --stream --runtime demo-mir --subscription <your_subscription_id> -g <your_resource_group_name> -w <your_workspace_name>
# pfazure run create --flow . --data ./data.jsonl --column-mapping url='${data.url}' --stream # automatic runtime

# set default workspace
az account set -s <your_subscription_id>
az configure --defaults group=<your_resource_group_name> workspace=<your_workspace_name>

pfazure run create --file run.yml --runtime demo-mir --stream
# pfazure run create --file run.yml --stream # automatic runtime
```
