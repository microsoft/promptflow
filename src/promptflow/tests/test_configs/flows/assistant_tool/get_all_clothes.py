from promptflow import tool


@tool
def get_all_clothes(location: str):
    """Get all available clothes in current location.
    
    :param location: Location to get clothes from.
    :type location: str
    """

    return [  
        "T-shirt",
        "Jeans",
        "Blouse",
        "Dress",
        "Skirt",
        "Sweater",
        "Jacket",
        "Coat",
        "Blazer",
        "Hoodie",
        "Sweatpants",
        "Shorts",
        "Tank Top",
        "Cardigan",
        "Leggings",
        "Pajamas",
        "Underwear",
        "Socks",
        "Swimsuit",
        "Suit"
    ]
