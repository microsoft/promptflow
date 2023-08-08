# Run and evaluate a flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](https://aka.ms/azuremlexperimental).
:::

You can use an evaluation method to evaluate your flow. The evaluation methods are also flows which use Python or LLM etc., to calculate metrics like accuracy, relevance score.

In this guide, we use [classification-accuracy-eval](https://github.com/microsoft/promptflow/tree/main/examples/flows/evaluation/classification-accuracy-eval) flow to evaluate. This is a flow illustrating how to evaluate the performance of a classification system. It involves comparing each prediction to the groundtruth and assigns a `Correct` or `Incorrect` grade, and aggregating the results to produce metrics such as `accuracy`, which reflects how good the system is at classifying the data.



## Evaluate your run
### Run evaluation flow against run

Firstly set the working directory to `<path-to-the-sample-repo>/examples/flows/`

::::{tab-set}

:::{tab-item} CLI
:sync: CLI

**Create a flow run to be evaluated**

To evaluate a flow run, you need an already finished run and pass it to the evaluation method flow. Let's create a run `my_first_run` with flow [web-classification](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification).

```sh
pf run create --flow standard/web-classification --data standard/web-classification/data.jsonl --name my_first_run --stream
```

**Evaluate the finished flow run**

After the run is finished, you can evaluate the run with below command, compared with the normal run create command, note there are two extra arguments:

- `column-mapping`: A string value represents sources of the input data that are needed for the evaluation method. The sources can be from the flow run output or from your test dataset.
  - If the data column is in your test dataset, then it is specified as `${data.<column_name>}`.
  - If the data column is from your flow output, then it is specified as `${run.outputs.<output_name>}`.
- `run`: The run name of the flow run to be evaluated.

```sh
pf run create --flow evaluation/classification-accuracy-eval --data standard/web-classification/data.jsonl --column-mapping "groundtruth=${data.answer},prediction=${run.outputs.category}" --run my_first_run --stream
```

Same as the previous run, you can specify the evaluation run name with `--name my_first_eval_run` in above command.

With a run name, you can easily stream or view the run details using below commands:

```sh
pf run stream -n my_first_eval_run  # same as "--stream" in command "run create"
pf run show-details -n my_first_eval_run
pf run show-metrics -n my_first_eval_run
```

Since now you have two different runs `my_first_run` and `my_first_eval_run`, you can visualize the two runs at the same time with below command.

```sh
pf run visualize -n "my_first_run,my_first_eval_run"
```

A web browser will be opened to show the visualization result.

![q_0](../../media/community/local/visualize_run.png)

:::

:::{tab-item} SDK
:sync: SDK

**Create a flow run to be evaluated**

To evaluate a flow run, you need an already finished run and pass it to the evaluation method flow. Let's create a run `base_run` with flow [web-classification](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification).

```python
from promptflow import PFClient

pf = PFClient()
flow = "standard/web-classification" # set the flow directory
data= "standard/web-classification/data.jsonl" # set the data file

# create a run
base_run = pf.run(
    flow=flow,
    data=data,
)
```

**Evaluate the finished flow run**

After the run is finished, you can evaluate the run with below command, compared with the normal run create command, note there are two extra arguments:

- `column-mapping`: A dictionary represents sources of the input data that are needed for the evaluation method. The sources can be from the flow run output or from your test dataset.
  - If the data column is in your test dataset, then it is specified as `${data.<column_name>}`.
  - If the data column is from your flow output, then it is specified as `${run.outputs.<output_name>}`.
- `run`: The run name or run instance of the flow run to be evaluated.
  
```python
# set eval flow path
eval_flow = "evaluation/classification-accuracy-eval"
data= "standard/web-classification/data.jsonl"

# run the flow with exisiting run
eval_run = pf.run(
    flow=eval_flow,
    data=data,
    run=base_run,
    column_mapping={"groundtruth": "${data.answer}","prediction": "${run.outputs.category}"},  # map the url field from the data to the url input of the flow
)

# stream the run until it's finished
pf.stream(eval_run)

# get the inputs/outputs details of a finished run.
details = pf.get_details(eval_run)
details.head(10)

# view the metrics of the eval run
metrics = pf.get_metrics(eval_run)
print(json.dumps(metrics, indent=4))

# visualize both the base run and the eval run
pf.visualize([base_run, eval_run])

```

A web browser will be opened to show the visualization result.

![q_0](../../media/community/local/visualize_run.png)

:::

:::{tab-item} VS Code Extension
:sync: VS Code Extension
(WIP)
:::

::::

## Next steps

Learn more about:
- [Tune prompts with variants](./tune-prompts-with-variants.md)
- [Deploy and export a flow](./deploy-and-export-a-flow.md)