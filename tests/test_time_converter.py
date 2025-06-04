import sys
import os
import unittest

# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.time_converter import convert_duration_to_minutes

class TestTimeConverter(unittest.TestCase):
    
    def test_hours_and_minutes(self):
        self.assertEqual(convert_duration_to_minutes("1h 31min"), 91)
        self.assertEqual(convert_duration_to_minutes("2h 15min"), 135)
        self.assertEqual(convert_duration_to_minutes("1h 0min"), 60)
    
    def test_hours_only(self):
        self.assertEqual(convert_duration_to_minutes("2h"), 120)
        self.assertEqual(convert_duration_to_minutes("1 h"), 60)
    
    def test_minutes_only(self):
        self.assertEqual(convert_duration_to_minutes("45min"), 45)
        self.assertEqual(convert_duration_to_minutes("45 min"), 45)
        self.assertEqual(convert_duration_to_minutes("45"), 45)
    
    def test_different_formats(self):
        self.assertEqual(convert_duration_to_minutes("1 hour 30 minutes"), None)  # Not supported format
        self.assertEqual(convert_duration_to_minutes("1h30m"), None)  # Not supported format
        self.assertEqual(convert_duration_to_minutes("1.5h"), None)  # Not supported format
    
    def test_invalid_inputs(self):
        self.assertEqual(convert_duration_to_minutes(""), None)
        self.assertEqual(convert_duration_to_minutes(None), None)
        self.assertEqual(convert_duration_to_minutes(123), None)  # Not a string
        self.assertEqual(convert_duration_to_minutes("invalid"), None)

if __name__ == "__main__":
    unittest.main() 