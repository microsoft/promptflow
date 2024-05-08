# Model Configuration

Tailoring your AI applications to use specific models with desired parameters is now easier than ever with the Promptflow SDK's new Model Configuration feature. Whether you're engaging with chatbots, generating text, or building complex AI workflows, our unified configuration approach allows you to set up and switch between models from OpenAI, AzureOpenAI seamlessly.

## Model Configuration at a Glance

We've designed a set of classes that cater to various scenarios, each with a straightforward setup process. Here's how you can configure models for different services:

### `AzureOpenAIModelConfiguration`

The `AzureOpenAIModelConfiguration` class lets you connect to Azure's AI services with minimal hassle. Just provide your endpoint, deployment, and optional authentication details, and you're good to go.
Reference [here](https://microsoft.github.io/promptflow/reference/python-library-reference/promptflow-core/promptflow.core.html?#promptflow.core.AzureOpenAIModelConfiguration) for it's defintion.

### `OpenAIModelConfiguration`

The `OpenAIModelConfiguration` class is tailored for direct OpenAI integration. Specify your API key, the model you want to use, and any additional parameters.
Reference [here](https://microsoft.github.io/promptflow/reference/python-library-reference/promptflow-core/promptflow.core.html?#promptflow.core.OpenAIModelConfiguration) for it's definition.
