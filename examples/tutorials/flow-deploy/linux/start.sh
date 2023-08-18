# Startup script for the flow container
ls
ls connections
export USER_AGENT=promptflow-appservice
pf connection create --file /connections/basic_custom_connection.yaml
pf flow serve --source flow --host 0.0.0.0
