"""Exact decimal contract shared by the receipt registration adapter."""
from decimal import Decimal
import re


def parse_quantity(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,15}(\.[0-9]{1,3})?', value):
        raise ValueError('Quantity must be decimal text with at most 3 decimals')
    number = Decimal(value)
    if number <= 0:
        raise ValueError('Quantity must be positive')
    return number
