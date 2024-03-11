We already have a clear story from authoring to deployment with DAG flow, given we will be more foucs on the eager(flex) flow, we need to define a story for that also.
## Goal
- provide smooth experience from authoring to deployment
- simplify the authoring experience as much as possible

## User experience question
- can we totally get rid of flow.yaml for eager flow?
  - signature
  - requirements.txt
  - entry
  - environment_variables
  - additional_includes(??)
- is pf.save a must stage?


## Daniel's proposal - loader function
[loader_function](https://github.com/enterprises/microsoftopensource/saml/initiate?return_to=https%3A%2F%2Fgithub.com%2FAzure%2Fazureml_run_specification%2Fblob%2Fusers%2Fanksing%2Fevaluator_flow_asset%2Fspecs%2Fsimplified-sdk%2Fevaluator%2Fsave_load_promptflow.md)   
Ignore the details of the pf.save and pf.load_flow (we won't cover the details here), loader function is a way to allow customer customizing their eager flow and it does can mitigate the issue to some extend.   
There are still some issues for loader function:
- customer needs to define both the encapsulated class and the loader function
- the flow can only be deployed after pf.save

## Other choices

### Function + BaseFlow

#### Function mode (configure via environment variables)
If all of customer's settings are via environment variables, they can define the flow with a function, this is what our eager flow example shows now, we still can support that natively and customer don't need to change anything.

#### Class mode (configura via initialization settings)
The environment variables way does work but it might need customer to configure lots of environment variables to replace the connection usage. For those customer who want to directly depend on the local/workspace connection and have some customized initialization logic, they can inherit from the BaseFlow we provided and define their own flow logic.

```python
# BaseFlow interface
class BaseFlow:
    def init(self, flow_settings: dict, *kwargs);
    def execute(self, *kwargs);
    #def signature(self);
```
- `init` function can be used for customized initialization logic; 
- `execute` function is the entry point of flow execution.

Besides this BaseFlow interface, we can also abstract the connection provider impl to factory mode and allow customer using that directly in their code, here's a sample code for `init`:
```python
class EvaluatorFlow(BaseFlow):
    def init(self, flow_settings: dict, *kwargs):
        connection_provider_name = flow_settings.get("CONNECTION_PROVIDER") # provider can also be system configuration
        provider = ConnectionProviderFactory.get_provider(connection_provier_name)
        # customer can hard-code the authoring connection name in the flow implementation and override that on demand
        connection_overrides = flow_settings.get("CONNECTION_OVERRIDES")
        connections_to_load = combine(connection_overrides, hard_coded_connections) # dict, key is
        self.connections = provider.load(connections_to_load.values())
        self.deployment_name = flow_settings.get("chat_model_deployment_name", "gpt-35-turbo")
        self.temperature = flow_settings.get("chat_model_temperature", 0.7)
        self.identity_to_use = flow_settings.get("identity_to_use", "default")
        self.credential = ManagedIdentityCredential() if self.identity_to_user == "managed" else DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            self.credential, "https://cognitiveservices.azure.com/.default"
        )
        azure_open_ai_connection = self.connections.get("azure_open_ai_connection")
        self.aoai_client = AsyncAzureOpenAI(
            azure_endpoint = azure_open_ai_connection.api_base,
            api_version = azure_open_ai_connection.api_version,
            azure_deployment=self.deployment_name,
            azure_ad_token_provider=token_provider
        )
    
    async def execute(self, text: str):
        response = await self.aoai_client.completions.create(
            model="ignored",
            temperature=self.chat_model_temperature,
            prompt=f'answer 1 if the following text contains an apologie, answer 0 if it does not contain an apology\n{text}'    
        )
        print(response.choices[0].text)
        return {'score': int(response.choices[0].text == "1")}
```

From system level, it's easier to support such flow inheritance and it can be easily supported by both authoring and deployment.

From infra perspective, we can detect whether the entry is a function with @flow or it's class inherited from BaseFlow. If it's a function, we don't need to help customer do any initialization; if it's a inherited class, we can help customer trigger the flow initalization before running it.

### Any other proposal?



