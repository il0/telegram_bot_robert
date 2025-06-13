#!/usr/bin/env python3
"""
Test script to validate bot command handlers
"""

import sys
import os
sys.path.append('.')

def test_activity_parsing():
    """Test the activity parsing function with various inputs"""
    print("=== TESTING ACTIVITY PARSING ===")
    
    try:
        import telegram_bot_robert_fixed as bot
        
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
        ]
        
        for test_input in test_cases:
            result = bot.parse_activities(test_input)
            print(f"Input: '{test_input}' -> Output: {result}")
            
    except Exception as e:
        print(f"Error testing activity parsing: {e}")
        import traceback
        traceback.print_exc()
    
    print()

def test_database_operations():
    """Test database operations"""
    print("=== TESTING DATABASE OPERATIONS ===")
    
    try:
        import telegram_bot_robert_fixed as bot
        
        # Load database
        db = bot.load_database()
        print(f"Database loaded: {type(db)}")
        
        # Test user initialization
        test_user_id = 12345
        test_username = "testuser"
        bot.init_user(db, test_user_id, test_username)
        print(f"User initialized: {test_user_id}")
        
        # Test logging activities
        activities = {"M": 20, "S": 30}
        success = bot.log_activities(db, test_user_id, test_username, activities)
        print(f"Log activities result: {success}")
        
        # Test getting summary
        summary = bot.get_user_weekly_summary(db, test_user_id)
        print(f"Weekly summary: {summary}")
        
        # Test date functions
        week_key = bot.get_week_key()
        day_key = bot.get_day_key()
        print(f"Week key: {week_key}, Day key: {day_key}")
        
    except Exception as e:
        print(f"Error testing database operations: {e}")
        import traceback
        traceback.print_exc()
    
    print()

def test_handler_logic():
    """Test the logic that would run in command handlers"""
    print("=== TESTING HANDLER LOGIC ===")
    
    try:
        import telegram_bot_robert_fixed as bot
        
        # Simulate log command logic
        print("Testing log command logic...")
        
        # Test various argument combinations
        test_args_list = [
            ["M20", "S30"],
            ["M20"],
            [],  # No args
            ["invalid"],
            ["M20", "S30", "Y15"]
        ]
        
        for args in test_args_list:
            print(f"\n  Testing args: {args}")
            
            if not args:
                print("    No arguments provided - would show help")
                continue
            
            activities_text = " ".join(args)
            activities = bot.parse_activities(activities_text)
            
            if not activities:
                print("    No valid activities parsed - would show error")
                continue
            
            print(f"    Parsed activities: {activities}")
            
            # Simulate database operation
            db = bot.load_database()
            success = bot.log_activities(db, 99999, "testuser", activities)
            print(f"    Database operation: {'SUCCESS' if success else 'FAILED'}")
            
            if success:
                # Generate response text
                response_text = "✅ Logged successfully:\n"
                for activity, value in activities.items():
                    response_text += f"{activity}: {value} units\n"
                print(f"    Response: {response_text.strip()}")
        
    except Exception as e:
        print(f"Error testing handler logic: {e}")
        import traceback
        traceback.print_exc()
    
    print()

def main():
    print("🧪 TELEGRAM BOT COMMAND TESTING")
    print("=" * 50)
    
    test_activity_parsing()
    test_database_operations()
    test_handler_logic()
    
    print("=" * 50)
    print("🏁 TESTING COMPLETE")

if __name__ == '__main__':
    main()

