# Change log of default runtime image
In Azure Machine Learning prompt flow, the execution of flows is facilitated by using runtimes. Within the Azure Machine Learning workspace, a runtime serves as computing resource that enable customers to execute flows.

A runtime includes a pre-built Docker image (users can also provide their own custom image), which contains all necessary dependency packages.

This Docker image is continuously updated, and here we record the new features and fixed bugs of each image version. The image can be pulled by specifying a runtime version and execute the following command:
```
docker pull mcr.microsoft.com/azureml/promptflow/promptflow-runtime-stable:<runtime_version>
```
You can check the runtime image version from the flow execution log:
![img](../../media/cloud/runtime-change-log/runtime-version.png)

## 20240116.v1

### New features
NA

### Bugs fixed

- Add validation for wrong connection type for LLM tool.

## 20240111.v2

### New features

- Support error log scrubbing for heron jobs.

### Bugs fixed
 
- Fixed the compatibility issue between runtime and promptflow package < 1.3.0
