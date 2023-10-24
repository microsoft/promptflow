# Prompt flow for JavaScript/TypeScript

## What is the value-add of providing JavaScript/TypeScript support for Prompt flow

- JavaScript /TypeScript is a popular programming language for Web UI and web view based app development. JS/TS supports for Prompt flow will empower developers to code integration to connect the user interface with PF flows **without adding extra service or deployment**. The flows will be hosted and executed in the client JavaScript engine (Browser, web container, Node.js runtime) and flow developers do not have to worry about the distributing or hosting.

## JS/TS language constraints and design considerations

- Despite TypeScript are widely used in Microsoft and many other developers, it is not a official standard. There are lots of diverged JS standards.
  - For language spec, es5(legacy), es6 es2016, es2017, ... es2023, supports.
  - For typing support, there are TypeScript, Flow, etc.
  - For module definition, there are IIFE, AMD, CJS, UMD, ESM.
- JavaScript in real world is a programming language which requires to be **compiled before being interpreted**.
  - Compiler's job: 
    - [**Bundling**: Compilers can bundle multiple JavaScript files into a single file, which can be more efficient for the browser to download and execute ](https://stackoverflow.com/questions/67231389/why-we-need-webpack-in-2021) [ref](https://stackoverflow.com/questions/67231389/why-we-need-webpack-in-2021).
    - [**Minification**: Compilers can also minify the code by removing whitespace and comments, which can reduce the file size and improve performance ](https://stackoverflow.com/questions/67231389/why-we-need-webpack-in-2021) [ref](https://stackoverflow.com/questions/67231389/why-we-need-webpack-in-2021).
    - [**Transpilation**: Compilers can transpile newer JavaScript syntax into older syntax that is more widely supported by browsers ](https://stackoverflow.com/questions/67231389/why-we-need-webpack-in-2021) [ref](https://stackoverflow.com/questions/67231389/why-we-need-webpack-in-2021).
    - [**Optimization**: Compilers can optimize the code by removing dead code and other unnecessary parts of the code](https://stackoverflow.com/questions/67231389/why-we-need-webpack-in-2021)
  - Popular compiler options: Webpack, Rollup, Esbuild, Vite, etc. They are not compatible with each other.
- Design considerations:
  - Packing, distributing or deployment is not the priority for JavaScript supports for local PF. In local, user code can make JS/TS function calls to a flow instance as usual code, with TypeScript support.
  - For AZ attached PF experience, a PF flow can be built (export) as a NPM package.  NPM meta infos:
    - "type": "module". 
    - "main": "dist/index.cjs". It is a CJS bundle could be consumed in Node.Js env.
    - "module": "dist/index.mjs",  It is a ESM bundle for browser.
    - "source": N/A. The package contains NO source code.
    - "dependencies": pf packages + az core packages + auth packages + arm packages (for rp calls) + custom dependencies.
  - In-code call experience should be a priority. 
    - In current Prompt flow for Python, there is no function call support to consume a flow instance in user code.
    - How to avoid api key leaking?
    - Should be adapters for popular JavaScript frameworks. Like what XState does: [Packages | Stately](https://stately.ai/docs/category/xstate-packages)
    - Should be caching to save customer LLM calls.

## A typical user story

To make a LLM powered copilot VSCode extension with chat inputs and VSCode workspace as inputs.

![image-20231023172528285](/Users/yucongj/github/promptflow/src/promptflow-js/assets/image-20231023172528285.png)

- With Prompt flow (python)
  - Create a new flow with PF authoring experience.
  - Prepare a dataset with tune and evaluate flow with PF features.
  - When user feels the flow is good enough, deploy it as an endpoint.
  - Init a new git repo to for the copilot extension.
  - Implement the chat inputs and answer ui.
  - Writes code to call the button in the chat button click handler.
  - Do integration testing and distribute the copilot extension.
- With Prompt flow (python) (option 2)
  - Create a new flow with PF authoring experience.
  - Prepare a dataset with tune and evaluate flow with PF features.
  - When user feels the flow is good enough, deploy it as a Streamlit app.
  - Init a new git repo for copilot extension.
  - Write glue code to embed the Streamlit app into the extension UI container.
  - Do integration testing and distribute the copilot extension.
- With Promt flow with JavaScript support.
  - Init a TypeScript repo following the VS Code extension develop guideline as the extension codebase.
  - Implement the chat inputs and answer ui.
  - Add prompt flow js sdk libs as the dependencies or dev dependencies to the repo.
  - Author a flow with js code experience in the repo.
  - Integrate prompt flow build step into the existing build toolchain.
  - Do code integration between ui chat button and the flow instance.
  - Debug the flow and debug the app at the same time.
  - Integrate evaluation into the app CI/CD pipelines.

## Design directions

### Connections

- With AZ attaching approach, connections are stored in RP. Should user consume RP apis for their production code?
- For local development, we cannot enforce to use workspace RP or local db to store user connections. It will introduce extra dependencies to user codebase. Needs to specify the pure code approach for connections.

### Tools

- Script tools:
  - Local: separated code files. Specify the entry path in the flow.dag.yaml.
  - Portal UI: Flatten view inline code.
- Package tools:
  - Local: 3rd parth NPM packages. User can use .npmrc (.yarnrc) to specify different npm registry as normal JavaScript repos.
  - Portal UI: a UI form to add 3rd party libraries from different registries.



## Flow Authoring/Debug/Test experience.

todo

## Flow consuming experience

Todo

## Browser experience

### A basic sample 

```html
<html>
  <body>
    <script src="https://some.cdn.com/promptflow.js"></script>
    <script type="module"> 
    	export const helloJinja = `
    		{# Please replace the template with your own prompt. #}
				Write a simple {{text}} program that displays the greeting message when executed.
`
    </script>
    <script src="https://some.cdn.com/openai"></script>
    <script nomodule>
    	define("hello", ["OpenAI"], function(OpenAI) {
        return function myJavaScriptAMDTool (inputs) {
          var openAIClient = new OpenAI({
            apiKey: inputs.apiKey
          });
          
          //...
        }
      });
    </script>
    <script>
    	var flowYamlString = ```
    	inputs:
        text:
          type: string
          default: Hello World!
        outputs:
          output:
            type: string
            reference: \$\{llm.output\}
      nodes:
      - name: hello_prompt
        type: prompt
        source:
          type: jinja
          root: helloJinja
        inputs:
          text: \$\{inputs.text\}
      - name: llm
        type: amd
        source:
          type: code
          amd: hello
        inputs:
        	apiKey: "my-api-key"
          prompt: \$\{hello_prompt.output\}
          deployment_name: text-davinci-003
          max_tokens: "120"
        dependencies:
          openAI  	
    	```;
      var flow = PF.Flow.fromYaml(flowYamlstring);
      var inputs = {"<flow_input_name>": "<flow_input_value>"};    
      
      flow
        .test(inputs: optitions: {})
      	.then(function(res) {
          console.log(res); // { detail: "detail json", output: "output json", log: "log text" }
      	})
      	.catch(function() {
          // error handler
        })
    </script>
  </body>
</html>

```

- ***It does not require any service behind it.***
- I do feel that using YAML is not a good idea with this pure browser inline scripts approach. Let's checkout the web ui experience.

## Web UI experience

1. PromptFlow SDK

Web UI developer needs to introduce PromptFlow JS SDK.

```html
 <script src="https://some.cdn.com/promptflow.js"></script>
```

```bash
yarn add @promptflow/core @promptflow/react
```



2. User script tools:

User's template jinja file content.

```jinja2
{# Please replace the template with your own prompt. #}
Write a simple {{text}} program that displays the greeting message when executed.
```

User's tool code in TypeScript

```typescript
import { OpenAIClient, AzureKeyCredential } from "@azure/openai";
import process from "process";
import { IJsTool } from "prompt-flow";

export interface IHelloToolInputs {
  prompt: string;
  deploymentName: string;
  suffix?: string;
  maxTokens?: number;
  temperature?: number;
  topP?: number;
  n?: number;
  logprobs?: number;
  echo?: boolean;
  stop?: string[];
  presencePenalty?: number;
  frequencyPenalty?: number;
  bestOf?: number;
  logitBias?: Record<string, number>;
  user?: string;
}

export const HelloTool: IJsTool<IHelloToolInputs, string> = async ({ deploymentName, prompt, ...others }) => {
  if (!process.env.AZURE_OPENAI_API_KEY || !process.env.AZURE_OPENAI_API_BASE) {
    throw new Error("AZURE_OPENAI_API_KEY is not set");
  }

  const openai = new OpenAIClient(process.env.AZURE_OPENAI_API_BASE, new AzureKeyCredential(process.env.AZURE_OPENAI_API_KEY));
  const { choices } = await openai.getCompletions(deploymentName, [prompt], others);

  return choices?.[0]?.text;
}
```

Use vite in node js server or browser-vite in browser: [divriots/browser-vite: Vite in the browser. (github.com)](https://github.com/divriots/browser-vite) to bundle user script tools.

3. Other 3rd party reference.

Many browsers lack of full support for ES Modules. We may need some extra UI controls to introduce the 3rd party references and it will be concat to the html.

Like CodeSandbox does:

<img src="/Users/yucongj/Library/Application Support/typora-user-images/image-20231010203027844.png" alt="image-20231010203027844" style="zoom:50%;" />

<script src="https://some.cdn.com/openai"></script>



4. Flow inputs

   ```js
   var inputs = {"<flow_input_name>": "<flow_input_value>"};   
   ```

​	WebUI reads user inputs form and generate this piece of code snippet.



5. The flow

We will use the content from flow.dag.yaml to generate it.

```js
var flowYamlString = ```
    	inputs:
        text:
          type: string
          default: Hello World!
        outputs:
          output:
            type: string
            reference: \$\{llm.output\}
      nodes:
      - name: hello_prompt
        type: prompt
        source:
          type: module
          root: helloJinja
        inputs:
          text: \$\{inputs.text\}
      - name: llm
        type: amd
        source:
          type: code
          amd: hello
        inputs:
        	apiKey: "my-api-key"
          prompt: \$\{hello_prompt.output\}
          deployment_name: text-davinci-003
          max_tokens: "120"
        environment:
          python_requirements_txt: requirements.txt   	
    	```;
var flow = PF.fromYaml(flowYamlstring);
```



6. Flow test

Our web app will run this code to perform the flow test:

```typescript
import { pfclient } from "promptflow";

const result = await pfclient.test({
  flow, 
  inputs
});


```





7. Impelementation of the "test" method.

- We may need web worker to do this. Otherwise the whole page would freeze during testing.

- Step 1: parse the flow yarm to JS objects.
- Step 2: topo-sorting
- Step 3: use js dynamic import to import tool code. Then wrap each tool code to JavaScript function.
- Step 4: pipe the function calls one by one.

8. Visualize flow test result on the WebUI page

WebUI page listens to the "onFlowDidRun" event and use the "res" object to perform the result visualization. 



## Code experience

### load flow

Get a flow instance from json/yaml strings. In the future, we may support more template engines or even DSLs.

```typescript
import { FlowDAG } from "@promptflow/core";
import flowJSONString from "path/to/flow.dag.json";
import flowYAMLString from "path/to/flow.dag.yaml";

const flowFromJSON: FlowDAG = FlowDAG.fromJSON(flowJSONString);
const flowFromYaml: FlowDAG = FlowDAG.fromYaml(flowYAMLString);

```

### DAG Visualization

#### React component to visualize flow dag.

```tsx
import { FlowDAG } from "@promptflow/core";
import { FlowGraph } from "@promptflow/react";
import * as React from "react";

export const MyComponent: React.FC = () => {
    const [flowDag, setFlowDag] = React.useState<Flow | undefined>();
    const onDagDidChange = (newValue: string) => {
        setFlow(FlowDAG.fromYaml(newValue));
    };
    
    return (
    	<div>
           <MyYamlEditor onChange={onDagDidChange} />
        	<FlowGraph flowDag={flowDag} />
        </div>
    );
}
```



#### Get raw html

```typescript
import { FlowDAG } from "@promptflow/core";
import PromptFlowDOM from "@promptflow/web";
import flowYAMLString from "path/to/flow.dag.yaml";

const flowDAG: FlowDAG = FlowDAG.fromYAML(flowYAMLString);
const htmlContent: string = PromptFlowDOM.toHTMLString(flowDAG);
```

### Whole playground experience

#### React component

```tsx
import { Flow, emptyFlowDag } from "@promptflow/core";
import { PlayGround } from "@promptflow/react";
import * as React from "react";

export const MyWebPage: React.FC = () => {
  const [flow, setFlow] = React.useState<Flow>({
    flowDag: emptyFlowDag,
    tools: []
  });  
  
  return <PlayGround flow={flow} onFlowDidChange={setFlow} />;
}
```

