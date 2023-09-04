# Tutorial: How prompt flow helps on quality improvement
This is a tutorial about how to improve the flow quality by tuning prompts and evaluation.

## Prerequisite

Before moving ahead, ensure you've completed the [Quick Start](../../../README.md#get-started-with-prompt-flow-⚡) guidance.

Click to [download the samples](./pf-test.zip), unzip it, and go into the `pf-test` folder, where contains the sample flow and test data we'll use in this tutorial:

```sh
cd pf-test
```
> ℹ️ For testing quickly, this tutorial uses CLI command.

Next, let's get started with customizing the flow for a specific task.

## Customize the Flow for a Specific Task

In the `pf-test` folder, you can see a `my_chatbot_orgin` folder, which represents a chat template flow as same as the one you created in the [Quick Start](../../../README.md#get-started-with-prompt-flow-⚡) guidance. We'll use this flow as a starting point to build a math problem solver.
 
To enable your chatbot flow to solve math problems, you need to instruct the LLM about the task and target in the prompt. Open `chat.jinja2`, you can see that tasks and targets are mentioned in the system prompt as:

```
system:
You are an assistant to calculate the answer to the provided math problems. 
Please return the final numerical answer only, without any accompanying reasoning or explanation.
```

Run the following command to test the flow with a simple math problem:

```sh
pf flow test --flow ./my_chatbot_origin --inputs question="1+1=?"
```
This will yield the following output:
```json
{
    "answer": "2"
}
```

Sometime, the question may be challenging. Now, let's test it with a complex math problem, such as:

```sh
pf flow test --flow ./my_chatbot_origin --inputs question="We are allowed to remove exactly one integer from the list $$-1,0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10,11,$$and then we choose two distinct integers at random from the remaining list. What number should we remove if we wish to maximize the probability that the sum of the two chosen numbers is 10?"
```

The output is:
```json
{
    "answer": "-1"
}
```
However, the correct answer is 5. The output answer is incorrect! It indicates that we need to further evaluate the performance. Therefore, in the next step, we will test the flow with more math problems to better evaluate the quality.

## Evaluate the quality of your prompt

With prompt flow, you can quickly trigger a batch-run to test your prompt with a larger dataset, and evaluate the quality of the answers.

There is a `test_data.jsonl` file in the `pf-test` folder, which is a dataset containing 20 test data entries (a subset of [the Math Dataset](https://github.com/hendrycks/math/)). It includes the input question, the ground truth for numerical answer, and the reasoning (raw_answer). Here's one example:

```json
{
    "question": "Determine the number of ways to arrange the letters of the word PROOF.", 
    "answer": "60", 
    "raw_answer": "There are two O's and five total letters, so the answer is $\\dfrac{5!}{2!} = \\boxed{60}$." 
}

```

Run the following command to test your prompt with this dataset:

>The default model is `gpt-turbo-3.5`, let's try `gpt-4` to see if it's smarter to get better results:

```sh
pf run create --flow ./my_chatbot --data test_data.jsonl --column-mapping question='${data.question}' chat_history=[] --name base_run --connections chat.connection=open_ai_connection chat.model=gpt-4 --stream
```

> ⚠ For Windows CMD users, please specify the absolute path of the flow and data file, and use double quotes in `--column-mapping`. The command should be like this:
> ```sh 
> pf run create --flow C:\Users\test\pf-test\my_chatbot_origin --data C:\Users\test\pf-test\test_data.jsonl --column-mapping question="${data.question}" chat_history=[] --name base_run --connections chat.connection=open_ai_connection chat.model=gpt-4 --stream
> ```

> ⚠ The run name must be unique. Please specify a new name in `--name`. <br> 
> If you see "Run 'base_run' already exists.", you can specify another name. But please remember the name you specified, because you'll need it in the next step.


When it completes, you can run the following command to see the details of results:
> Specify the run name of your completed run in `--name` argument:

```sh
pf run show-details --name base_run
```

This can show the line by line input and output of the run:
```
+----+---------------+-----------------+---------------+---------------+
|    | inputs.chat   | inputs.questi   |   inputs.line | outputs.ans   |
|    | _history      | on              |       _number | wer           |
+====+===============+=================+===============+===============+
|  0 | []            | Compute $\dbi   |             0 | 4368          |
|    |               | nom{16}{5}$.    |               |               |
+----+---------------+-----------------+---------------+---------------+
|  1 | []            | Determine the   |             1 | 60            |
|    |               | number of       |               |               |
|    |               | ways to         |               |               |
|    |               | arrange the     |               |               |
|    |               | letters of      |               |               |
|    |               | the word        |               |               |
|    |               | PROOF.          |               |               |
+----+---------------+-----------------+---------------+---------------+
| .. | ...           | ...             |...            | ...           |
```

Next, create an **evaluation run** to calculate the accuracy of the answers based on the previous run.

In the `pf-test` folder, you can see a `eval_accuracy` folder, which represents an evaluation flow. We'll use this flow to evaluate the accuracy of the answers.

```sh
pf run create --flow ./eval_accuracy --data test_data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.answer}' --run base_run --name eval_run --stream
```

Then get metrics of the `eval_run` (specify another customized or random run name in `--name` argument):
```sh
pf run show-metrics --name eval_run
```

You can visualize and compare the output line by line of `base_run` and `eval_run` in a web browser:

```sh
pf run visualize --name 'base_run,eval_run'
```
> ⚠ For Windows CMD users, please use double quotes instead of single quotes in the `--name` argument. The command should be like this:
> ```sh
> pf run visualize --name "base_run,eval_run"
> ```

Because of the randomness of the LLM, the accuracy may vary. For example, in my run, the metrics are as follows:

```json
{
    "accuracy": 0.35,
    "error_rate": 0.65
}
```

Opps! The accuracy isn't satisfactory. It's time to fine-tune your prompt for higher quality!

## Fine-tuning your prompt and evaluate the improvement

In the `pf-test` folder, you can see a `my_chatbot_variant` folder, which represents a flow with two additional prompt variants compared to the original `my_chatbot_origin`. 

In this sample flow, you'll find three Jinja files: 
* `chat.jinja2` is the original prompt as same as the one in `my_chatbot_origin`.
* `chat_variant_1.jinja2` and `chat_variant_2.jinja2` are the 2 additional prompt variants.

We leverage the Chain of Thought (CoT) prompt engineering method to adjust the prompt. The goal is to activate the Language Model's reasoning capability of the questions, by providing a few CoT examples.

<details>
<summary>Variant_1: 2 CoT examples</summary>

```sh
system:
You are an assistant to calculate the answer to the provided math problems.
Please think step by step.
Return the final numerical answer only and any accompanying reasoning or explanation seperately as json format. <br>
user:
A jar contains two red marbles, three green marbles, ten white marbles and no other marbles. Two marbles are randomly drawn from this jar without replacement. What is the probability that these two marbles drawn will both be red? Express your answer as a common fraction.
assistant:
{Chain of thought: "The total number of marbles is $2+3+10=15$.  The probability that the first marble drawn will be red is $2/15$.  Then, there will be one red left, out of 14.  Therefore, the probability of drawing out two red marbles will be: $$\\frac{2}{15}\\cdot\\frac{1}{14}=\\boxed{\\frac{1}{105}}$$.", "answer": "1/105"}
user:
Find the greatest common divisor of $7!$ and $(5!)^2.$
assistant:
{"Chain of thought": "$$ \\begin{array}{rcrcr} 7! &=& 7 \\cdot 6 \\cdot 5 \\cdot 4 \\cdot 3 \\cdot 2 \\cdot 1 &=& 2^4 \\cdot 3^2 \\cdot 5^1 \\cdot 7^1 \\\\ (5!)^2 &=& (5 \\cdot 4 \\cdot 3 \\cdot 2 \\cdot 1)^2 &=& 2^6 \\cdot 3^2 \\cdot 5^2 \\\\ \\text{gcd}(7!, (5!)^2) &=& 2^4 \\cdot 3^2 \\cdot 5^1 &=& \\boxed{720} \\end{array} $$.", "answer": "720"}

......
```
</details>

<details>
<summary>Variant_2 : 6 CoT examples.</summary>

```sh
system:
You are an assistant to calculate the answer to the provided math problems.
Please think step by step.
Return the final numerical answer only and any accompanying reasoning or explanation seperately as json format.

user:
A jar contains two red marbles, three green marbles, ten white marbles and no other marbles. Two marbles are randomly drawn from this jar without replacement. What is the probability that these two marbles drawn will both be red? Express your answer as a common fraction.
assistant:
{Chain of thought: "The total number of marbles is $2+3+10=15$.  The probability that the first marble drawn will be red is $2/15$.  Then, there will be one red left, out of 14.  Therefore, the probability of drawing out two red marbles will be: $$\\frac{2}{15}\\cdot\\frac{1}{14}=\\boxed{\\frac{1}{105}}$$.", "answer": "1/105"}
user:
Find the greatest common divisor of $7!$ and $(5!)^2.$
assistant:
{"Chain of thought": "$$ \\begin{array}{rcrcr} 7! &=& 7 \\cdot 6 \\cdot 5 \\cdot 4 \\cdot 3 \\cdot 2 \\cdot 1 &=& 2^4 \\cdot 3^2 \\cdot 5^1 \\cdot 7^1 \\\\ (5!)^2 &=& (5 \\cdot 4 \\cdot 3 \\cdot 2 \\cdot 1)^2 &=& 2^6 \\cdot 3^2 \\cdot 5^2 \\\\ \\text{gcd}(7!, (5!)^2) &=& 2^4 \\cdot 3^2 \\cdot 5^1 &=& \\boxed{720} \\end{array} $$.", "answer": "720"}
user:
A club has 10 members, 5 boys and 5 girls.  Two of the members are chosen at random.  What is the probability that they are both girls?
assistant:
{"Chain of thought": "There are $\\binom{10}{2} = 45$ ways to choose two members of the group, and there are $\\binom{5}{2} = 10$ ways to choose two girls.  Therefore, the probability that two members chosen at random are girls is $\\dfrac{10}{45} = \\boxed{\\dfrac{2}{9}}$.", "answer": "2/9"}
user:
Allison, Brian and Noah each have a 6-sided cube. All of the faces on Allison's cube have a 5. The faces on Brian's cube are numbered 1, 2, 3, 4, 5 and 6. Three of the faces on Noah's cube have a 2 and three of the faces have a 6. All three cubes are rolled. What is the probability that Allison's roll is greater than each of Brian's and Noah's? Express your answer as a common fraction.
assistant:
{"Chain of thought": "Since Allison will always roll a 5, we must calculate the probability that both Brian and Noah roll a 4 or lower. The probability of Brian rolling a 4 or lower is $\\frac{4}{6} = \\frac{2}{3}$ since Brian has a standard die. Noah, however, has a $\\frac{3}{6} = \\frac{1}{2}$ probability of rolling a 4 or lower, since the only way he can do so is by rolling one of his 3 sides that have a 2. So, the probability of both of these independent events occurring is $\\frac{2}{3} \\cdot \\frac{1}{2} = \\boxed{\\frac{1}{3}}$.", "answer": "1/3"}
user:
Compute $\\dbinom{50}{2}$.
assistant:
{"Chain of thought": "$\\dbinom{50}{2} = \\dfrac{50!}{2!48!}=\\dfrac{50\\times 49}{2\\times 1}=\\boxed{1225}.$", "answer": "1225"}
user:
The set $S = \\{1, 2, 3, \\ldots , 49, 50\\}$ contains the first $50$ positive integers.  After the multiples of 2 and the multiples of 3 are removed, how many integers remain in the set $S$?
assistant:
{"Chain of thought": "The set $S$ contains $25$ multiples of 2 (that is, even numbers).  When these are removed, the set $S$ is left with only the odd integers from 1 to 49. At this point, there are $50-25=25$ integers in $S$. We still need to remove the multiples of 3 from $S$.\n\nSince $S$ only contains odd integers after the multiples of 2 are removed,  we must remove the odd multiples of 3 between 1 and 49.  These are 3, 9, 15, 21, 27, 33, 39, 45, of which there are 8.  Therefore, the number of integers remaining in the set $S$ is $25 - 8 = \\boxed{17}$.", "answer": "17"}

......
```
</details>

These two jinjia files are specified in the `flow.dag.yaml` file, which defines the flow structure. You can see that the `chat` node has 3 variants, which point to these 3 Jinjia files.

## Test and evaluate your prompt variants

First, you need to modify your flow to add two more prompt variants into the chat node, in addition to the existed default one. In the flow.dag.yaml file, you can see 3 variants definition of the `chat` node, which point to these 3 Jinjia files.

Run the CLI command below to start the experiment: test all variants, evaluate them, get the visualized comparison results of the experiment.

> ℹ️ By default, the connection is set to `open_ai_connection` and and the model is set to `gpt-4` for each variant, as specified in the `flow.dag.yaml` file. However, you have the flexibility to specify a different connection and model by adding `--connections chat.connection=<your_connection_name> chat.model=<model_name>` in the test run command.

Test and evaluate variant_0:
```sh
# Test-run
pf run create --flow ./my_chatbot_variant --data test_data.jsonl --column-mapping question='${data.question}' chat_history=[] --variant '${chat.variant_0}' --name my_variant_0_run --stream 
```
```sh
# Evaluate-run
pf run create --flow ./eval_accuracy --data test_data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.answer}' --run my_variant_0_run --name eval_variant_0_run --stream
```

Test and evaluate variant_1:
```sh
# Test-run
pf run create --flow ./my_chatbot_variant --data test_data.jsonl --column-mapping question='${data.question}' chat_history=[] --variant '${chat.variant_1}' --stream --name my_variant_1_run
```
```sh
# Evaluate-run
pf run create --flow ./eval_accuracy --data test_data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.answer}' --run my_variant_1_run --name eval_variant_1_run --stream
```

Test and evaluate variant_2:
```sh
# Test-run
pf run create --flow ./my_chatbot_variant --data test_data.jsonl --column-mapping question='${data.question}' chat_history=[] --variant '${chat.variant_2}' --stream --name my_variant_2_run
```
```sh
# Evaluate-run
pf run create --flow ./eval_accuracy --data test_data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.answer}' --run my_variant_2_run --name eval_variant_2_run --stream
```

Get metrics of the all evaluations:
```sh
pf run show-metrics --name eval_variant_0_run
pf run show-metrics --name eval_variant_1_run
pf run show-metrics --name eval_variant_2_run
```

You may get the familiar output like this:
```
# eval_variant_0_run
{
    "accuracy": 0.3, 
    "error_rate": 0.7
}
# eval_variant_1_run
{
    "accuracy": 0.9,
    "error_rate": 0.1
}
# eval_variant_2_run
{
    "accuracy": 0.9,
    "error_rate": 0.1
}
```

Visualize the results:
```sh
pf run visualize --name 'my_variant_0_run,eval_variant_0_run,my_variant_1_run,eval_variant_1_run,my_variant_2_run,eval_variant_2_run'
```

Click the HTML link, to get the experiment results. Click on column in the **Output** table will allow you to view the snapshot of each line.

The snapshot of chat flow:
![Visualization chat flow](media/visualization_chat_flow.png)

The snapshot of evaluation flow:
![Visualization eval flow](media/visualization_eval_flow.png)

Excellent! Now you can compare their performances and token costs, and choose the prompt that best suits your needs. We can see that variant_1 and variant_2 have the same accuracy, but variant_1 has a lower token cost (only 2 few shots rather than the 6 in in variant_2). So variant_1 is the best choice for the quality and cost balance.

## Conclusion

Great! Now you can compare their performances and token costs to choose the prompt that best suits your needs. Upon comparison, we can observe that variant_1 and variant_2 have the similar accuracy. However, variant_1 stands out as the better choice due to its lower token cost (2 few-shots vs. 6 few-shots).

<img src="media/realcase.png" alt="comparison resutl" width=65%/>

It is evident that adding more CoT examples in the prompt does not necessarily improve the accuracy further. Instead, we should identify the optimal point where the number of shots maximizes accuracy while minimizing cost.

Just in a few steps, we identified that variant_1 strikes the ideal balance between quality and cost! This is where the value of prompt tuning and evaluation using prompt flow becomes apparent. With prompt flow, you can easily test and evaluate different prompt variants, enabling you to facilitate high quality LLM-native apps to production.