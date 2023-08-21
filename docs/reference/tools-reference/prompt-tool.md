# Prompt

## Introduction
The Prompt Tool in PromptFlow offers a collection of textual templates that serve as a starting point for creating prompts. 
These templates, based on the Jinja2 template engine, facilitate the definition of prompts. The tool proves useful 
when prompt tuning is required prior to feeding the prompts into the Language Model (LLM) model in PromptFlow.


## Inputs

| Name               | Type   | Description                                              | Required |
|--------------------|--------|----------------------------------------------------------|----------|
| prompt             | string | The prompte template in Jinja                            | Yes      |
| Inputs             | -      | List of variables of prompt template and its assignments | -        |


## Outputs

The prompt text parsed from the prompt + Inputs 


## How to write Prompt?

1. Prepare jinja template. Learn more about [Jinja](https://jinja.palletsprojects.com/en/3.1.x/)

_In below example, the prompt incorporates Jinja templating syntax to dynamically generate the welcome message and personalize it based on the user's name. It also presents a menu of options for the user to choose from. Depending on whether the user_name variable is provided, it either addresses the user by name or uses a generic greeting._

```jinja
Welcome to {{ website_name }}!
{% if user_name %}
    Hello, {{ user_name }}!
{% else %}
    Hello there!
{% endif %}
Please select an option from the menu below:
1. View your account
2. Update personal information
3. Browse available products
4. Contact customer support
```

2. Assign value for the variables.

_In above example, two variables would be automatically detected and listed in '**Inputs**' section. Please assign values._

### Sample 1
Inputs

| Variable      | Type   | Sample Value | 
|---------------|--------|--------------|
| website_name  | string | "Microsoft"  |
| user_name     | string | "Jane"       |

Outputs

```
Welcome to Microsoft! Hello, Jane! Please select an option from the menu below: 1. View your account 2. Update personal information 3. Browse available products 4. Contact customer support
```

### Sample 2

Inputs

| Variable     | Type   | Sample Value   | 
|--------------|--------|----------------|
| website_name | string | "Bing"         |
| user_name    | string | "              |

Outputs

```
Welcome to Bing! Hello there! Please select an option from the menu below: 1. View your account 2. Update personal information 3. Browse available products 4. Contact customer support
```