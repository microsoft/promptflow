# Tutorial: Prompt tuning and evaluation

## Evaluate the quality of your prompt
Let's have a quick test with a larger dataset in prompt flow!

> Click to [download the test dataset](./tune-your-prompt-samples/test_data.jsonl), then put it under the pf-test folder.

Run the following command to test your prompt in 20 lines input questions:
> [!Note]
> The run name is unique. If 'base_run' has already existed, please give a new name by '--name' 

```sh
pf run create --flow my_chatbot --data test_data.jsonl --column-mapping question='${data.question}' chat_history=[] --name base_run --stream
```

You can see the run details by:
```sh
pf run show-details -n base_run
```

Then, run a specific flow for **evaluation** to calculate the accuracy of the answers based on previous run:

> Click to [download the evaluation flow](./src/eval_accuracy.zip), then put it under the pf-test folder.

```sh
pf run create --flow eval_accuracy --data test_data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.answer}' --run base_run --name eval_run --stream
```

Then get metrics of the eval_run:
```sh
pf run show-metrics -n eval_run
```

You can visualize and compare the output of base_run and eval_run in a web browser:

```sh
pf run visualize -n 'base_run,eval_run'
```

Opps! The accuracy is not good enough. It's time to tune your prompt for higher accuracy!

## Tune your prompt

To improve the quality of your prompt, you can quickly start an experiment to test your ideas.

> Click to [download the prompt tuning case](./src/my_chat_variant.zip), unzip it, then put the `my_chat_variant` folder under the pf-test folder.

In the sample flow, you can see 3 Jinjia files: `chat.jinja2`, `chat_variant_1.jinja2` and `chat_variant_2.jinja2`. They are 3 prompt variants.

We leverage the Chain of Thought (CoT) prompt engineering method to modify the prompt. Try to inspire LLM's reasoning ability by feeding few-shot CoT examples.

Variant_0: the origin prompt
```
system:
You are an assistant specialized in math computation. Your task is to solve math problems. Please provide the result number only in your response.
{% for item in chat_history %}
user:
{{item.inputs.question}}
assistant:
{{item.outputs.answer}}
{% endfor %}
user:
{{question}}
```

Variant_1: 2 CoT examples
```
system:
You are a helpful assistant. Help me with some mathematics problems of counting and probability. Think step by step and output as json format.
Here are some examples:
user:
A jar contains two red marbles, three green marbles, ten white marbles and no other marbles. Two marbles are randomly drawn from this jar without replacement. What is the probability that these two marbles drawn will both be red? Express your answer as a common fraction.
assistant:
{Chain of thought: "The total number of marbles is $2+3+10=15$.  The probability that the first marble drawn will be red is $2/15$.  Then, there will be one red left, out of 14.  Therefore, the probability of drawing out two red marbles will be: $$\\frac{2}{15}\\cdot\\frac{1}{14}=\\boxed{\\frac{1}{105}}$$.", "answer": "1/105"}
user:
Find the greatest common divisor of $7!$ and $(5!)^2.$
assistant:
{"Chain of thought": "$$ \\begin{array}{rcrcr} 7! &=& 7 \\cdot 6 \\cdot 5 \\cdot 4 \\cdot 3 \\cdot 2 \\cdot 1 &=& 2^4 \\cdot 3^2 \\cdot 5^1 \\cdot 7^1 \\\\ (5!)^2 &=& (5 \\cdot 4 \\cdot 3 \\cdot 2 \\cdot 1)^2 &=& 2^6 \\cdot 3^2 \\cdot 5^2 \\\\ \\text{gcd}(7!, (5!)^2) &=& 2^4 \\cdot 3^2 \\cdot 5^1 &=& \\boxed{720} \\end{array} $$.", "answer": "720"}
{% for item in chat_history %}
user:
{{item.inputs.question}}
assistant:
{{item.outputs.answer}}
{% endfor %}
user:
{{question}}
```

Variant_2 : 6 CoT examples.
```
system:
You are a helpful assistant. Help me with some mathematics problems of counting and probability. Think step by step and output as json format.

Here are some examples:

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
{% for item in chat_history %}
user:
{{item.inputs.question}}
assistant:
{{item.outputs.answer}}
{% endfor %}
user:
{{question}}
```

## Test and evaluate your prompt variants

First, you need to modify your flow to add two more prompt variants into the chat node, in addition to the existed default one. In the flow.dag.yaml file, you can see 3 variants definition of the `chat` node, which point to these 3 Jinjia files.

Run the CLI command below to start the experiment: test all variants, evaluate them, get the visualized comparison results of the experiment.

Test and evaluate variant_0:
```sh
pf run create --flow my_chat_variant --data test_data.jsonl --variant '${chat.variant_0}' --stream --name my_variant_0_run
```
```sh
pf run create --flow eval_accuracy --data test_data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.answer}' --run my_variant_0_run --name eval_variant_0_run --stream
```

Test and evaluate variant_1:
```sh
pf run create --flow my_chat_variant --data test_data.jsonl --variant '${chat.variant_1}' --stream --name my_variant_1_run
```
```sh
pf run create --flow eval_accuracy --data test_data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.answer}' --run my_variant_1_run --name eval_variant_1_run --stream
```

Test and evaluate variant_2:
```sh
pf run create --flow my_chat_variant --data test_data.jsonl --variant '${chat.variant_2}' --stream --name my_variant_2_run
```
```sh
pf run create --flow eval_accuracy --data test_data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.answer}' --run my_variant_2_run --name eval_variant_2_run --stream
```

Visualize the results:
```sh
pf run visualize -n 'my_variant_0_run,eval_variant_0_run,my_variant_1_run,eval_variant_1_run,my_variant_2_run,eval_variant_2_run'
```

Excellent! Now you can click the html link, to get the experiment results of your prompts, balance their performances and token costs, and choose the prompt that is most suitable for your needs.