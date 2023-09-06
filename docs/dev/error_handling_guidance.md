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

### Principals:

* **Human**:

    Concise, Clear, understandable

    > Good Example: *"Youd failed at the validation in PFS."*

    > Bad Example: *"You account does not have enough permission to submit the flow"*

* **Helpful**:

    Informative, Actionable with constructive suggestions

    > Good Example: *"The 'source' property is not specified for Node 'fetch_content'. To proceed, please specify with a valid source file path in your flow"*

    > Bad Example: *"'source' missing for node."*

* **Humble**:
    
    Kindly, without blame and judgement

    > Good Example: *"The field 'num' expects 'int' value" but assigned with string literal."*

    > Bad Example: *"You made a mistake to assign string literal to int 'num'*

### Rules

1. In PromptFlow, to fit in with above principals, the error message(format) shall corporate below segments at least:


    **Description/Cause**:

    Sentences to provide an explanation of the issue and details on how it occurs.

    > *"The input for flow is incorrect. Error: The value 'hello' for flow input 'num' in line '0' of input data does not match the expected type 'int'"*


    **Solution/Suggestion**:

    Sentences to offer valuable suggestions for preventing or resolving the issue, including clear directions for mitigation or resolution.

    > *"To fix this error, please input an integer value for 'num'"*

2. For value quote, placeholder value, variables in the error message, please try to enclose with single quote.

   Use above example, below values shall be single quoted in message body

   > 'num', '0', 'int'      

3. PromptFlow is designed with a strong commitment to user privacy and data security. As such, it does not log or record any user [PII](https://en.wikipedia.org/wiki/Personal_data) to mitigate the risk of unintentional data exposure. 

    However, when handling error messages, there are situations where you may need to address sensitive information. For instance, you might encounter scenarios where you need to raise exceptions due to unforeseen or inner exceptions, which may possibly include sensitive user data. As a contributor, it's essential to craft error messages that are both informative and secure.

    To achieve this, we recommend using the **message_format** member of PromptFlowException. You can encapsulate any sensitive information within variables within the message_format body. For instance, if error_type_and_message might contain sensitive user data, you can format it as follows:
    
    > *"Execution failure in '{node_name}': {error_type_and_message}"*

    When raising a PromptFlowException with the specified message_format, the **message** member will be automatically populated with the rendered values, maintaining security. For example:

    > *"Execution failure in 'MyTool': {UnSecureError}The input 'Washington Secret Order' from file 'order.11.2.35' is not well encrypted."*

    In PromptFlow, the **message_format** is logged and tracked, but the **message** itself is **only** visible to PromptFlow users. We prioritize the security and privacy of user data throughout the platform. 


### Samples


1. Flow Definition Error：Node circular


>*"Flow is defined incorrectly. Node circular dependency has been detected among the nodes in your flow. Please Kindly review the reference relationships for the nodes **['divide_num', 'divide_num_1', 'divide_num_2']** and resolve the circular reference issue in the flow."*


2. Input Data Error: Type not match


> "*The input for flow is incorrect. The value for flow input '**num**' in line **'0'** of input data does not match the expected type '**int**'. Please review the input data or adjust the input type of '**num**' in your flow.*"


3. File not found Error

>"*The file '**connections.json**' could not be located at '**/var/tmp/**'. This file is crucial for connection definition for flow execution. Please ensure that the missing file is provisioned in its designated location.*"

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