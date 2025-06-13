#!/usr/bin/env python3
"""
Test script to validate core bot functions without dependencies
"""

import re
import json
import os
from datetime import datetime

# Copy the core functions from the bot
def validate_activity_format(activity):
    return bool(re.match(r'^[A-Za-z]\d+$', activity))

def parse_activities(text):
    """Parse activities with improved validation and error handling."""
    activities = {}
    if not text:
        return activities
    
    parts = text.strip().split()
    
    for part in parts:
        if not validate_activity_format(part):
            print(f"DEBUG: Skipping invalid activity format: {part}")
            continue
            
        activity_letter = part[0].upper()
        try:
            value = int(part[1:])
            if value <= 0:
                print(f"DEBUG: Skipping non-positive value: {part}")
                continue
            if value > 10000:  # Reasonable upper limit
                print(f"WARNING: Large activity value detected: {part}")
            
            # If activity already exists, sum the values
            if activity_letter in activities:
                activities[activity_letter] += value
                print(f"DEBUG: Summed duplicate activity {activity_letter}: {activities[activity_letter]}")
            else:
                activities[activity_letter] = value
                
        except ValueError as e:
            print(f"DEBUG: Error parsing activity value in '{part}': {e}")
            continue
    
    return activities

def test_activity_parsing():
    """Test the activity parsing function with various inputs"""
    print("=== TESTING ACTIVITY PARSING ===")
    
    test_cases = [
        "M20 S30",      # Normal case
        "m20 s30",      # Lowercase
        "M20 S30 Y15",  # Multiple activities
        "M20 M10",      # Duplicate activities (should sum)
        "M0",           # Zero value (should be skipped)
        "M-10",         # Negative value (should be skipped)
        "M20 invalid S30", # Mixed valid/invalid
        "M20S30",       # No spaces
        "",             # Empty string
        "M",            # No number
        "20",           # No letter
        "M20 S30 M5",   # More duplicates
        "M100",         # Large value
        "X1 Y2 Z3",     # Multiple single digits
    ]
    
    for test_input in test_cases:
        result = parse_activities(test_input)
        print(f"Input: '{test_input}' -> Output: {result}")
    
    print()

def test_validation():
    """Test the activity format validation"""
    print("=== TESTING VALIDATION ===")
    
    test_cases = [
        "M20",      # Valid
        "m20",      # Valid (lowercase)
        "M0",       # Valid format but zero value
        "M-10",     # Valid format but negative
        "M",        # Invalid - no number
        "20",       # Invalid - no letter
        "M20S30",   # Invalid - multiple activities together
        "invalid",  # Invalid - not the right format
        "M20X",     # Invalid - letter at end
        "MM20",     # Invalid - multiple letters
        "M20.5",    # Invalid - decimal
        "M 20",     # Invalid - space
        "2M0",      # Invalid - number first
    ]
    
    for test_input in test_cases:
        result = validate_activity_format(test_input)
        print(f"Format '{test_input}': {'VALID' if result else 'INVALID'}")
    
    print()

def test_command_scenarios():
    """Test realistic command scenarios"""
    print("=== TESTING COMMAND SCENARIOS ===")
    
    scenarios = [
        {
            "name": "Basic daily log",
            "input": "M20 S30",
            "expected": {"M": 20, "S": 30}
        },
        {
            "name": "Multiple same activities",
            "input": "M10 M15 M5", 
            "expected": {"M": 30}
        },
        {
            "name": "Mixed case",
            "input": "m20 S30 y15",
            "expected": {"M": 20, "S": 30, "Y": 15}
        },
        {
            "name": "With invalid entries",
            "input": "M20 invalid S30 also_invalid Y15",
            "expected": {"M": 20, "S": 30, "Y": 15}
        },
        {
            "name": "All invalid",
            "input": "invalid also_invalid 123",
            "expected": {}
        },
        {
            "name": "Empty input",
            "input": "",
            "expected": {}
        },
        {
            "name": "Zero and negative values",
            "input": "M0 S-10 Y20",
            "expected": {"Y": 20}
        }
    ]
    
    for scenario in scenarios:
        result = parse_activities(scenario["input"])
        success = result == scenario["expected"]
        status = "✅ PASS" if success else "❌ FAIL"
        
        print(f"{status} {scenario['name']}")
        print(f"  Input: '{scenario['input']}'")
        print(f"  Expected: {scenario['expected']}")
        print(f"  Got: {result}")
        if not success:
            print(f"  ❌ MISMATCH!")
        print()

def main():
    print("🧪 TELEGRAM BOT CORE FUNCTIONS TESTING")
    print("=" * 50)
    
    test_activity_parsing()
    test_validation()
    test_command_scenarios()
    
    print("=" * 50)
    print("🏁 TESTING COMPLETE")

if __name__ == '__main__':
    main()

