# Startup script for the flow container
ls
ls connections
pf connection create --file /connections/custom_connection.yaml
pf flow serve --source flow --host 0.0.0.0
