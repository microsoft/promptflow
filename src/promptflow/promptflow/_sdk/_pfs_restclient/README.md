## Convert Swagger 2.0 to OpenAPI 3.0

1. Use a tool like swagger2openapi to convert your Swagger 2.0 specification to OpenAPI 3.0. You can install swagger2openapi using npm:
```
npm install -g swagger2openapi
```
Then, convert your Swagger 2.0 specification to OpenAPI 3.0:
```
swagger2openapi ../_service/swagger.json -o openapi.yaml
```

## Generate Python Client using AutoRest:

```
pip install openapi-generator-cli
```

```python
openapi-python-client generate --path ./openapi.yaml --meta none --config ./client_config.yaml
```