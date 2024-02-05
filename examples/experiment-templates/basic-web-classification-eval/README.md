# Basic web classification evaluation experiment
This folder contains example experiment template YAML file which runs a web classification flow then evaluate the flow result with
a given ground truth.

## Prerequisites
- Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Test flow in experiment template with sample inputs
To test the flow in experiment template with sample inputs, execute following command:
```bash
pf flow test --flow ../../flows/standard/web-classification/ --experiment basic.exp.yml --inputs url="https://arxiv.org/abs/2307.04767" answer="Academic"
```
You are able to see the flow result of each node in experiment in the console.
```json
{
  "main": {
    "category": "Academic",
    "evidence": "Text content"
  },
  "eval": {
    "grade": "Incorrect"
  }
}
```

## Run experiment template with data file
To run experiment template with data file, an experiment entity needs to be created based on template, all the node snapshots
will be created under experiment folder at `~/.promptflow/.exps/<exp-name>`. Create the experiment via:
```bash
pf experiment create --template basic.exp.yaml -n my_experiment
```

Then start the experiment with command:
```bash
pf experiment start -n my_experiment
```

## Manage experiments
To list experiments:
```bash
pf experiment list
```

To show experiment with specific name:
```bash
pf experiment show -n my_experiment
```
