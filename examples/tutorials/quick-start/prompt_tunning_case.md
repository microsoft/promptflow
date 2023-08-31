# Tutorial: Prompt tuning case

## Test the quality of the generated prompt

Do you have confidence in the quality of the generated prompt? Let's have a quick test with a larger dataset in prompt flow!

Click to download the [test dataset]().

Run the following python code to test your prompt in 10 lines input questions:

```python
import promptflow as pf
from promptflow import PFClient

pf_client=PFClient()

# specify the path to the flow folder
my_flow_path = "<my_chatbot>"
# specify the path to the dataset
my_data_path = "<my_data>"

# create a run
base_run = pf.run(
    flow=my_flow_path,
    data=data_path,
    column_mapping={  # map the url field from the data to the url input of the flow
      "question": "${data.question}",
      "chat_history": [],
    }
)

# get the inputs/outputs details of a finished run.
details = pf.get_details(base_run)
details.head(5)
```

Then calculate the accuracy of the answers by running the specific flow for evaluation. Click to download the [evaluation flow]().

```python
# specify the path to the evaluation flow folder
my_evaluation_flow_path = "<my_evaluation_flow>"

# run the flow with existing run
eval_run = pf.run(
    flow = my_eval_flow_path,
    data= my_data_path,
    run = base_run,
    column_mapping={
        "groundtruth": "${data.groundtruth}",
        "answer": "${run.outputs.answer}",
    },  # map the url field from the data to the url input of the flow
)

# visualize the run in a web browser
pf.visualize([base_run, eval_run])
```

Opps! The accuracy is not good enough. Only 35% accuracy! I need to tune the prompt for better performance.

## Facilitate high quality by prompt tuning

To improve the quality of the prompt in Prompt flow, as long as you have a sense of what the prompt should look like, you can quickly start an experiment to test your ideas.

In this case, you can try leverage the Chain of Thought (COT) prompt engineering method to feed the few-shot examples to LLM. But how many few-shot examples should be added? It's important to strike a balance between better performance and controlling the token cost.

Let's conduct a quick experiment using two more prompt variants. One includes 2 examples, while the other includes 6 examples. Then you need to edit the flow yaml file to add these two more variants of the chat node.

Click to download the [my_chatbot_with_variants]() which contains 3 Jinjia files point to the 3 prompt variants and the new flow yaml file.

Then proceed to the python script of base_run and eval_run again, then you can get the visualization of the experiment results, for example:


Excellent! The accuracy of the variant_1 prompt with 2 examples is 80%, while is 90% for the variant_2 prompt with 6 examples. But we can see the token of variant_1 is 1.5x of the variant_2. So, more examples may not always lead to better performance. 2 examples few-shot learning strike a balance for the performance and cost.