# Prompt Flow Service
This document will describle the usage of pfs(prompt flow service) CLI.

### Install prompt flow service

You can execute this command to install pfs as a service in your machine.
```commandline
pfs install
```

**Notes:** Adminstrator privileges are required to install the Service on Windows.

### Start prompt flow service (optional)
If you don't install pfs as a service, you need to start pfs manually.
pfs CLI provides **start** command to start service. You can also use this command to specify the service port.

```commandline
usage: pfs start [-h] [-p PORT]

Start prompt flow service.

optional arguments:
  -h, --help            show this help message and exit
  -p PORT, --port PORT  port of the promptflow service
```

If you don't specify a port to start service, pfs will first use the port in the configure file in "~/.promptflow/pf.port".

If not found port configuration or the port is used, pfs will use a random port to start the service.

### Swagger of service
After start the service, it will provide Swagger UI documentation, served from "http://localhost:your-port/v1.0/swagger.json". 

#### Generate C# client
1. Right click the project, Add -> Rest API Client... -> Generate with OpenAPI Generator 
   
2. It will open a dialog, fill in the file name and swagger url, it will generate the client under the project.

For details, please refer to [REST API Client Code Generator](https://marketplace.visualstudio.com/items?itemName=ChristianResmaHelle.ApiClientCodeGenerator2022).