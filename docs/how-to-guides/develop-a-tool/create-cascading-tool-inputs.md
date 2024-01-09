# Creating cascading tool inputs

Cascading input settings are useful when the value of one input field determines which subsequent inputs are shown. This makes the input process more streamlined, user-friendly, and error-free. This guide will walk through how to create cascading inputs for your tools.

## Prerequisites
- Please make sure you have the latest version of [Prompt flow for VS Code](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow) installed (v1.2.0+).
- Please install promptflow package and ensure that its version is 1.0.0 or later.
  ```
  pip install promptflow>=1.0.0
  ```

## Create a tool with cascading inputs
We'll build out an example tool to show how cascading inputs work. The `student_id` and `teacher_id` inputs will be controlled by the value selected for the `user_type` input. Here's how to configure this in the tool code.

Develop the tool function, following the [cascading inputs example](https://github.com/microsoft/promptflow/blob/main/examples/tools/tool-package-quickstart/my_tool_package/tools/tool_with_cascading_inputs.py). Key points:
 * Use the `@tool` decorator to mark the function as a tool.
 * Define `UserType` as an Enum class, as it accepts only a specific set of fixed values in this example.
 * Conditionally use inputs in the tool logic based on `user_type`.
 * Add `enabled_by` and `enabled_by_value` to control visibility of dependent inputs.
    * The `enabled_by` attribute specifies the input field, which must be an enum type, that controls the visibility of the dependent input field.
    * The `enabled_by_value` attribute defines the accepted enum values from the `enabled_by` field that will make this dependent input field visible.
    > Note: `enabled_by_value` takes a list, allowing multiple values to enable an input.

```python
from enum import Enum

from promptflow.entities import InputSetting
from promptflow import tool


class UserType(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"


@tool(
    name="My Tool with Enabled By Value",
    description="This is my tool with enabled by value",
    input_settings={
        "teacher_id": InputSetting(enabled_by="user_type", enabled_by_value=[UserType.TEACHER]),
        "student_id": InputSetting(enabled_by="user_type", enabled_by_value=[UserType.STUDENT]),
    }
)
def my_tool(user_type: UserType, student_id: str = "", teacher_id: str = "") -> str:
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


## Use the tool in VS Code
Once you package and share your tool, you can use it in VS Code per the [tool package guide](create-and-use-tool-package.md). We have a [demo flow](https://github.com/microsoft/promptflow/tree/main/examples/tools/use-cases/cascading-inputs-tool-showcase) you can try.

Before selecting a `user_type`, the `student_id` and `teacher_id` inputs are hidden. Once you pick the `user_type`, the corresponding input appears.
![before_user_type_selected.png](../../media/how-to-guides/develop-a-tool/before_user_type_selected.png)
![after_user_type_selected_with_student.png](../../media/how-to-guides/develop-a-tool/after_user_type_selected_with_student.png)
![after_user_type_selected_with_teacher.png](../../media/how-to-guides/develop-a-tool/after_user_type_selected_with_teacher.png)



## FAQs
### How do I create multi-layer cascading inputs?
If you are dealing with multiple levels of cascading inputs, you can effectively manage the dependencies between them by using the `enabled_by` and `enabled_by_value` attributes. For example:
```python
from enum import Enum

from promptflow.entities import InputSetting
from promptflow import tool


class EventType(str, Enum):
    CORPORATE = "corporate"
    PRIVATE = "private"


class CorporateTheme(str, Enum):
    SEMINAR = "seminar"
    TEAM_BUILDING = "team_building"


@tool(
    name="My Tool with Multi-Layer Cascading Inputs",
    description="This is my tool with multi-layer cascading inputs",
    input_settings={
        "corporate_theme": InputSetting(enabled_by="event_type", enabled_by_value=[EventType.CORPORATE]),
        "seminar_location": InputSetting(enabled_by="corporate_theme", enabled_by_value=[CorporateTheme.SEMINAR]),
        "private_theme": InputSetting(enabled_by="event_type", enabled_by_value=[CorporateTheme.PRIVATE]),
    }
)
def my_tool(event_type: EventType, corporate_theme: CorporateTheme, seminar_location: str, private_theme: str) -> str:
    """This is a dummy function to support enabled by feature."""
    pass
```
Inputs will be enabled in a cascading way based on selections.