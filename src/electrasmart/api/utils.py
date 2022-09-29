from math import floor, pow
from random import randint


def generate_imei() -> str:
    minimum = int(pow(10, 7))
    maximum = int(pow(10, 8) - 1)
    return f"2b950000{str(floor(randint(minimum, maximum)))}"
