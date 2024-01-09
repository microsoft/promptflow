1. Create a conda environment with python=3.9 or higher version like 3.10 and activate this conda env.
2. Download vsix and install the extension: https://aka.ms/prompty/vsc
3. Install prompt flow sdk from the private wheel:
   https://msdata.visualstudio.com/Vienna/_build/results?buildId=115503045&view=artifacts&pathAsName=false&type=publishedArtifacts
4. Install prompt flow tools ```pip install promptflow-tools```
5. Add these 2 environment variables in your environment:
   - AZURE_OPENAI_ENDPOINT
   - AZURE_OPENAI_API_KEY
6. Open the sample.prompt file.
7. Use ctrl/cmd+shift+p, use the "Python: set interpreter" command and selecte the environment prepared in step 1.
8. Click the "test" code lens button on the top.
9. Wait for the run completion in the terminal, click "Status:complete" on the top of the yaml editor to visulize the run traces.