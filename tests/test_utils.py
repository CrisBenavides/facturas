"""
Tests for utility functions
"""

import unittest
from src.utils import format_rut, validate_rut


class TestUtilFunctions(unittest.TestCase):
    """Test utility functions"""

    def test_format_rut(self):
        """Test RUT formatting"""
        result = format_rut("12345678-9")
        self.assertEqual(result, "123456789-9")

    def test_validate_rut(self):
        """Test RUT validation"""
        self.assertTrue(validate_rut("12.345.678-9"))
        self.assertTrue(validate_rut("123456789"))
        self.assertFalse(validate_rut(""))
        self.assertFalse(validate_rut("invalid"))


if __name__ == "__main__":
    unittest.main()
