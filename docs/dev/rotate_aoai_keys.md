Here is a checklist to rotate the AOAI keys:
1. Go to the well known URL of the AOAI service.
2. Check the secondary keys (This is the key used in the following days).
3. Change [promptflow-eastus2euap](https://ml.azure.com/prompts/list?wsid=/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourcegroups/promptflow/providers/Microsoft.MachineLearningServices/workspaces/promptflow-eastus2euap&tid=72f988bf-86f1-41af-91ab-2d7cd011db47#FlowsConnections) Connections
4. Also Change [promptflow-eastus](https://ml.azure.com/prompts/list?wsid=/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourceGroups/promptflow/providers/Microsoft.MachineLearningServices/workspaces/promptflow-eastus&tid=72f988bf-86f1-41af-91ab-2d7cd011db47#FlowsConnections) Connections
5. Save the key in the well known key vault.
6. Save the key in the github secrets, to mask the key.
7. Rotate the DEPRECATED the leaked key in the AOAI service.