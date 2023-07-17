## Working with Connection in Prompt Flow
This repository contains example `YAML` files for creating `connection` using prompt-flow cli. Learn more on all the [connections types](https://promptflow.azurewebsites.net/concepts/concept-connections.html).


- To create a connection using any of the sample `YAML` files provided in this directory, execute following command:
```bash
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
pf connection update -n custom_connection --set configs.key1='abc'
```

- To delete a connection:
```bash
pf connection delete -n <connection_name>
```
