# Flow with enabled_by_value
This sample demos how to use "enabled_by_value" tool in flows.

## Tools used in this flow
- Python Tool

## What you will learn

In this flow, you will learn
- how to add "enabled_by_value" tool to the flow

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```


## Run flow

### 1. Add "enabled_by_value" tool to flow
You need to have a tool which support "enabled_by_value" first, then you can add "enabled_by_value" tool into the [`flow.dag.yaml`](flow.dag.yaml). 

### 2. Test flow with "enabled_by_value" tool
```bash
pf flow test --flow .
```

### 3. List and show run meta
```bash
# list created run
pf run list

# get a sample run name
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("basic_variant_0")) | .name'| head -n 1 | tr -d '"')

# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name

# visualize run in browser
pf run visualize --name $name
```
