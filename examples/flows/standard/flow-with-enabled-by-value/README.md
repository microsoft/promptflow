# Flow with enabled_by_value
This sample demos how to use "enabled_by_value" tool in flows. The "enabled_by_value" is designed to support cascading settings between inputs for tool. 
Cascading settings between inputs are frequently used in situations where the selection in one input field determines what subsequent inputs should be shown. 
This approach help in creating a more efficient, user-friendly, and error-free input process.

## Tools used in this flow
- Python Tool

## What you will learn

In this flow, you will learn how to add "enabled_by_value" tool to the flow.

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