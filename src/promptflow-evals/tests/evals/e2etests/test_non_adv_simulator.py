# flake8: noqa
import asyncio

import pytest

from promptflow.evals.synthetic.simulator.simulator import Simulator


@pytest.mark.usefixtures("model_config", "recording_injection")
@pytest.mark.e2etest
class TestNonAdvSimulator:
    def test_non_adv_conversation(self, model_config):
        from openai import AsyncAzureOpenAI

        oai_client = AsyncAzureOpenAI(
            api_key=model_config.api_key,
            azure_endpoint=model_config.azure_endpoint,
            api_version="2023-12-01-preview",
        )
        userbot_config = {
            "api_base": model_config.azure_endpoint,
            "api_key": model_config.api_key,
            "api_version": model_config.api_version,
            "model_name": "gpt-4",
        }
        template_parameters = [
            {
                "name": "Jane",
                "profile": "Jane Doe is a 28-year-old outdoor enthusiast who lives in Seattle, Washington."
                "She has a passion for exploring nature and loves going on camping and hiking trips with her friends."
                "She has recently become a member of the company's loyalty program and has achieved Bronze level status."
                "Jane has a busy schedule, but she always makes time for her outdoor adventures."
                "She is constantly looking for high-quality gear that can help her make the most of her trips "
                "and ensure she has a comfortable experience in the outdoors."
                "Recently, Jane purchased a TrailMaster X4 Tent from the company."
                "This tent is perfect for her needs, as it is both durable and spacious, allowing her to enjoy her camping trips with ease."
                "The price of the tent was $250, and it has already proved to be a great investment."
                "In addition to the tent, Jane also bought a Pathfinder Pro-1 Adventure Compass for $39.99."
                "This compass has helped her navigate challenging trails with confidence,"
                "ensuring that she never loses her way during her adventures."
                "Finally, Jane decided to upgrade her sleeping gear by purchasing a CozyNights Sleeping Bag for $100."
                "This sleeping bag has made her camping nights even more enjoyable,"
                "as it provides her with the warmth and comfort she needs after a long day of hiking.",
                "tone": "happy",
                "metadata": dict(
                    customer_info="## customer_info      name: Jane Doe    age: 28     phone_number: 555-987-6543     email: jane.doe@example.com     address: 789 Broadway St, Seattle, WA 98101      loyalty_program: True     loyalty_program Level: Bronze        ## recent_purchases      order_number: 5  date: 2023-05-01  item: - description:  TrailMaster X4 Tent, quantity 1, price $250    item_number: 1   order_number: 18  date: 2023-05-04  item: - description:  Pathfinder Pro-1 Adventure Compass, quantity 1, price $39.99    item_number: 4   order_number: 28  date: 2023-04-15  item: - description:  CozyNights Sleeping Bag, quantity 1, price $100    item_number: 7"
                ),
                "task": "Jane is trying to accomplish the task of finding out the best hiking backpacks suitable for her weekend camping trips,"
                "and how they compare with other options available in the market."
                "She wants to make an informed decision before making a purchase from the outdoor gear company's website or visiting their physical store."
                "Jane uses Google to search for 'best hiking backpacks for weekend trips,'"
                "hoping to find reliable and updated information from official sources or trusted websites."
                "She expects to see a list of top-rated backpacks, their features, capacity, comfort, durability, and prices."
                "She is also interested in customer reviews to understand the pros and cons of each backpack."
                "Furthermore, Jane wants to see the specifications, materials used, waterproof capabilities,"
                "and available colors for each backpack."
                "She also wants to compare the chosen backpacks with other popular brands like Osprey, Deuter, or Gregory."
                "Jane plans to spend about 20 minutes on this task and shortlist two or three options that suit her requirements and budget."
                "Finally, as a Bronze level member of the outdoor gear company's loyalty program,"
                "Jane might also want to contact customer service to inquire about any special deals or discounts available"
                "on her shortlisted backpacks, ensuring she gets the best value for her purchase.",
                "chatbot_name": "ChatBot",
            },
            {
                "name": "John",
                "profile": "John Doe is a 35-year-old software engineer who lives in San Francisco, California. He is an avid traveler and enjoys exploring new destinations around the world. He is always on the lookout for the latest travel gear that can make his trips more comfortable and enjoyable."
                "John recently booked a trip to Japan and is excited to explore the country's rich culture and history. He is looking for a reliable and durable travel backpack that can carry all his essentials and provide him with the convenience he needs during his trip."
                "After doing some research, John decided to purchase the Voyager 45L Travel Backpack from the company. This backpack is perfect for his needs, as it is spacious, lightweight, and comes with multiple compartments to keep his belongings organized. The price of the backpack was $150, and it has already proved to be a great investment."
                "In addition to the backpack, John also bought a TravelPro 21-inch Carry-On Luggage for $100. This luggage has made his travel experience even more convenient, as it is compact, durable, and easy to carry around. It has become his go-to choice for short trips and weekend getaways."
                "Finally, John decided to upgrade his travel accessories by purchasing a TravelMate Neck Pillow for $20. This neck pillow has made his long flights more comfortable, ensuring that he arrives at his destination well-rested and ready to explore."
                "John is thrilled with his recent purchases and is looking forward to using them on his upcoming trip to Japan.",
                "tone": "happy",
                "metadata": dict(
                    customer_info="## customer_info      name: John Doe    age: 35     phone_number: 555-123-4567     email: john.doe@example.com     address: 123 Main St, San Francisco, CA 94101      ## recent_purchases      order_number: 10  date: 2023-05-01  item: - description:  Voyager 45L Travel Backpack, quantity 1, price $150    item_number: 2   order_number: 25  date: 2023-05-04  item: - description:  TravelPro 21-inch Carry-On Luggage, quantity 1, price $100    item_number: 5   order_number: 30  date: 2023-04-15  item: - description:  TravelMate Neck Pillow, quantity 1, price $20    item_number: 8"
                ),
                "task": "John is trying to accomplish the task of finding out the best travel backpacks suitable for his upcoming trip to Japan, and how they compare with other options available in the market. He wants to make an informed decision before making a purchase from the outdoor gear company's website or visiting their physical store."
                "John uses Google to search for 'best travel backpacks for Japan trip,' hoping to find reliable and updated information from official sources or trusted websites. He expects to see a list of top-rated backpacks, their features, capacity, comfort, durability, and prices. He is also interested in customer reviews to understand the pros and cons of each backpack."
                "Furthermore, John wants to see the specifications, materials used, waterproof capabilities, and available colors for each backpack. He also wants to compare the chosen backpacks with other popular brands like Osprey, Deuter, or Gregory. John plans to spend about 20 minutes on this task and shortlist two or three options that suit his requirements and budget."
                "Finally, John might also want to contact customer service to inquire about any special deals or discounts available on his shortlisted backpacks, ensuring he gets the best value for his purchase.",
                "chatbot_name": "ChatBot",
            },
        ]
        ch_template = Simulator.get_template("conversation")
        async_oai_chat_completion_fn = oai_client.chat.completions.create
        simulator = Simulator.from_fn(
            fn=async_oai_chat_completion_fn,
            simulator_connection=userbot_config,
            model="gpt-4",
            max_tokens=300,
        )

        outputs = asyncio.run(
            simulator.simulate_async(
                template=ch_template,
                parameters=template_parameters,
                max_conversation_turns=2,
                api_call_delay_sec=15,
                max_simulation_results=2,
            )
        )

        in_json_line_format = outputs.to_json_lines()
        assert in_json_line_format is not None
        assert len(in_json_line_format) > 0
