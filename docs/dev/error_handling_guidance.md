# Overview

We follow [the Microsoft API guideline](https://github.com/microsoft/api-guidelines/blob/vNext/Guidelines.md#7102-error-condition-responses) to define error codes.

As an implementation in PromptFlow, the exceptions are defined in a hierarchy style.
Here is a sample based on part of our existing exceptions:

```
PromptflowException
 |- SystemErrorException
 |   |- RunResultParseError
 |   |
 |   |- (more system errors defined here)
 |
 |- UserErrorException
     |- ValidationError
     |   |- ...
     |
     |- ToolValidationError
     |   |- JinjaParsingError
     |   |   |- ReservedVariableConnotBeUsed
     |   |
     |   |- PythonParsingError
     |       |- NoToolDefined
     |       |- MultipleToolsDefined
     |       |- BadFunctionInterface
     |
     |- (more user errors defined here)
```

* `PromptflowException` is the base class of all the exceptions, it defines some basic properties and operations for all the exception classes. It is not supposed to be raised directly.
* `SystemErrorException` and `UserErrorException` are two root errors. We only have these two at the root level and have no plan to add new ones. They are not supposed to be raised directly either.
* Other errors inherit from either `SystemErrorException` or `UserErrorException`, directly or indirectly, organized in a hierarchy style.


## "Error code" and "error code hierarchy"

The exception class name itself is used as "error code" (with some exceptions for root errors).

Since the exceptions are defined in a hierarchy style, each exception also has a corresponding 'error code hierarchy'.

For the sample above, the error code hierarchy for `NoToolDefined` is `UserError/ToolValidationError/PythonParsingError/NoToolDefined`.

We use the error code hierarchy to identify and classify errors.
* We could check the first section of the error code hierarchy to figure out whether the error is a user error or a system error.
* We could also check into details to see what specific error occurred.


## Conventions on error code definition

### Use specific error codes

* The error code should be specific. They can be detailed enough and should indicate only one failure or a limited subset of the failure scenario.
 i.e. Given `UserError/ToolValidationError/PythonParsingError/NoToolDefined`, it indicates that the tool validation failed due to no tool defined in the Python code.
* Generally, the leaf error code should be only raised in one place in the code. If it is suitable to be raised from multiple places, consider whether it can split into multiple codes.
 i.e. We may split `UserError/ToolValidationError/PythonParsingError` into `UserError/ToolValidationError/PythonParsingError/NoToolDefined` and `UserError/ToolValidationError/PythonParsingError/MultipleToolsDefined`.
* However, it is still open to allow error codes be shared in multiple places if:
  * The hierarchy goes too deep (>5?)
  * When you find it is too hard to get a proper name for the specific scenario.
  In this case, we need to set different message formats for each case to differenciate between them.

### Keep in mind that the error code hierarchy should be easy to read

The error codes are meant to be formatted as sections of the error code hierarchy. We should be aware that they are easy to read and easy to understand.
* Avoid using `Exception`, use `Error` instead when possible. i.e. prefer using `PythonParsingError` than `PythonParsingException`.
* The error code should not necessarily end with an `Error`. It could also be a shot phrase that describes the error itself, i.e. `NoToolDefined`, `ConnectionNotFound`, etc.


## Where to put the exception definitions

* Put some commonly used error codes (like UserError, ValidationError, etc) in [exceptions.py](../src/promptflow/promptflow/exceptions.py).
  * They are not supposed to be used directly, define subclasses of them to use.
* Put specific error codes in self-defined _errors.py. We can have multiple _errors.py files to separate them into module level. i.e. We can have `promptflow.contracts._errors`, `promptflow.executor._errors`, etc.
  * Here is a good example on how to organize the format of _errors.py: [runtime/_errors.py](../src/promptflow-sdk/promptflow/runtime/_errors.py)
  * Do not put specific error codes into the global exceptions.py, as:
    * They are for specific cases and are not supposed to be shared across multiple modules.
    * There will be a lot of such leaf error codes. They will make exceptions.py long and hard to manage.

## Error target

Indicates in which feature/part this exception is being raised. Can add new items if needed.

```python
class ErrorTarget:
    EXECUTOR = "Executor"
    FLOW_EXECUTOR = "FlowExecutor"
    NODE_EXECUTOR = "NodeExecutor"
    TOOL = "Tool"
    AZURE_RUN_STORAGE = "AzureRunStorage"
    SECRET_MANAGER = "SecretManager"
    RUNTIME = "Runtime"
    UNKNOWN = "Unknown"
```

Avoid passing the target parameter for every specific exception class. Set to its parent class when possible. i.e., for the sample above, the target is set to `ErrorTarget.TOOL` in `ToolValidationError` level, so that all the child classes will no need to set one by one.

> NOTE: This part may change in the future, the target could be detected automatically and no need to set any more.

## "Error message format" vs "error message"

Basically, the exception should be initialized with the "error message format" and "error message parameters" and then it can format the final "error message" by itself.

* The "error message format" does not contain sensitive data and it is safe to be logged.
* The "error message" is meant to be displayed to the user but should not be logged.

Currently, most of the exceptions are initialized by a simple "error message". It is formatted outside of the exception and thus the exception does not have the "error message format" and "error message parameters" information.

We recommend to use the "error format + error parameters" to initialize the exception instead of setting the "error message" directly.
However, the "error message" initialization is still supported for backward compatibility.

* Current style: Pass the formatted message into exception (To be deprecated)
```python
raise MultipleToolsDefined(
    f"Expected 1 but collected {len(tools)} tools: {tool_names}."
)
```

* Recommended style: Pass the message format and parameters into exception
```python
raise MultipleToolsDefined(
    message_format="Expected 1 but collected {count} tools: {tool_names}.",
    count=len(tools),
    tool_names=tool_names,
)
```


# How-to guide

## Define your error message/message_format

Error messages principals:

* **Human**:

 Concise, Clear, understandable

* **Helpful**:

Informative, Actionable, with constructive suggestions

* **Humble**:
Kindly, without blame and judgement

For PromptFlow, to fit in with above principals, the error message(format) shall corporate below segments at least:


**Cause Part**:

>Sentences to provide an explanation of the issue and detail how it occurs.

**Solution Part**:

>Sentences to offer valuable suggestions for preventing or resolving the issue, including clear directions for mitigation or resolution.


### Samples

1. Brief example to explain what is the issue in your flow submission. Provide directions on how to resolve it by list the problematic nodes names for further review.

>*"Node circular dependency has been detected among the nodes in your flow. Kindly review the reference relationships for the nodes **['divide_num', 'divide_num_1', 'divide_num_2']** and resolve the circular reference issue in the flow."*


2. Concise example to accurately locate the essence of problem with nodes, input name/value and line information. Suggest further step as well.

> *The value '**hello**' for flow input '**num**' in line **0** of input data does not match the expected type '**int**'. Please review the input data or adjust the input type of '**num**' in your flow.*


3. Great example to include what kind of rule the client shall follow when specifying chat role format. Also point out the issues in current prompt specification. Finally, it highlights on how to get the api work with helpful link and step.

>*The Chat API requires a specific format for prompt definition, and the prompt should include separate lines as role delimiters: '**assistant**:',
'**user**:','**system**:','**function**:'. Current parsed role '**what is your name**' does not meet the requirement. If you intend to use the Completion API, please select the appropriate API type and deployment name. If you do intend to use the Chat API, please refer to the guideline at **https://aka.ms/pfdoc/chat-prompt** or view the samples in our gallery that contain '**Chat**' in the name.*

## Define your error codes

Simply inherit from a common error code as the start point.

In the example below, a base `ToolValidationError` is defined inheriting from the root error code `UserError`.
Note that the `target` is set to the `ToolValidationError`. We do not need to set target for its child error codes.

```python
class ToolValidationError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    def __init__(self, message):
        super().__init__(message, target=ErrorTarget.TOOL)


class JinjaParsingError(ToolValidationError):
    pass


class ReservedVariableCannotBeUsed(JinjaParsingError):
    pass


class PythonParsingError(ToolValidationError):
    pass


class NoToolDefined(PythonParsingError):
    pass


class MultipleToolsDefined(PythonParsingError):
    pass


class BadFunctionInterface(PythonParsingError):
    pass
```

## Raise specific error code in your code

Just raise the error as other exceptions.


```
def generate_python_tool(name, content, source=None):
    try:
        m = types.ModuleType("promptflow.dummy")
        exec(content, m.__dict__)
    except Exception as e:
        msg = f"Parsing python got exception: {e}"
        raise PythonParsingError(message_format=msg) from e
    tools = collect_tool_functions_in_module(m)
    if len(tools) == 0:
        raise NoToolDefined(message_format="No tool found in the python script.")
    elif len(tools) > 1:
        tool_names = ", ".join(t.__name__ for t in tools)
        raise MultipleToolsDefined(
            message_format="Expected 1 but collected {tool_count} tools: {tool_names}.",
            tool_count=len(tools),
            tool_names=tool_names,
        )
```

When there is an inner error that caused your exception, use `raise .. from` to set it as the cause:
```python
    try:
        ...
    except Exception as e:
        msg = f"Parsing python got exception: {e}"
        raise PythonParsingError(message_format=msg) from e
```

> NOTE: Currently, it is required to format the inner error into your error message explicitly. In the future, we may change the logic to do the format automatically.