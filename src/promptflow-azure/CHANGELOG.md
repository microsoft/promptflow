# promptflow-azure package

## v1.11.0 (2024.05.17)

### Improvements
- Refine trace Cosmos DB setup process to print setup status during the process, and display error message from service when setup failed.
- Return the secrets in the connection object by default to improve flex flow experience.
  - Behaviors not changed: 'pfazure connection' command will scrub secrets.
  - New behavior: connection object by `client.connection.get` will have real secrets. `print(connection_obj)` directly will scrub those secrets. `print(connection_obj.api_key)` or `print(connection_obj.secrets)` will print the REAL secrets.
  - Workspace listsecrets permission is required to get the secrets. Call `client.connection.get(name, with_secrets=True)` if you want to get without the secrets and listsecrets permission.
- [promptflow-azure] Check workspace/project trace Cosmos DB status and honor when create run in Azure.

## v1.10.0 (2024.04.26)

## v1.9.0 (2024.04.17)
