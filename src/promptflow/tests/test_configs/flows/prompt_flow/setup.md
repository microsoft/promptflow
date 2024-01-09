1. Create a conda environment with Python 11 and activate this conda env.
2. Download vsix and install the extension: https://aka.ms/prompty/vsc
3. Install prompt flow sdk from the private wheel: https://msdata.visualstudio.com/Vienna/_build/results?buildId=115101133&view=artifacts&pathAsName=false&type=publishedArtifacts
4. Install prompt flow tools ```pip install promptflow-tools```
5. Add these 2 environment variables in your environment:
   - AZURE_OPENAI_ENDPOINT
   - AZURE_OPENAI_API_KEY
6. Open the sample.prompt file, click the "test" code lens button on the top.