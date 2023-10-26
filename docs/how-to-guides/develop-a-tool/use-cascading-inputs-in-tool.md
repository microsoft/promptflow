# Use Cascading Inputs in Tool

Cascading settings between inputs are frequently used in situations where the selection in one input field determines what subsequent inputs should be shown.
This approach help in creating a more efficient, user-friendly, and error-free input process.
This article will guide you through the process of implementing cascading settings for tool inputs.

## Prerequisites
Please ensure that your [Prompt flow for VS Code](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow) is updated to version 1.2.0 or later.


## Create tool with cascading inputs
We will provide a hands-on tool example to showcase the implementation of cascading settings between inputs within a tool. 
The availability of "student_id" and "teacher_id" inputs is determined by the value of the "user_type" input in this tool .
Below shows how to support this cascading setting in both tool code and tool yaml.

1. Develop your tool within the def function, referring to [tool_with_enabled_by_value.py](https://github.com/microsoft/promptflow/blob/main/examples/tools/tool-package-quickstart/my_tool_package/tools/tool_with_enabled_by_value.py) as an example. You need to pay attention to some key points:
    * Use the @tool decorator to identify the function as a tool.
    * When an input should only take on a certain set of fixed values, an Enum class such as "UserType" as shown in the following example can be created.
    * Within the tool's logic, various inputs may be used depending on the value of input "user_type".

```python
from enum import Enum

from promptflow import tool


class UserType(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"


@tool
def my_tool(user_type: Enum, student_id: str = "", teacher_id: str = "") -> str:
    """This is a dummy function to support enabled by feature.

    :param user_type: user type, student or teacher.
    :param student_id: student id.
    :param teacher_id: teacher id.
    :return: id of the user.
    If user_type is student, return student_id.
    If user_type is teacher, return teacher_id.
    """
    if user_type == UserType.STUDENT:
        return student_id
    elif user_type == UserType.TEACHER:
        return teacher_id
    else:
        raise Exception("Invalid user.")
```

2. Following the guide [Create and Use Tool Package](create-and-use-tool-package.md) to generate a tool yaml for your tool, then you need to update this tool yaml manually to transition from common inputs to cascading inputs.

Referring to the [tool_with_enabled_by_value.yaml](https://github.com/microsoft/promptflow/blob/main/examples/tools/tool-package-quickstart/my_tool_package/yamls/tool_with_enabled_by_value.yaml) as an example, You need incorporate two configurations for cascading inputs: "enabled_by" and "enabled_by_value". The "enabled_by_value" in one input means that this input is enabled and displayed by the value of the input referred to in the "enabled_by" attribute.

```yaml
my_tool_package.tools.tool_with_enabled_by_value.my_tool:
  function: my_tool
  inputs:
    user_type:
      type:
      - string
      enum:
        - student
        - teacher
    student_id:
      type:
      - string
      # This input is enabled by the input "user_type".
      enabled_by: user_type
      # This input is enabled when "user_type" is "student".
      enabled_by_value: [student]
    teacher_id:
      type:
        - string
      enabled_by: user_type
      enabled_by_value: [teacher]
  module: my_tool_package.tools.tool_with_enabled_by_value
  name: My Tool with Enabled By Value
  description: This is my tool with enabled by value
  type: python
```
> Note: The "enabled_by_value" in the tool yaml is of list type, implying that a single input can be enabled by multiple values from the dependent input.

## Use your tool from VSCode Extension
After you build and share the tool package, you can use your tool from VSCode Extension according to [Create and Use Tool Package](create-and-use-tool-package.md).
Here we use an existing flow to demonstrate the experience, open [this flow](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/flow-with-enabled-by-value) in VS Code extension. 

Before you select the "user_type" input, both "student_id" and "teacher_id" inputs are disabled and hidden.
![before_user_type_selected.png](../../media/how-to-guides/develop-a-tool/before_user_type_selected.png)

However, after you select the "user_type" input, the corresponding input is enabled and shown.
![after_user_type_selected_with_student.png](../../media/how-to-guides/develop-a-tool/after_user_type_selected_with_student.png)
![after_user_type_selected_with_teacher.png](../../media/how-to-guides/develop-a-tool/after_user_type_selected_with_teacher.png)



## FAQ
### How to use multi-layer cascading inputs in tool?
If you are dealing with multiple levels of cascading inputs, you can effectively manage the dependencies between them by using the "enabled_by" and "enabled_by_value" attributes. Here's a hypothetical YAML example.
```yaml
my_tool_package.tools.tool_with_multi_layer_cascading_inputs.my_tool:
  function: my_tool
  inputs:
    event_type:
      type:
      - string
      enum:
        - corporate
        - private
    corporate_theme:
      type:
      - string
      # This input is enabled by the input "event_type".
      enabled_by: event_type
      # This input is enabled when "event_type" is "corporate".
      enabled_by_value: [corporate]
      enum:
        - seminar
        - team_building
    seminar_location:
      type:
      - string
      # This input is enabled by the input "corporate_theme".
      enabled_by: corporate_theme
      # This input is enabled when "corporate_theme" is "seminar".
      enabled_by_value: [seminar]
    private_theme:
      type:
        - string
      # This input is enabled by the input "event_type".
      enabled_by: event_type
      # This input is enabled when "event_type" is "private".
      enabled_by_value: [private]
  module: my_tool_package.tools.tool_with_multi_layer_cascading_inputs
  name: My Tool with Multi-Layer Cascading Inputs
  description: This is my tool with multi-layer cascading inputs
  type: python
```
When the tool is run, the inputs will be displayed in a cascading manner. As each input is filled out, any inputs that are dependent on it and have their "enabled_by_value" condition met will be enabled.
