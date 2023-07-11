from promptflow import tool


@tool
def prepare_examples():
    return [
        {
            "url": "https://play.google.com/store/apps/details?id=com.spotify.music",
            "text_content": "Spotify is a free music and podcast streaming app with millions of songs, albums, and "
            "original podcasts. It also offers audiobooks, so users can enjoy thousands of stories. "
            "It has a variety of features such as creating and sharing music playlists, discovering "
            "new music, and listening to popular and exclusive podcasts. It also has a Premium "
            "subscription option which allows users to download and listen offline, and access "
            "ad-free music. It is available on all devices and has a variety of genres and artists "
            "to choose from.",
            "category": "App",
            "evidence": "Both",
        },
        {
            "url": "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw",
            "text_content": "NFL Sunday Ticket is a service offered by Google LLC that allows users to watch NFL "
            "games on YouTube. It is available in 2023 and is subject to the terms and privacy policy "
            "of Google LLC. It is also subject to YouTube's terms of use and any applicable laws.",
            "category": "Channel",
            "evidence": "URL",
        },
        {
            "url": "https://arxiv.org/abs/2303.04671",
            "text_content": "Visual ChatGPT is a system that enables users to interact with ChatGPT by sending and "
            "receiving not only languages but also images, providing complex visual questions or "
            "visual editing instructions, and providing feedback and asking for corrected results. "
            "It incorporates different Visual Foundation Models and is publicly available. Experiments "
            "show that Visual ChatGPT opens the door to investigating the visual roles of ChatGPT with "
            "the help of Visual Foundation Models.",
            "category": "Academic",
            "evidence": "Text content",
        },
        {
            "url": "https://ab.politiaromana.ro/",
            "text_content": "There is no content available for this text.",
            "category": "None",
            "evidence": "None",
        },
    ]
