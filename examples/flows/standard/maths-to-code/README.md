# Math to Code
Math to Code is a project that utilizes the power of the chatGPT model to generate code that models math questions and then executes the generated code to obtain the final numerical answer.

> [!NOTE]
>
> Building a system that generates executable code from user input with LLM is [a complex problem with potential security risks](
https://developer.nvidia.com/blog/securing-llm-systems-against-prompt-injection/
), this example is more of a demonstration rather than something you can directly use in production. To build such system correctly, you should address key security considerations like input validation, additional sanitization of the code generated or better run the generated code in a sandbox environment.

Tools used in this flow：

- `python` tool
- built-in `llm` tool

Connections used in this flow:

- `open_ai` connection

## Prerequisites
Install promptflow sdk and other dependencies:

```cmd
pip install -r requirements.txt
```

## Setup connection
Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

Note in this example, we are using [chat api](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/chatgpt?pivots=programming-language-chat-completions), please use `gpt-35-turbo` or `gpt-4` model deployment.

Create connection if you haven't done that. Ensure you have put your azure open ai endpoint key in [azure_openai.yml](azure_openai.yml) file. 
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

Ensure you have created `open_ai_connection` connection.
```bash
pf connection show -n open_ai_connection
```


## Run flow in local

### Run locally with single line input

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
# test with specific input
pf flow test --flow . --inputs math_question='If a rectangle has a length of 10 and width of 5, what is the area?'
```

### Run with multiple lines data

- create run
```bash
# create a random run name
run_name="math_to_code_"$(openssl rand -hex 12)
pf run create --flow . --data ./math_data.jsonl --column-mapping math_question='${data.question}' --name $run_name --stream
```

### Get the accuracy using evaluation flow
Use [eval-accuracy-maths-to-code](../../evaluation/eval-accuracy-maths-to-code/) to evaluate accuracy and error rate metrics against the math-to-code flow.

- accuracy: if the generated code can be correctly executed and got final number answer, it will be compare with the groundtruth in the test data. For single instance, it's True if the final number equals to the groundtruth, False otherwise. Accuracy is to measure the correct percentage against test data.
- error_rate: some case the flow cannot get number answer, for example, the generated code cannot be executed due to code parsing error of dependent package not available in conda env. Error rate is to measure the percentage of this case in test data. 

```bash
# create a random eval run name
eval_run_name="math_to_code_eval_run_"$(openssl rand -hex 12)

# invoke accuracy and error rate evaluation against math-to-code batch run
pf run create --flow ../../evaluation/eval-accuracy-maths-to-code/ --data ./math_data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.answer}' --run $run_name --name $eval_run_name --stream

# view the run details
pf run show-details -n $eval_run_name
pf run show-metrics -n $eval_run_name
```
