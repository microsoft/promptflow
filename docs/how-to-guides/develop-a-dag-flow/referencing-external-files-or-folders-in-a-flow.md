# Referencing external files/folders in a flow

Sometimes, pre-existing code assets are essential for the flow reference. In most cases, you can accomplish this by importing a Python package into your flow. However, if a Python package is not available or it is heavy to create a package, you can still reference external files or folders located outside of the current flow folder by using our **additional includes** feature in your flow configuration.

This feature provides an efficient mechanism to list relative file or folder paths that are outside of the flow folder, integrating them seamlessly into your flow.dag.yaml. For example:

```yaml
additional_includes:
- ../web-classification/classify_with_llm.jinja2
- ../web-classification/convert_to_dict.py
- ../web-classification/fetch_text_content_from_url.py
- ../web-classification/prepare_examples.py
- ../web-classification/summarize_text_content.jinja2
- ../web-classification/summarize_text_content__variant_1.jinja2
```

You can add this field `additional_includes` into the flow.dag.yaml. The value of this field is a list of the **relative file/folder path** to the flow folder.

Just as with the common definition of the tool node entry, you can define the tool node entry in the flow.dag.yaml using only the file name, eliminating the need to specify the relative path again. For example:

```yaml
nodes:
- name: fetch_text_content_from_url
  type: python
  source:
    type: code
    path: fetch_text_content_from_url.py
  inputs:
    url: ${inputs.url}
- name: summarize_text_content
  use_variants: true
- name: prepare_examples
  type: python
  source:
    type: code
    path: prepare_examples.py
  inputs: {}
```

The entry file "fetch_text_content_from_url.py" of the tool node "fetch_text_content_from_url" is located in "../web-classification/fetch_text_content_from_url.py", as specified in the additional_includes field. The same applies to the "summarize_text_content" tool nodes.

> **Note**:
>
> 1. If you have two files with the same name located in different folders specified in the `additional_includes` field, and the file name is also specified as the entry of a tool node, the system will reference the **last one** it encounters in the `additional_includes` field.
> > 1. If you have a file in the flow folder with the same name as a file specified in the `additional_includes` field, the system will prioritize the file listed in the `additional_includes` field.
Take the following YAML structure as an example:

```yaml
additional_includes:
- ../web-classification/prepare_examples.py
- ../tmp/prepare_examples.py
...
nodes:
- name: summarize_text_content
  use_variants: true
- name: prepare_examples
  type: python
  source:
    type: code
    path: prepare_examples.py
  inputs: {}
``` 

In this case, the system will use "../tmp/prepare_examples.py" as the entry file for the tool node "prepare_examples". Even if there is a file named "prepare_examples.py" in the flow folder, the system will still use the file "../tmp/prepare_examples.py" specified in the `additional_includes` field.

> Tips:
> The additional includes feature can significantly streamline your workflow by eliminating the need to manually handle these references.
> 1. To get a hands-on experience with this feature, practice with our sample [flow-with-additional-includes](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/flow-with-additional-includes).
> 1. You can learn more about [How the 'additional includes' flow operates during the transition to the cloud](../../cloud/azureai/run-promptflow-in-azure-ai.md#run-snapshot-of-the-flow-with-additional-includes).