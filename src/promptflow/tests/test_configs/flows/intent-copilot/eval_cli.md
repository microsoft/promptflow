# Run evaluation from cloud bulk test

## CLI

```shell
# run with local eval
## Note: cloud evaluation doesn't support specify input or output now 
pf eval --variants "BULK_TEST_URL1, BULK_TEST_URL2" --flow ../classification_accuracy_evaluation --input ./data/denormalized-flat.jsonl --column-mapping "k1=v1,k2=v2" --runtime pfci
# run with bulitin eval
pf eval --variants "BULK_TEST_URL" --flow azureml://flows/QnARelevanceEvaluation --input ./data/denormalized-flat.jsonl --column-mapping "k1=v1,k2=v2" --runtime pfci
```

## SDK

```python
# load cloud bulk test run
bulk_test_url = "https://ml.azure.com/prompts/flow/3e123da1-f9a5-4c91-9234-8d9ffbb39ff5/9ed90c96-4e86-4873-8775-19d1917b02ec/bulktest/69602a09-3f81-45af-ba40-8de8c9909e1b/details?wsid=/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourcegroups/promptflow/providers/Microsoft.MachineLearningServices/workspaces/promptflow-eastus"
bulk_test_run = BulkFlowRun.load_from_url(bulk_test_url)

# run evaluation, same as before
eval_path = flow_test_dir / "classification_accuracy_evaluation/"
classification_accuracy_eval = load_flow(source=eval_path)

bulk_flow_run_input = BulkFlowRunInput(
    data=flow_test_dir / "webClassification20.csv",
    variants=[bulk_test_run],
    inputs_mapping={
        "groundtruth": "data.url",
        "prediction": "data.answer",
    },
)

baseline_accuracy = classification_accuracy_eval.submit_bulk_run(
    data=bulk_flow_run_input,
    runtime=runtime,
)

```