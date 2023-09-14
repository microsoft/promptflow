# Column mapping

In this document, we will introduce how to map inputs with column mapping when running a flow.

## Column mapping introduction

Column mapping is a mapping from flow input name to specified values.
If specified, the flow will be executed with provided value for specified inputs.
The following types of values in column mapping are supported:

- `${data.<column_name>}` to reference from your test dataset.
- `${run.outputs.<output_name>}` to reference from your flow output.
- `STATIC_VALUE` to create static value for all lines for specified column.

## Flow inputs override priority

Flow input values are overridden according to the following priority:

"specified in column mapping" > "default value" > "same name column in provided data".

For example, if we have a flow with following inputs:

```yaml
inputs:
  input1:
    type: string
    default: "default_val1"
  input2:
    type: string
    default: "default_val2"
  input3:
    type: string
  input4:
    type: string
...
```

And the flow will return each inputs in outputs.

With the following data

```json
{"input3": "val3_in_data", "input4": "val4_in_data"}
```

And use the following YAML to run

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json
flow: path/to/flow
# my_flow has default value val2 for key2
data: path/to/data
# my_data has column key3 with value val3
column_mapping:
    input1: "val1_in_column_mapping"
    input3: ${data.input3}
```

Since the flow will return each inputs in output, we can get the actual inputs from `outputs.output` field in run details:

![column_mapping_details](../media/column_mapping_details.png)

- Input "input1" has value "val1_in_column_mapping" since it's specified as constance in `column_mapping`.
- Input "input2" has value "default_val2" since it used default value in flow dag.
- Input "input3" has value "val3_in_data" since it's specified as data reference in `column_mapping`.
- Input "input4" has value "val3_in_data" since it has same name column in provided data.
