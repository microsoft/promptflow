# Working with Connection
This folder contains example `YAML` files for creating `connection` using `pf` cli. Learn more on all the [connections types](https://promptflow.azurewebsites.net/concepts/concept-connections.html).

## Prerequisites
- Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Get started

- To create a connection using any of the sample `YAML` files provided in this directory, execute following command:
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f custom.yml --set configs.key1='<your_api_key>'
pf connection create -f azure_openai.yml --set api_key='<your_api_key>'
```

- To create a custom connection using an `.env` file, execute following command:
```bash
pf connection create -f .env --name custom_connection
```

- To list the created connection, execute following command:
```bash
pf connection list
```

- To show one connection details, execute following command:
```bash
pf connection show --name custom_connection
```

- To update a connection that in workspace, execute following command. Currently only a few fields(description, display_name) support update:
```bash
# Update an existing connection with --set to override values
# Update an azure open ai connection with a new api base
pf connection update -n open_ai_connection --set api_base='<your_api_base>'
# Update a custom connection
pf connection update -n custom_connection --set configs.key1='<your_new_key>' secrets.key2='<your_another_key>'
```

- To delete a connection:
```bash
pf connection delete -n custom_connection
```
