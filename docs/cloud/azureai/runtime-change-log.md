# Change log of default runtime image
## Runtime image
In Azure Machine Learning prompt flow, runtime provides the environment to execute flows. The default runtime includes a pre-built Docker image, which contains all necessary dependent packages.

### Pull image
The image can be pulled by specifying a runtime version and executing the following command:
```
docker pull mcr.microsoft.com/azureml/promptflow/promptflow-runtime-stable:<runtime_version>
```

### Check image version
You can check the runtime image version from the flow execution log:
![img](../../media/cloud/runtime-change-log/runtime-version.png)

## Change log
Default runtime image is continuously updated, and here we record the new features and fixed bugs of each image version.
### 20240124.v3

#### New features
- Support downloading data from Azure Machine Learning registry for batch run.
- Show node status when one line of a batch run times out.

#### Bugs fixed
- Fix the bug that exception raised during preparing data is not set in run history.
- Fix the bug that unexpected exception is raised when executor process crushes. 

### 20240116.v1

#### New features
NA

#### Bugs fixed
- Add validation for wrong connection type for LLM tool.

### 20240111.v2

#### New features
- Support error log scrubbing for heron jobs.

#### Bugs fixed
- Fixed the compatibility issue between runtime and promptflow package < 1.3.0
