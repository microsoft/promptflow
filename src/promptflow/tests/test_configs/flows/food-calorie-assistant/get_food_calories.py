import random
from promptflow.core import tool

@tool
def get_food_calories(food: str, amount: float, unit: str) -> float:
    """
    Get the approximate calorie content for a specified amount and type of food.

    :param food: the name of the food item. e.g. 'apple', 'rice', 'pizza'
    :type food: str
    :param amount: the quantity of the food item
    :type amount: float
    :param unit: the unit of measurement for the amount of the food item. e.g. 'g', 'oz', 'cup'
    :type unit: str
    """
    print(f"Get the calories for {food}, with amount={amount} and unit={unit}")
    return round(random.uniform(50, 500), 2)