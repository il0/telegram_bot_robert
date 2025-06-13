#!/usr/bin/env python3
"""
Telegram Bot Debug Script
This script helps diagnose issues with the telegram_bot_robert.py
"""

import json
import logging
import os
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if all required dependencies are installed"""
    print("=== CHECKING DEPENDENCIES ===")
    required_packages = ['telegram', 'pytz']
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} - OK")
        except ImportError as e:
            print(f"❌ {package} - MISSING: {e}")
            print(f"   Install with: pip install {package}")
    
    print()

def check_token_file():
    """Check if token file exists and is readable"""
    print("=== CHECKING TOKEN FILE ===")
    token_file = "/home/users/ilo/bin/telegram_bot_robert/token"
    
    if os.path.exists(token_file):
        print(f"✅ Token file exists: {token_file}")
        try:
            with open(token_file, 'r') as f:
                token = f.read().strip()
                if token:
                    print(f"✅ Token loaded (length: {len(token)})")
                    # Basic format check
                    if ':' in token and len(token) > 20:
                        print("✅ Token format looks valid")
                    else:
                        print("⚠️  Token format might be invalid")
                else:
                    print("❌ Token file is empty")
        except Exception as e:
            print(f"❌ Cannot read token file: {e}")
    else:
        print(f"❌ Token file not found: {token_file}")
        print("   Please create the token file with your bot token")
    
    print()

def check_database():
    """Check database file and structure"""
    print("=== CHECKING DATABASE ===")
    db_file = "accountability_db.json"
    
    if os.path.exists(db_file):
        print(f"✅ Database file exists: {db_file}")
        try:
            with open(db_file, 'r') as f:
                db = json.load(f)
                print(f"✅ Database loaded successfully")
                
                # Check structure
                required_keys = ['users', 'weekly_logs', 'group_chats', 'edited_logs']
                for key in required_keys:
                    if key in db:
                        print(f"✅ {key} section exists ({len(db[key])} items)")
                    else:
                        print(f"⚠️  {key} section missing")
                        
                # Show some stats
                print(f"   Users: {len(db.get('users', {}))}")
                print(f"   Weekly logs: {len(db.get('weekly_logs', {}))}")
                print(f"   Group chats: {len(db.get('group_chats', {}))}")
                
        except json.JSONDecodeError as e:
            print(f"❌ Database file is corrupted: {e}")
        except Exception as e:
            print(f"❌ Error reading database: {e}")
    else:
        print(f"⚠️  Database file not found: {db_file}")
        print("   This is normal for first run")
    
    print()

def check_permissions():
    """Check file permissions"""
    print("=== CHECKING PERMISSIONS ===")
    
    files_to_check = [
        "telegram_bot_robert.py",
        "accountability_db.json",
        "/home/users/ilo/bin/telegram_bot_robert/token"
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            try:
                # Check read permissions
                with open(file_path, 'r') as f:
                    f.read(1)
                print(f"✅ {file_path} - readable")
                
                # Check write permissions for database
                if file_path.endswith('.json') or file_path.endswith('.py'):
                    if os.access(file_path, os.W_OK):
                        print(f"✅ {file_path} - writable")
                    else:
                        print(f"⚠️  {file_path} - not writable")
                        
            except Exception as e:
                print(f"❌ {file_path} - permission error: {e}")
        else:
            print(f"⚠️  {file_path} - not found")
    
    print()

def test_bot_functions():
    """Test basic bot functions"""
    print("=== TESTING BOT FUNCTIONS ===")
    
    try:
        # Import the bot module
        sys.path.append('.')
        import telegram_bot_robert as bot
        print("✅ Bot module imported successfully")
        
        # Test database functions
        db = bot.load_database()
        print("✅ Database load function works")
        
        # Test activity parsing
        test_activities = "M20 S30 Y15"
        parsed = bot.parse_activities(test_activities)
        print(f"✅ Activity parsing works: {parsed}")
        
        # Test week/day key generation
        week_key = bot.get_week_key()
        day_key = bot.get_day_key()
        print(f"✅ Date functions work: week={week_key}, day={day_key}")
        
    except Exception as e:
        print(f"❌ Error testing bot functions: {e}")
        import traceback
        traceback.print_exc()
    
    print()

def check_logs():
    """Check for recent log files"""
    print("=== CHECKING LOG FILES ===")
    
    # Common log locations
    log_locations = [
        "bot.log",
        "telegram_bot.log",
        "/var/log/telegram_bot.log",
        "nohup.out"
    ]
    
    for log_file in log_locations:
        if os.path.exists(log_file):
            print(f"✅ Found log file: {log_file}")
            try:
                # Show last few lines
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        print(f"   Last modified: {datetime.fromtimestamp(os.path.getmtime(log_file))}")
                        print(f"   Size: {len(lines)} lines")
                        if len(lines) > 5:
                            print("   Last 3 lines:")
                            for line in lines[-3:]:
                                print(f"     {line.strip()}")
            except Exception as e:
                print(f"   Error reading log: {e}")
        else:
            print(f"⚠️  Log file not found: {log_file}")
    
    print()

def check_processes():
    """Check if bot is running"""
    print("=== CHECKING RUNNING PROCESSES ===")
    
    try:
        import subprocess
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        
        bot_processes = []
        for line in result.stdout.split('\n'):
            if 'telegram_bot_robert' in line or ('python' in line and 'robert' in line):
                bot_processes.append(line.strip())
        
        if bot_processes:
            print(f"✅ Found {len(bot_processes)} bot process(es):")
            for process in bot_processes:
                print(f"   {process}")
        else:
            print("⚠️  No bot processes found")
            
    except Exception as e:
        print(f"❌ Error checking processes: {e}")
    
    print()

def main():
    print("🔍 TELEGRAM BOT DIAGNOSTIC TOOL")
    print("=" * 50)
    print(f"Timestamp: {datetime.now()}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Python version: {sys.version}")
    print()
    
    check_dependencies()
    check_token_file()
    check_database()
    check_permissions()
    test_bot_functions()
    check_logs()
    check_processes()
    
    print("=" * 50)
    print("🏁 DIAGNOSTIC COMPLETE")
    print()
    print("Next steps:")
    print("1. Fix any ❌ errors shown above")
    print("2. If everything looks good, check the bot logs for runtime errors")
    print("3. Test commands manually in Telegram")
    print("4. Monitor the logs while testing")

if __name__ == '__main__':
    main()

