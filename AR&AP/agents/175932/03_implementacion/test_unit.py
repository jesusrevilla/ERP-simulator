import unittest
from decimal import Decimal
from contract import parse_quantity


class QuantityContract(unittest.TestCase):
    def test_preserves_decimal(self):
        self.assertEqual(parse_quantity('0.125'), Decimal('0.125'))

    def test_accepts_integer_and_three_decimals(self):
        self.assertEqual(parse_quantity('10'), Decimal('10'))
        self.assertEqual(parse_quantity('10.001'), Decimal('10.001'))

    def test_rejects_invalid_quantities(self):
        for value in ('0', '-1', '1.0001', 'NaN', 'Infinity', '1e3', '', ' 1', 1, True, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_quantity(value)


if __name__ == '__main__':
    unittest.main()
