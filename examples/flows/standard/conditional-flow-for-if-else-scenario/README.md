# Conditional flow for if-else scenario

This example is a conditonal flow for if-else scenario.

In this flow, it checks if an input query passes content safety check. If it's denied, we'll return a default response; otherwise, we'll call LLM to get a response and then summarize the final results.

By following this example, you will learn how to create a conditional flow using the `activate config`.

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Run flow

- Test flow/node
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with flow inputs
pf flow test --flow . --inputs query="What is Prompt flow?"
```

- List and show run meta
```bash
# list created run
pf run list

# get a sample run name
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("basic_default")) | .name'| head -n 1 | tr -d '"')

# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name

# visualize run in browser
pf run visualize --name $name
```
