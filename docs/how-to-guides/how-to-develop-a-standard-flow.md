# Develop a standard flow

You can develop your flow from scratch, by creating a standard flow. In this article, you will learn how to develop the standard flow in the authoring page.

You can quickly start developing your standard flow by following this video tutorial:

[![develop_a_standard_flow](https://img.youtube.com/vi/Y1CPlvQZiBg/0.jpg)](https://www.youtube.com/watch?v=Y1CPlvQZiBg)


## Create a standard flow

In the prompt flow​​​​​​​ homepage, you can create a standard flow from scratch. Select **Create** button.

![flow-create-standard](../media/develop-a-standard-flow/flow-create-standard.png)

## Authoring page - flatten view and graph view

After the creation you will enter the authoring page for flow developing.

At the left, it is the flatten view, the main working area where you can author the flow, for example add tools in your flow, edit the prompt, set the flow input data, run your flow, view the output, etc.

![flow-authoring-flatten](../media/develop-a-standard-flow/flow-flatten-view.png)

At the right, it is the graph view for visualization only. It shows the flow structure you are developing, including the tools and their links. You can zoom in, zoom out, auto layout, etc.

Note: You cannot edit the graph view. To edit one tool node, you can double-click the node to locate to the corresponding tool card in the flatten view the do the inline edit.

![flow-authoring-graph](../media/develop-a-standard-flow/flow-graph-view.png)

## Select runtime

Before you start authoring to develop your flow, you should first select a runtime.  Click the Runtime at the top and select a available one that suits your flow run.

**Note:** You cannot save your inline edit of tool without a runtime!

![flow-runtime](../media/develop-a-standard-flow/flow-runtime-setting.png)

## Flow input data

The flow input data is the data that you want to process in your flow. When unfolding **Inputs** section in the authoring page, you can set and view your flow inputs, including input schema (name and type), and the input value.

For Web Classification sample as shown the screenshot below, the flow input is a URL of string type.

![flow-input](../media/develop-a-standard-flow/flow-input.png)

We also support the input type of int, bool, double, list and object.

![flow-input-type](../media/develop-a-standard-flow/flow-input-datatype.png)

You should first set the input schema (name: url; type: string), then set a value manually or by:

1. Inputting data manually in the value field.
2. Selecting a row of existing dataset in **fill value from data**.

![flow-value-from-data](../media/develop-a-standard-flow/flow-value-from-data.gif)

The dataset selection supports search and auto-suggestion.

![flow-input-dataerror](../media/develop-a-standard-flow/flow-input-dataerror.png)

After selecting a row, the url is backfilled to the value field.

If the existing datasets do not meet your needs, upload new data from files. We support **.csv** and **.txt** for now.

![flow-input-content](../media/develop-a-standard-flow/flow-input-content.png)

## Develop tool in your flow

In one flow, you can consume different kinds of tools. We now support LLM, Python, Serp API, Content Safety and Vector Search.

### Add tool as your need

By clicking the tool card on the very top, you will add a new tool node to flow.

![flow-add-tool](../media/develop-a-standard-flow/flow-tool.png)

### Edit tool

When a new tool node is added to flow, it will be appended at the bottom of flatten view with a random name by default. The new added tool appears at the top of the graph view as well.

![flow-new-tool](../media/develop-a-standard-flow/flow-new-tool.png)

At the top of each tool node card, there is a toolbar for adjusting the tool node. You can **move it up or down**, you can **delete** or **rename** it too.

![flow-tool-toolbar](../media/develop-a-standard-flow/flow-tool-edit.png)

### Select connection

In the the LLM tool, click Connection to select one to set the LLM key or credential.

![flow-llm-connection](../media/develop-a-standard-flow/flow-llm-conn.png)

### Prompt and python code inline edit

In the LLM tool and python tool, it's available to inline edit the prompt or code. Go to the card in the flatten view, click the prompt section or code section, then you can make your change there.

![flow-inline-edit-prompt](../media/develop-a-standard-flow/flow-inline-edit-prompt.gif)

![flow-inline-edit-code](../media/develop-a-standard-flow/flow-inline-edit.gif)

### Validate and run

To test and debug a single node, click the **Run** icon on node in flatten view. The run status appears at the top of the screen. If the run fails, an error banner displays. To view the output of the node, go to the node and open the output section, you can see the output value, trace and logs of the single step run.

The single node status is shown in the graph view as well.

![flow-run](../media/develop-a-standard-flow/flow-step-run.png)

You can also change the flow input url to test the node behavior for different URLs.

## Chain your flow - link nodes together

Before linking nodes together, you need to define and expose an interface.

### Define LLM node interface

LLM node has only one output, the completion given by LLM provider.

As for inputs, we offer a templating strategy that can help you create parametric prompts that accept different input values. Instead of fixed text, simply enclose your input name in `{{}}`, so it can be replaced on the fly. We use **Jinja** as our templating language.

Click **Edit** next to prompt box to define inputs using `{{input_name}}`.

![flow-input-interface](../media/develop-a-standard-flow/flow-input-interface.png)

### Define Python node interface

Python node might have multiple inputs and outputs. Define inputs and outputs as shown below. If you have multiple outputs, remember to make it a dictionary so that the downstream node can call each key separately.

![flow-input-python](../media/develop-a-standard-flow/flow-input-python.png)

### Link nodes together

After the interface is defined, you can use:

* ${inputs.key} to link with flow input.
* ${upstream_node_name.output} to link with single-output upstream node.
* ${upstream_node_name.output.key} to link with multi-output upstream node.

Below are common scenarios for linking nodes together.

### SCENARIO 1 - Link LLM node with flow input

1. Add a new LLM node, rename it with a meaningful name, specify the connection and api type.
2. Click **Edit** next to the prompt box, add an input by `{{url}}`, then you will see an input called url is created in inputs section.
3. In the value drop down, select ${inputs.url}, then you will see in the graph view that the newly created LLM node is linked to the flow input. When running the flow, the url input of the node will be replaced by flow input on the fly.

![link_llm_node_input](../media/develop-a-standard-flow/link_llm_node_input1.gif)

### SCENARIO 2 - Link LLM node with single-output upstream node

1. Click **Edit** next to the prompt box, add another input by `{{summary}}`, then you will see an input called summary is created in inputs section.
2. In the value drop down, select ${summarize_text_content.output}, then you will see in the graph view that the newly created LLM node is linked to the upstream summarize_text_content node. When running the flow, the summary input of the node will be replaced by summarize_text_content node output on the fly.

![link_llm_node_summary](../media/develop-a-standard-flow/link_llm_node_input2.gif)

We support search and auto-suggestion here in the drop down. You can search by node name if you have many nodes in the flow.

![flow-auto-suggestion](../media/develop-a-standard-flow/flow-auto-suggestion.png)

You can also navigate to the node you want to link with, copy the node name, navigate back to the newly created LLM node, paste in the input value field.

![link_llm_node_summary2](../media/develop-a-standard-flow/link_llm_node_summary2.gif)

### SCENARIO 3 - Link LLM node with multi-output upstream node

Suppose we want to link the newly created LLM node with covert_to_dict Python node whose output is a dictionary with 2 keys: category and evidence.

1. Click Edit next to the prompt box, add another input by `{{category}}`, then you will see an input called category is created in inputs section.
2. In the value drop down, select ${convert_to_dict.output}, then manually append category, then you will see in the graph view that the newly created LLM node is linked to the upstream convert_to_dict node. When running the flow, the category input of the node will be replaced by category value from convert_to_dict node output dictionary on the fly.

![link_llm_node_summary3](../media/develop-a-standard-flow/link_llm_node_summary3.png)

### SCENARIO 4 - Link Python node with upstream node/flow input

1. First you need to edit the code, add an input in python function.
1. The linkage is the same as LLM node, using \${flow.input_name\} to link with flow input or \${upstream_node_name.output1\} to link with upstream node.

![new_python_node_input](../media/develop-a-standard-flow/new_python_node_input.gif)

## Flow run

To test and debug the whole flow, click the Run button at the right top.

![flow-run](../media/develop-a-standard-flow/flow-run-all.png)

Then you can check the run status and output of each node. The node statuses are shown in the graph view as well. Similarly, you can change the flow input url to test how the flow behaves for different URLs.

## Set and check flow output

When the flow is complicated, instead of checking outputs on each node, you can set flow output and check outputs of multiple nodes in one place. Moreover, flow output helps:

* check bulk test results in one single table.
* define evaluation interface mapping.
* set deployment response schema.

First define flow output schema, then select in drop down the node whose output you want to set as flow output. Since convert_to_dict has a dictionary output with 2 keys: category and evidence, you need to manually append category and evidence to each. Then run flow, after a while, you can check flow output in a table.

![flow-output](../media/develop-a-standard-flow/flow-output.png)
![flow-output-check](../media/develop-a-standard-flow/flow-output-check.png)
![flow-output-check](../media/develop-a-standard-flow/flow-output-check2.png)
