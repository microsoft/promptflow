from promptflow import tool


@tool
def prepare_example():
    return [
      {
        "question": "What is 37593 * 67?",
        "code": "{\n    \"code\": \"print(37593 * 67)\"\n}",
        "answer": "2512641",
      },
      {
        "question": "What is the value of x in the equation 2x + 3 = 11?",
        "code": "{\n    \"code\": \"print((11-3)/2)\"\n}",
        "answer": "4",
      },
      {
        "question": "How many of the integers between 0 and 99 inclusive are divisible by 8?",
        "code": "{\n    \"code\": \"count = 0\\nfor i in range(100):\\n    \
          if i % 8 == 0:\\n        count += 1\\nprint(count)\"\n}",
        "answer": "10",
      },
      {
        "question": "Janet's ducks lay 16 eggs per day. \
          She eats three for breakfast every morning and bakes muffins for her friends every day with four.\
            She sells the remainder at the farmers' market daily for $2 per fresh duck egg. \
              How much in dollars does she make every day at the farmers' market?",
        "code": "{\n    \"code\": \"print((16-3-4)*2)\"\n}",
        "answer": "18",
      },
      {
        "question": "What is the sum of the powers of 3 (3^i) that are smaller than 100?",
        "code": "{\n    \"code\": \"sum = 0\\ni = 0\n\
          while 3**i < 100:\\n    sum += 3**i\\n    i += 1\\nprint(sum)\"\n}",
        "answer": "40",
      },
      {
        "question": "Carla is downloading a 200 GB file. She can download 2 GB/minute, \
          but 40% of the way through the download, the download fails.\
            Then Carla has to restart the download from the beginning. \
              How load did it take her to download the file in minutes?",
        "code": "{\n    \"code\": \"print(200/2*1.4)\"\n}",
        "answer": "140",
      },
      {
        "question": "What is the sum of the 10 first positive integers?",
        "code": "{\n    \"code\": \"print(sum(range(1,11)))\"\n}",
        "answer": "55",
      }
    ]
