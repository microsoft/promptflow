# Create and Use Your Own Custom Strong Type Connection
Connections serve as a secure method for managing credentials for external APIs and data sources. This document provides a step-by-step guide on how to create and use a custom strong type connection. The advantages of using a custom strong type connection are as follows:

* Enhanced user-friendly experience: Custom strong type connections offer an enhanced user-friendly experience compared to custom connections, as they eliminate the need to fill in connection keys.
* Improved intellisense experience: Custom strong type connections enhance the intellisense experience, offering real-time suggestions and auto-completion for available keys.
* Centralized information: Custom strong type connections provide a central location to access and view all available keys and value types. This centralization makes it easier to explore and create the connection.

For other connections types, please refer to [Connections](https://microsoft.github.io/promptflow/concepts/concept-connections.html).

## Prerequisites
- Please ensure that your [Prompt flow for VS Code](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow) is updated to at least version 1.2.1.
- Please install promptflow package and ensure that its version is 0.1.0b8 or later.
  ```
  pip install promptflow>=0.1.0b8
  ```

## Create your own custom strong type connection
Take [this file](https://github.com/microsoft/promptflow/blob/main/examples/tools/tool-package-quickstart/my_tool_package/tools/tool_with_custom_strong_type_connection.py) as an example, you can create your custom strong type connection as belows:

```python
from promptflow.connections import CustomStrongTypeConnection
from promptflow.contracts.types import Secret


class MyCustomConnection(CustomStrongTypeConnection):
    """My custom strong type connection.

    :param api_key: The api key.
    :type api_key: Secret
    :param api_base: The api base.
    :type api_base: String
    """
    api_key: Secret
    api_base: str = "This is a fake api base."

```

Make sure that you adhere to the following guidelines:

* You can define your own custom connection using any desired name, but make sure it inherits from the `CustomStrongTypeConnection` class.
  > [!Note] Please avoid using the `CustomStrongTypeConnection` class directly.
* Use the `Secret` type to denote that a key should be treated as a secret. This enhances security by scrubbing secret keys.
* You have the option to either include your custom connection class within your custom tool or separate it into a distinct Python file.
* Improve clarity for users by documenting your custom strong type connection using docstrings. Use `param` and `type` to provide explanations for each key, as shown in the following example:
  
  ```python
  """My custom strong type connection.

  :param api_key: The api key get from "https://xxx.com".
  :type api_key: Secret
  :param api_base: The api base.
  :type api_base: String
  """
  ```
  
  ```yaml
  $schema: https://azuremlschemas.azureedge.net/promptflow/latest/CustomStrongTypeConnection.schema.json
  name: "to_replace_with_connection_name"
  type: custom
  custom_type: MyCustomConnection
  module: my_tool_package.tools.my_tool_with_custom_strong_type_connection
  package: test-custom-tools
  package_version: 0.0.2
  configs:
    api_base: "This is a fake api base." # String type. The api base.
  secrets:
    api_key: <user-input> #  Secret type. The api key get from "https://xxx.com". Don't replace the '<user-input>' placeholder. The application will prompt you to enter a value when it runs.
  ```

## Develop a flow using package tools with custom strong type connections
To develop a flow using package tools with custom strong type connections, follow these steps:
* Step1: Refer to the [Create and Use Tool Package](create-and-use-tool-package.md#create-custom-tool-package) to build and install your tool package in your local environment.
  > [!Note] Once the new tool package is installed in your local environment, a window reload is necessary. This action ensures that the new tools and custom strong type connections become visible and accessible.

* Step2: Develop a flow with custom tools. Please take [this folder](https://github.com/microsoft/promptflow/tree/main/examples/tools/use-cases/custom-strong-type-connection-package-tool-showcase) as an example.

* Step3: Create a custom strong type connection using one of the following methods:
  - If the connection type hasn't been created previously, click the 'Add connection' button to create the connection.
    ![create_custom_strong_type_connection_in_node_interface](../../media/how-to-guides/develop-a-tool/create_custom_strong_type_connection_in_node_interface.png)
  - Click the 'Create connection' plus sign in the CONNECTIONS section.
    ![create_custom_strong_type_connection_add_sign](../../media/how-to-guides/develop-a-tool/create_custom_strong_type_connection_add_sign.png)
  - Click 'Create connection' plus sign in the Custom category.
    ![create_custom_strong_type_connection_in_custom_category](../../media/how-to-guides/develop-a-tool/create_custom_strong_type_connection_in_custom_category.png)

  Fill in the `values` starting with `to-replace-with` in the connection template.
  ![custom_strong_type_connection_template](../../media/how-to-guides/develop-a-tool/custom_strong_type_connection_template.png)

* Step4: Use the created custom strong type connection in your flow and run.
  ![use_custom_strong_type_connection_in_flow](../../media/how-to-guides/develop-a-tool/use_custom_strong_type_connection_in_flow.png)

## Develop a flow using script tools with custom strong type connections
To develop a flow using script tools with custom strong type connections, follow these steps:
* Step1: Develop a flow with python script tools. Please take [this folder](https://github.com/microsoft/promptflow/tree/main/examples/tools/use-cases/custom-strong-type-connection-script-tool-showcase) as an example.
* Step2: Using a custom strong type connection in a script tool is slightly different from using it in a package tool. When creating the connection, you will create a `CustomConnection`. Fill in the `keys` and `values` in the connection template.
  ![custom](../../media/how-to-guides/develop-a-tool/custom_connection_template.png)
* Step3: Use the created custom connection in your flow.
  ![use_custom_connection_in_flow](../../media/how-to-guides/develop-a-tool/use_custom_connection_in_flow.png)

## Local to cloud
When creating the necessary connections in Azure AI, you will need to create a `CustomConnection`. In the node interface of your flow, this connection will be displayed as the `CustomConnection` type.

Please refer to [Run prompt flow in Azure AI](https://microsoft.github.io/promptflow/cloud/azureai/quick-start.html) for more details.

Here is an example command:
```
pfazure run create --subscription 96aede12-2f73-41cb-b983-6d11a904839b -g promptflow -w my-pf-eus --flow D:\proj\github\ms\promptflow\examples\flows\standard\flow-with-package-tool-using-custom-strong-type-connection --data D:\proj\github\ms\promptflow\examples\flows\standard\flow-with-package-tool-using-custom-strong-type-connection\data.jsonl --runtime test-compute
```