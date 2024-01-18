# How to construct test data based on documents
This guide will help to construct test data based on the provided documents.
The test data construction process contains three steps:
- Split documents to smaller trunks.
- Based on each document trunk generate a test data containing `question`, `answer`, `context` and `question_type`.
By `question_type`, the given flow sample would evolve the simple question into more diverse question types like reasoning and conditional.
- Collect all the test data and remove empty values.

## Data preprocess
### Local
#### Prerequisites
Enter `test_data_gen_local` folder, run below command to install required packages.
```bash
pip install -r requirements.txt
```

#### Get started
- Enter [construct_test_data_flow folder](../../examples/test_data_gen/construct_test_data_flow/) to tune your prompt in order to customize your own test data gen logic.
> [!Note] This step can be skipped if you just want to have a try.

- Enter [test_data_gen_local folder](../../examples/test_data_gen/test_data_gen_local)
    - Update configs in `configs.ini`
    - After configuration, run below command to gen test data set.
      ```bash
      python run_test_data_gen.py
      ```
    - The generated test data would be a data jsonl file with path you configured in `config.ini`

### Cloud
If you want to deal with large test data, you can leverage PRS to run flow in pipeline.
#### Prerequisites
Enter `test_data_gen_pipeline` folder, run below command to install required packages.
```bash
pip install -r requirements.txt
```

#### Get started
- Enter [test_data_gen_pipeline folder](../../examples/test_data_gen/test_data_gen_pipeline)
    - Update configs in `configs.ini`
    - After configuration, run below command to gen test data set.
      ```bash
      python run_test_data_gen_pipeline.py
      ```
    - The generated test data would be a data asset which you can find by the last node output. You can register that data asset as a registered data asset for later use.