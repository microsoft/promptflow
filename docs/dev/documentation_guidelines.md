# Promptflow Reference Documentation Guide

## Overview

This guide describes how to author Python docstrings for promptflow public interfaces. See our doc site at [Promptflow API reference documentation](https://microsoft.github.io/promptflow/reference/python-library-reference/promptflow.html).

## Principles

- **Coverage**: Every public object must have a docstring. For private objects, docstrings are encouraged but not required.
- **Style**: All docstrings should be written in [Sphinx style](https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html#the-sphinx-docstring-format) noting all types and if any exceptions are raised.
- **Relevance**: The documentation is up-to-date and relevant to the current version of the product.
- **Clarity**: The documentation is written in clear, concise language that is easy to understand.
- **Consistency**: The documentation has a consistent format and structure, making it easy to navigate and follow.


## How to write the docstring

First please read through [Sphinx style](https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html#the-sphinx-docstring-format) to have a basic understanding of sphinx style docstring.


### Write class docstring

Let's start with a class example:
```python
from typing import Dict, Optional, Union
from promptflow import PFClient

class MyClass:
    """One-line summary of the class.

    More detailed explanation of the class. May include below notes, admonitions, code blocks.

    .. note::

        Here are some notes to show, with a nested python code block:

        .. code-block:: python

            from promptflow import MyClass, PFClient
            obj = MyClass(PFClient())

    .. admonition:: [Title of the admonition]

        Here are some admonitions to show.

    :param client: Description of the client.
    :type client: ~promptflow.PFClient
    :param param_int: Description of the parameter.
    :type param_int: Optional[int]
    :param param_str: Description of the parameter.
    :type param_str: Optional[str]
    :param param_dict: Description of the parameter.
    :type param_dict: Optional[Dict[str, str]]
    """
    def __init__(
        client: PFClient,
        param_int: Optional[int] = None,
        param_str: Optional[str] = None,
        param_dict: Optional[Dict[str, str]] = None,
    ) -> None:
        """No docstring for __init__, it should be written in class definition above."""
        ...


```

**Notes**:

1. One-line summary is required. It should be clear and concise.
2. Detailed explanation is encouraged but not required. This part may or may not include notes, admonitions and code blocks.
    - The format like `.. note::` is called `directive`. Directives are a mechanism to extend the content of [reStructuredText](https://docutils.sourceforge.io/rst.html). Every directive declares a block of content with specific role. Start a new line with `.. directive_name::` to use the directive. 
    - The directives used in the sample(`note/admonition/code-block`) should be enough for basic usage of docstring in our project. But you are welcomed to explore more [Directives](https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#specific-admonitions).
3. Parameter description and type is required.
    - A pair of `:param [ParamName]:` and `:type [ParamName]:` is required.
    - If the type is a promptflow public class, use the `full path to the class` and prepend it with a "~". This will create a link when the documentation is rendered on the doc site that will take the user to the class reference documentation for more information.
        ```text
        :param client: Description of the client.
        :type client: ~promptflow.PFClient
        ```
    - Use `Union/Optional` when appropriate in function declaration. And use the same annotation after `:type [ParamName]:`
        ```text
        :type param_int: Optional[int]
        ```
4. For classes, include docstring in definition only. If you include a docstring in both the class definition and the constructor (init method) docstrings, it will show up twice in the reference docs.
5. Constructors (def `__init__`) should return `None`, per [PEP 484 standards](https://peps.python.org/pep-0484/#the-meaning-of-annotations).
6. To create a link for promptflow class on our doc site. `~promptflow.xxx.MyClass` alone only works after `:type [ParamName]` and `:rtype:`. If you want to achieve the same effect in docstring summary, you should use it with `:class:`:
     ```python
     """
     An example to achieve link effect in summary for :class:`~promptflow.xxx.MyClass`
     For function, use :meth:`~promptflow.xxx.my_func`
     """
     ```

7. There are some tricks to highlight the content in your docstring:
    - Single backticks (`): Single backticks are used to represent inline code elements within the text. It is typically used to highlight function names, variable names, or any other code elements within the documentation.
    - Double backticks(``): Double backticks are typically used to highlight a literal value.

8. If there are any class level constants you don't want to expose to doc site, make sure to add `_` in front of the constant to hide it.

### Write function docstring

```python
from typing import Optional

def my_method(param_int: Optional[int] = None) -> int:
    """One-line summary

    Detailed explanations.

    :param param_int: Description of the parameter.
    :type param_int: int
    :raises [ErrorType1]: [ErrorDescription1]
    :raises [ErrorType2]: [ErrorDescription2]
    :return: Description of the return value.
    :rtype: int
    """
    ...
```

In addition to `class docstring` notes:

1. Function docstring should include return values.
    - If return type is promptflow class, we should also use `~promptflow.xxx.[ClassName]`.
2. Function docstring should include exceptions that may be raised in this function.
    - If exception type is `PromptflowException`, use `~promptflow.xxx.[ExceptionName]`
    - If multiple exceptions are raised, just add new lines of `:raises`, see the example above.


## How to build doc site locally

You can build the documentation site locally to preview the final effect of your docstring on the rendered site. This will provide you with a clear understanding of how your docstring will appear on our site once your changes are merged into the main branch.

1. Setup your dev environment, see [dev_setup](./dev_setup.md) for details. Sphinx will load all source code to process docstring.
2. Install `langchain` package since it is used in our code but not covered in `dev_setup`.
3. Open a `powershell`, activate the conda env and navigate to `<repo-root>/scripts/docs` , run `doc_generation.ps1`:
    ```pwsh
    cd scripts\docs
    .\doc_generation.ps1 -WithReferenceDoc -WarningAsError
    ```
    - For the first time you execute this command, it will take some time to install `sphinx` dependencies. After the initial installation, next time you can add param `-SkipInstall` to above command to save some time for dependency check.
4. Check warnings/errors in the build log, fix them if any, then build again.
5. Open `scripts/docs/_build/index.html` to preview the local doc site.

## Additional comments

- **Utilities**: The [autoDocstring](https://marketplace.visualstudio.com/items?itemName=njpwerner.autodocstring) VSCode extension or GitHub Copilot can help autocomplete in this style for you.

- **Advanced principles**
  - Accuracy: The documentation accurately reflects the features and functionality of the product.
  - Completeness: The documentation covers all relevant features and functionality of the product.
  - Demonstration: Every docstring should include an up-to-date code snippet that demonstrates how to use the product effectively.



## References

- [AzureML v2 Reference Documentation Guide](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ml/azure-ai-ml/documentation_guidelines.md)
- [Azure SDK for Python documentation guidelines](https://azure.github.io/azure-sdk/python_documentation.html#docstrings)
- [How to document a Python API](https://review.learn.microsoft.com/en-us/help/onboard/admin/reference/python/documenting-api?branch=main)