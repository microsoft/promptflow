import asyncio

from workflow import AutoGPTInput, workflow


async def main():
    print("--- Running autonomous agent ---")
    result = await workflow.run(
        AutoGPTInput(
            name="FilmTriviaGPT",
            goals=[
                "Introduce 'Lord of the Rings' film trilogy including the film title, "
                "release year, director, current age of the director, production company "
                "and a brief summary of the film."
            ],
            role=(
                "an AI specialized in film trivia that provides accurate and up-to-date "
                "information about movies, directors, actors, and more."
            ),
        )
    )
    print(f"Output:\n{result.get_outputs()[0]}")


if __name__ == "__main__":
    asyncio.run(main())
