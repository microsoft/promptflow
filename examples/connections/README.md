# Working with Connection in Prompt Flow
This repository contains example `YAML` files for creating `connection` using prompt-flow cli. Learn more on all the [connections types](https://promptflow.azurewebsites.net/concepts/concept-connections.html).

## Prerequisites
- Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Get started

- To create a connection using any of the sample `YAML` files provided in this directory, execute following command:
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f custom.yml --set configs.key1='abc'
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
pf connection update -n my_azure_open_ai_connection --set api_base='new_value'
# Update a custom connection
pf connection update -n custom_connection --set configs.key1='abc' secrets.key2='xyz'
```

- To delete a connection:
```bash
pf connection delete -n <connection_name>
```
