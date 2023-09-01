# Tutorial: Prompt tuning case

## Test the quality of the generated prompt

Do you have confidence in the quality of the generated prompt? Let's have a quick test with a larger dataset in prompt flow!

Run the following command to test your prompt in 10 lines input questions:

> Click to [download the test dataset](). Specify the path to the flow and test dataset in the command.

```sh

```sh
pf run create --flow <my_chatbot> --data <test_data.jsonl> --column-mapping question="${data.question}" chat_history=[] --name base_run --stream
```

Then get details of the base_run:
```sh
pf run show-details -n base_run
```

Then calculate the accuracy of the answers by running the specific flow for **evaluation**.  Run the following command to evaluate the output of previous run:

> Click to [download the evaluation flow](). Specify the path to the evaluation flow and test dataset in the command.

```sh
pf run create --flow <eval-accuracy> --data <test_data.jsonl> --column-mapping groundtruth="${data.groundtruth}" answer="${run.outputs.answer}" --run base_run --name eval_run --stream
```

Then get metrics of the eval_run:
```sh
pf run show-metrics -n eval_run
```

You can visualize and compare the output of base_run and eval_run in a web browser:

```sh
pf run visualize -n "base_run,eval_run"
```


Opps! The accuracy is not good enough. Only 35% accuracy! I need to tune the prompt for better performance.

## Facilitate high quality by prompt tuning

To improve the quality of the prompt in Prompt flow, as long as you have a sense of what the prompt should look like, you can quickly start an experiment to test your ideas.

In this case, you can try leverage the Chain of Thought (COT) prompt engineering method to feed the few-shot examples to LLM. But how many few-shot examples should be added? It's important to strike a balance between better performance and controlling the token cost.

Let's conduct a quick experiment using two more prompt variants. One includes 2 examples, while the other includes 6 examples. Then you need to edit the flow yaml file to add these two more variants of the chat node.

Click to download the [my_chatbot_with_variants]() which contains 3 Jinjia files point to the 3 prompt variants and the new flow yaml file.

Then proceed to the python script of base_run and eval_run again, then you can get the visualization of the experiment results, for example:


Excellent! The accuracy of the variant_1 prompt with 2 examples is 80%, while is 90% for the variant_2 prompt with 6 examples. But we can see the token of variant_1 is 1.5x of the variant_2. So, more examples may not always lead to better performance. 2 examples few-shot learning strike a balance for the performance and cost.