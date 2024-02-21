# Upgrade swagger to openapi
Install the tool
```
npm install -g swagger2openapi
```
Run conversion
```
swagger2openapi --yaml --outfile openapi.yaml ../_service/swagger.json
```


# Generate python client

```commandline
autorest --python --track2 --version=3.9.0 --use=@autorest/python --input-file=openapi.yaml --output-folder=. --namespace=pfs_client
```
