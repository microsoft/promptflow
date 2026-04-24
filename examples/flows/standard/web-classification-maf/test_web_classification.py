import asyncio

from workflow import workflow


async def main():
    urls = [
        "https://play.google.com/store/apps/details?id=com.twitter.android",
        "https://arxiv.org/abs/2307.04767",
        "https://www.youtube.com/watch?v=kYqRtjDBci8",
    ]
    for url in urls:
        print(f"\n--- Classifying: {url} ---")
        result = await workflow.run(url)
        output = result.get_outputs()[0]
        print(f"Category: {output.get('category')}")
        print(f"Evidence: {output.get('evidence')}")


if __name__ == "__main__":
    asyncio.run(main())
