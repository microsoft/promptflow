# Next Items
0. Run it locally
1. "Validate" Flow - create promptflow folder with assets (like yaml)
  ```
  pf init .
  ```
  `fast_api` precedent or `mlflow`
  vscode extension with a selection
2. run (locally / cloud)
  ```
  pf validate ...
  ```
  for testing container locally

  ```
  pf run ...--name my_flow_thingie
  ```
  for testing in the cloud
3. bulk run / batch run
```
pf batch --input ./data/denormalized-flat.jsonl --output ./my_output_file.jsonl
```
this just runs the thing

4. evaluation - metrics
  ```
  pf evaluate --output ./my_output_file.jsonl --evaluation accuracy --mapping [d=>d]
  ```

5. deploy
```
pf deploy --sub 12323-2323 --workspace hal --resrouce_group robots
```
Think about `azd` in this case or something Joe/Rong
can come up with.

6. monitor
```
az ml online-deployment update -f promptflow-momo-deployment.yaml
```

AK Instructions

```
Deploy a PF to endpoint
You need to think ahead and make sure the PF has outputs that you want to monitor
Enable data collection on the PF endpoint
"eventually" this is just a checkbox in the UI
interim: you use the CLI like this:
az ml online-deployment update -f promptflow-momo-deployment.yaml
where the yaml is like this
$schema: https://azuremlschemas.azureedge.net/latest/managedOnlineDeployment.schema.json
name: green
endpoint_name: copilot-demo-eastus-momo
#model: azureml:copilot-demo-eastus-momo:1
#model: azureml:copilot-demo-momo-demo2:1
model: azureml:copilot-demo-eastus-momo:2
environment_variables:
  PROMPTFLOW_RUN_MODE: serving
  MAX_CONCURRENT_REQUESTS: 10
  PROMPTFLOW_MDC_ENABLE: "true"
  # PRT_CONFIG_OVERRIDE: deployment.subscription_id=15ae9cb6-95c1-483d-a0e3-b1a1a3b06324,deployment.resource_group=copilot-demo-eastus,deployment.workspace_name=copilot-demo-eastus
  PROMPTFLOW_ENCODED_CONNECTIONS: "H4sIADy+ZmQC/12P3W6CQBCFX8XsdZd/lXqHStBqoKk0tr0xyzIUaGXX3QWrxncv0JiYXk1mzplvzlyQF3lLPIc9Q5PBBRFe7BIioW1QrhSXE10njBQa41C1hZxrARplex09DHr3F5w6s2Flhknh0bHtzKHJmIwSd5hm7ihzs7GbuDe7OvEe3oNuwwaELFjVzS3DsrFhY3OIuYCmgCO6tq69xJR9SiCC5n3QWRTsNr73Mlvs/HD+HC3D+D4zZbz4Zgqn7WMYiFS11P62tWNRpewotQpUd/8OtAzn/ltH4YKlNVXyn77y3zvVzMO4jElSNovtVtQQ50/r12DKDtYoAetnNV0favFhlkHknTcwdaNy6KDr9ReV8jb0awEAAA=="
environment: azureml://registries/promptflow-preview/environments/promptflow-runtime/versions/11.1 # or creating your own env if there's any extra dependencies
# shouldn’t change the data_collector section
data_collector:
  collections:
    promptflow_inputs:
      enabled: "true"
    promptflow_outputs:
      enabled: "true"
request_settings:
  max_concurrent_requests_per_instance: 10
  request_timeout_ms: 90000
instance_type: Standard_DS3_v2
instance_count: 3
Monitor the endpoint
After the above is done, the monitoring UI will expose the PF-related signals
```
