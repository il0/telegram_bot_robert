#!/usr/bin/env python
import json
import logging
import os
import re
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Path to the token file
TOKEN_FILE_PATH = "/home/users/ilo/bin/telegram_bot_robert/token"

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Read the token from file
def read_token():
    try:
        with open(TOKEN_FILE_PATH, 'r') as token_file:
            return token_file.read().strip()
    except Exception as e:
        logger.error(f"Error reading token file: {e}")
        raise RuntimeError(f"Could not read token from {TOKEN_FILE_PATH}. Please check the file exists and has correct permissions.")

# Get the token
TOKEN = read_token()

# Database file
DB_FILE = "accountability_db.json"

# Default database structure
DEFAULT_DB = {
    "users": {},
    "weekly_logs": {},
    "group_chats": {},
    "edited_logs": {},  # Track edited logs
    "user_settings": {},  # User preferences (reminders, goals, etc.)
    "achievements": {},  # User achievements and badges
    "templates": {},  # User activity templates
    "activity_definitions": {},  # User-defined activity meanings
    "challenges": {},  # Weekly/monthly challenges
    "backups": {}  # Backup metadata
}

# Timezone (change to your preferred timezone)
TIMEZONE = pytz.timezone('Europe/Helsinki')

# Load database
def load_database():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                db = json.load(f)
                # Ensure the edited_logs field exists
                if "edited_logs" not in db:
                    db["edited_logs"] = {}
                return db
        except json.JSONDecodeError:
            logger.error("Error decoding database file")
            return DEFAULT_DB.copy()
    return DEFAULT_DB.copy()

# Save database
def save_database(db):
    """Save database with error handling and backup on failure."""
    try:
        # Create backup file first
        temp_file = f"{DB_FILE}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(db, f, indent=2)
        
        # Atomic move to replace original file
        os.rename(temp_file, DB_FILE)
        logger.debug("Database saved successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error saving database: {e}")
        # Clean up temp file if it exists
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass
        return False

# Get current week key (YYYY-WXX format)
def get_week_key():
    now = datetime.now(TIMEZONE)
    return f"{now.year}-W{now.strftime('%V')}"

# Get current day key (YYYY-M-D format)
def get_day_key():
    now = datetime.now(TIMEZONE)
    return f"{now.year}-{now.month}-{now.day}"

# Initialize user if not exists
def init_user(db, user_id, username):
    week_key = get_week_key()
    user_id_str = str(user_id)
    
    if user_id_str not in db["users"]:
        db["users"][user_id_str] = {
            "username": username,
            "joined_date": datetime.now(TIMEZONE).isoformat(),
            "activity_totals": {},
            "reminders_enabled": True,  # Default to enabled
            "current_streak": 0,  # Current consecutive days logged
            "longest_streak": 0,  # Longest streak ever
            "last_log_date": None,  # Last date user logged (for streak calculation)
            "total_logs": 0,  # Total number of days logged
            "achievements": [],  # List of earned achievements
            "goals": {},  # Weekly goals per activity
            "activity_definitions": {}  # User-defined activity meanings
        }
    
    if week_key not in db["weekly_logs"]:
        db["weekly_logs"][week_key] = {}
    
    if user_id_str not in db["weekly_logs"][week_key]:
        db["weekly_logs"][week_key][user_id_str] = {
            "logs": {},
            "missed_days": []
        }

# Validate activity format (1-2 letters followed by number)
def validate_activity_format(activity):
    return bool(re.match(r'^[A-Za-z]{1,2}\d+$', activity))

# Parse activities from log command
def parse_activities(text):
    """Parse activities with improved validation and error handling."""
    activities = {}
    if not text:
        return activities
    
    parts = text.strip().split()
    
    for part in parts:
        if not validate_activity_format(part):
            logger.debug(f"Skipping invalid activity format: {part}")
            continue
            
        # Extract activity letters (1-2 characters) and number
        match = re.match(r'^([A-Za-z]{1,2})(\d+)$', part)
        if not match:
            continue
            
        activity_letters = match.group(1).upper()
        try:
            value = int(match.group(2))
            if value <= 0:
                logger.debug(f"Skipping non-positive value: {part}")
                continue
            if value > 10000:  # Reasonable upper limit
                logger.warning(f"Large activity value detected: {part}")
            
            # If activity already exists, sum the values
            if activity_letters in activities:
                activities[activity_letters] += value
                logger.debug(f"Summed duplicate activity {activity_letters}: {activities[activity_letters]}")
            else:
                activities[activity_letters] = value
                
        except ValueError as e:
            logger.debug(f"Error parsing activity value in '{part}': {e}")
            continue
    
    return activities

# Helper functions for streak calculation
def update_user_streak(db, user_id):
    """Update user's streak based on their logging pattern."""
    user_id_str = str(user_id)
    today = datetime.now(TIMEZONE).date()
    today_key = f"{today.year}-{today.month}-{today.day}"
    
    user = db["users"][user_id_str]
    last_log_date = user.get("last_log_date")
    
    # Convert last log date string to date object
    if last_log_date:
        last_date = datetime.strptime(last_log_date, "%Y-%m-%d").date()
    else:
        last_date = None
    
    # If this is the user's first log ever
    if not last_date:
        user["current_streak"] = 1
        user["longest_streak"] = max(user.get("longest_streak", 0), 1)
        user["last_log_date"] = today_key
        user["total_logs"] = user.get("total_logs", 0) + 1
        return
    
    # If logging for the same day, don't change streak
    if last_date == today:
        return
    
    # Calculate weekdays between last log and today
    current = last_date + timedelta(days=1)
    missed_weekdays = 0
    
    while current < today:
        if is_weekday(current):
            missed_weekdays += 1
        current += timedelta(days=1)
    
    # If missed any weekdays, reset streak
    if missed_weekdays > 0:
        user["current_streak"] = 1
    else:
        # If today is a weekday, increment streak
        if is_weekday(today):
            user["current_streak"] = user.get("current_streak", 0) + 1
        else:
            # Weekend logs don't break or extend streaks
            pass
    
    # Update longest streak if current is longer
    user["longest_streak"] = max(user.get("longest_streak", 0), user["current_streak"])
    user["last_log_date"] = today_key
    user["total_logs"] = user.get("total_logs", 0) + 1

def check_achievements(db, user_id):
    """Check and award achievements to user."""
    user_id_str = str(user_id)
    user = db["users"][user_id_str]
    achievements = user.get("achievements", [])
    new_achievements = []
    
    # Streak achievements
    streak = user.get("current_streak", 0)
    if streak >= 7 and "streak_7" not in achievements:
        achievements.append("streak_7")
        new_achievements.append("🔥 7-Day Streak Master!")
    
    if streak >= 14 and "streak_14" not in achievements:
        achievements.append("streak_14")
        new_achievements.append("🚀 2-Week Consistency Champion!")
    
    if streak >= 30 and "streak_30" not in achievements:
        achievements.append("streak_30")
        new_achievements.append("👑 30-Day Streak Legend!")
    
    # Total activity achievements
    total_units = sum(user.get("activity_totals", {}).values())
    if total_units >= 100 and "total_100" not in achievements:
        achievements.append("total_100")
        new_achievements.append("💯 Century Club!")
    
    if total_units >= 500 and "total_500" not in achievements:
        achievements.append("total_500")
        new_achievements.append("⭐ 500 Units Superstar!")
    
    if total_units >= 1000 and "total_1000" not in achievements:
        achievements.append("total_1000")
        new_achievements.append("🏆 1000 Units Hall of Fame!")
    
    # Early bird achievement (logging before 9 AM)
    now = datetime.now(TIMEZONE)
    if now.hour < 9 and "early_bird" not in achievements:
        achievements.append("early_bird")
        new_achievements.append("🌅 Early Bird!")
    
    user["achievements"] = achievements
    return new_achievements

def get_quick_stats(db, user_id):
    """Get quick stats for today and this week."""
    user_id_str = str(user_id)
    week_key = get_week_key()
    day_key = get_day_key()
    
    # Today's stats
    today_activities = 0
    today_units = 0
    
    if (week_key in db["weekly_logs"] and 
        user_id_str in db["weekly_logs"][week_key] and
        day_key in db["weekly_logs"][week_key][user_id_str]["logs"]):
        
        daily_log = db["weekly_logs"][week_key][user_id_str]["logs"][day_key]
        today_activities = len(daily_log)
        today_units = sum(daily_log.values())
    
    # Week stats
    week_activities = 0
    week_units = 0
    week_days_logged = 0
    
    if (week_key in db["weekly_logs"] and 
        user_id_str in db["weekly_logs"][week_key]):
        
        week_logs = db["weekly_logs"][week_key][user_id_str]["logs"]
        week_days_logged = len([day for day in week_logs.keys() 
                               if is_weekday(datetime.strptime(day, "%Y-%m-%d"))])
        
        for daily_log in week_logs.values():
            week_activities += len(daily_log)
            week_units += sum(daily_log.values())
    
    return {
        "today_activities": today_activities,
        "today_units": today_units,
        "week_activities": week_activities,
        "week_units": week_units,
        "week_days_logged": week_days_logged
    }

# Log activities for a user
def log_activities(db, user_id, username, activities, message_id=None, chat_id=None):
    """Log activities with comprehensive error handling."""
    try:
        # Allow empty activities (this represents an "empty day" log)
        init_user(db, user_id, username)
        
        week_key = get_week_key()
        day_key = get_day_key()
        user_id_str = str(user_id)
        
        # Get old activities for this day (if any) before updating
        old_activities = db["weekly_logs"][week_key][user_id_str]["logs"].get(day_key, {})
        
        # Check if this is a new log (not an edit)
        is_new_log = day_key not in db["weekly_logs"][week_key][user_id_str]["logs"]
        
        # Store the logs for the day
        db["weekly_logs"][week_key][user_id_str]["logs"][day_key] = activities
        
        # Track the edited message if it's provided
        if message_id and chat_id:
            if user_id_str not in db["edited_logs"]:
                db["edited_logs"][user_id_str] = {}
            
            msg_key = f"{chat_id}:{message_id}"
            db["edited_logs"][user_id_str][msg_key] = {
                "week_key": week_key,
                "day_key": day_key,
                "activities": activities,
                "timestamp": datetime.now(TIMEZONE).isoformat()
            }
        
        # Update user totals - remove old values first
        for activity, value in old_activities.items():
            if activity in db["users"][user_id_str]["activity_totals"]:
                db["users"][user_id_str]["activity_totals"][activity] -= value
                # Prevent negative totals
                if db["users"][user_id_str]["activity_totals"][activity] < 0:
                    logger.warning(f"Negative total for user {user_id}, activity {activity}. Resetting to 0.")
                    db["users"][user_id_str]["activity_totals"][activity] = 0
        
        # Add new values
        for activity, value in activities.items():
            if activity not in db["users"][user_id_str]["activity_totals"]:
                db["users"][user_id_str]["activity_totals"][activity] = 0
            db["users"][user_id_str]["activity_totals"][activity] += value
        
        # Update streak only for new logs (not edits)
        if is_new_log:
            update_user_streak(db, user_id)
        
        # Check for new achievements (including monthly milestones)
        new_achievements = check_all_achievements(db, user_id)
        
        # Save database and return success status along with achievements
        success = save_database(db)
        if success:
            logger.info(f"Successfully logged activities for user {username} ({user_id}): {activities}")
        else:
            logger.error(f"Failed to save database after logging activities for user {user_id}")
        
        return success, new_achievements
        
    except Exception as e:
        logger.error(f"Error logging activities for user {user_id}: {e}")
        return False

# Get weekly summary for a user
def get_user_weekly_summary(db, user_id):
    week_key = get_week_key()
    user_id_str = str(user_id)
    
    if (week_key not in db["weekly_logs"] or 
        user_id_str not in db["weekly_logs"][week_key]):
        return "No logs found for this week."
    
    user_logs = db["weekly_logs"][week_key][user_id_str]["logs"]
    summary = {}
    
    # Calculate totals and find max values for each activity
    for day_key, daily_log in user_logs.items():
        for activity, value in daily_log.items():
            if activity not in summary:
                summary[activity] = {"total": 0, "max": 0, "count": 0}
            
            summary[activity]["total"] += value
            summary[activity]["count"] += 1
            summary[activity]["max"] = max(summary[activity]["max"], value)
    
    # Generate summary text
    summary_text = ""
    for activity, stats in summary.items():
        frequency = f"{stats['count']} day{'s' if stats['count'] != 1 else ''}"
        summary_text += f"{activity}: logged {frequency}, highest {stats['max']}, total {stats['total']}\n"
    
    return summary_text if summary_text else "No activities logged this week."

# Helper function to check if a date is a weekday
def is_weekday(date):
    return date.weekday() < 5  # Monday=0, Friday=4

# Update missed days in the database (weekdays only)
def update_missed_days(db):
    week_key = get_week_key()
    if week_key not in db["weekly_logs"]:
        return
    
    today = datetime.now(TIMEZONE)
    day_of_week = today.weekday()  # 0 (Monday) to 6 (Sunday)
    
    # Don't run on Sunday (when we'll send the weekly report)
    if day_of_week == 6:
        return
    
    # Check only weekdays until yesterday
    yesterday = today - timedelta(days=1)
    
    # Start from the beginning of the week (Monday)
    days_since_monday = day_of_week
    if day_of_week == 0:  # If today is Monday, start from today
        days_since_monday = 0
    start_of_week = today - timedelta(days=days_since_monday)
    
    # Loop through each weekday from Monday to yesterday
    current_day = start_of_week
    while current_day <= yesterday:
        # Only check weekdays
        if is_weekday(current_day):
            check_day_key = f"{current_day.year}-{current_day.month}-{current_day.day}"
            
            # For each user, check if they logged on this day
            for user_id in db["users"]:
                if (user_id in db["weekly_logs"][week_key] and
                    check_day_key not in db["weekly_logs"][week_key][user_id]["logs"] and
                    check_day_key not in db["weekly_logs"][week_key][user_id]["missed_days"]):
                    db["weekly_logs"][week_key][user_id]["missed_days"].append(check_day_key)
        
        current_day += timedelta(days=1)
    
    save_database(db)

# Send private message to user
async def send_private_message(context, user_id, text):
    try:
        await context.bot.send_message(chat_id=user_id, text=text)
        return True
    except Exception as e:
        logger.error(f"Error sending private message to user {user_id}: {e}")
        return False

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Start command called by user {update.effective_user.id} ({update.effective_user.username})")
        await update.message.reply_text(
            "Welcome to the Accountability Challenge Bot! 🚀\n\n"
            "Commands:\n"
            "/log [activities] - Log your daily activities (e.g., /log M20 S30)\n"
            "/status - View your current week's summary\n"
            "/help - Show this help message\n\n"
            "I'll remind you to log your activities and share weekly summaries!"
        )
        logger.info("Start command completed successfully")
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error processing your request.")
        except:
            pass

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Help command called by user {update.effective_user.id} ({update.effective_user.username})")
        
        # Check if user wants specific command help
        if context.args and len(context.args) > 0:
            command = context.args[0].lower()
            await show_command_help(update, command)
            return
        
        # Comprehensive help listing all commands
        help_text = (
            "📚 **Accountability Challenge Bot - Complete Command Guide** 📚\n\n"
            
            "**🎯 CORE COMMANDS**\n"
            "`/log [activities]` - Log daily activities\n"
            "  • `/log M20 S30` - 20 min meditation, 30 min sport\n"
            "  • `/log KK40 P100` - 40 kickboxing, 100 pushups\n"
            "  • `/log` - Empty day (still counts for attendance!)\n\n"
            
            "`/status` - View current week progress\n"
            "  • Shows activities, totals, missed days\n\n"
            
            "`/help [command]` - Show this help or specific command help\n"
            "  • `/help log` - Detailed help for logging\n"
            "  • `/help goals` - Help with goals system\n\n"
            
            "**📊 ANALYTICS & PROGRESS**\n"
            "`/history [weeks]` - View past activity history\n"
            "  • `/history` - Last 4 weeks\n"
            "  • `/history 8` - Last 8 weeks\n\n"
            
            "`/analytics` - Personal insights and trends\n"
            "  • Weekly trends, best days, activity patterns\n\n"
            
            "`/level` - Check your current level and progress\n"
            "  • Shows level score, achievements, next level\n\n"
            
            "`/calendar [month] [year]` - Visual monthly calendar\n"
            "  • `/calendar` - Current month\n"
            "  • `/calendar 12 2024` - December 2024\n\n"
            
            "**🎯 GOALS & CUSTOMIZATION**\n"
            "`/goals [set/remove] [activity] [target]` - Manage weekly goals\n"
            "  • `/goals` - View current goals\n"
            "  • `/goals set M 100` - Set 100 units of M per week\n"
            "  • `/goals remove M` - Remove goal for M\n\n"
            
            "`/define [code] [description]` - Define activity meanings\n"
            "  • `/define` - View all definitions\n"
            "  • `/define M Meditation and mindfulness` - Define M\n\n"
            
            "`/reminder [on/off]` - Toggle daily reminders\n"
            "  • Sends private reminders at 21:00 if not logged\n\n"
            
            "**🔧 POWER FEATURES**\n"
            "`/edit [day] [activities]` - Edit past activities\n"
            "  • `/edit yesterday M30 S20` - Edit yesterday\n"
            "  • `/edit monday P50` - Edit last Monday\n"
            "  • `/edit 3 KK40` - Edit 3 days ago\n\n"
            
            "`/template [save/use/list/delete] [name] [activities]`\n"
            "  • `/template save morning M20 S30` - Save template\n"
            "  • `/template use morning` - Use saved template\n"
            "  • `/template list` - Show all templates\n\n"
            
            "`/export` - Export your personal data\n"
            "  • Summary of all your stats and activity\n\n"
            
            "**💡 MOTIVATION & EXTRAS**\n"
            "`/quote` - Get daily motivation quote\n\n"
            
            "**📅 IMPORTANT RULES**\n"
            "• Only weekdays (Mon-Fri) count for the challenge\n"
            "• Use 1-2 letters + numbers (M20, KK40, etc.)\n"
            "• You can edit previous logs by editing your message\n"
            "• Empty logs (`/log`) count as participation\n\n"
            
            "**⏰ AUTOMATED SCHEDULE**\n"
            "• Sunday 6PM: Weekly celebration with stats\n"
            "• Monday 8AM: New week motivation\n"
            "• Weekdays 9PM: Optional daily reminders\n\n"
            
            "💡 **Tip:** Type `/help [command]` for detailed help on any command!"
        )
        
        await update.message.reply_text(help_text)
        logger.info("Help command completed successfully")
    except Exception as e:
        logger.error(f"Error in help command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error processing your help request.")
        except:
            pass

async def show_command_help(update: Update, command: str):
    """Show detailed help for specific commands."""
    help_texts = {
        "log": (
            "📝 **Detailed Help: /log Command** 📝\n\n"
            "**Purpose:** Log your daily activities\n\n"
            "**Format:** `/log [ActivityCode][Number] [ActivityCode][Number]...`\n\n"
            "**Examples:**\n"
            "• `/log M20` - 20 minutes of meditation\n"
            "• `/log M20 S30 P50` - Multiple activities\n"
            "• `/log KK40 MM15` - Double letter codes\n"
            "• `/log` - Empty day (counts for attendance)\n\n"
            "**Activity Code Rules:**\n"
            "• 1-2 letters followed by a number\n"
            "• Examples: M, S, P, KK, MM, BB\n"
            "• Numbers can be minutes, reps, whatever you prefer\n\n"
            "**Tips:**\n"
            "• Only works on weekdays (Mon-Fri)\n"
            "• You can edit logs by editing your message\n"
            "• Define codes with `/define M Meditation`\n"
            "• Set goals with `/goals set M 100`"
        ),
        "goals": (
            "🎯 **Detailed Help: /goals Command** 🎯\n\n"
            "**Purpose:** Set and track weekly targets\n\n"
            "**Commands:**\n"
            "• `/goals` - View current goals and progress\n"
            "• `/goals set [activity] [target]` - Set weekly goal\n"
            "• `/goals remove [activity]` - Remove a goal\n\n"
            "**Examples:**\n"
            "• `/goals set M 100` - Aim for 100 M units per week\n"
            "• `/goals set KK 200` - 200 KK units weekly\n"
            "• `/goals remove M` - Remove meditation goal\n\n"
            "**Features:**\n"
            "• Shows current progress vs target\n"
            "• Percentage completion display\n"
            "• Color-coded status (✅ achieved, 🔄 in progress, ❌ behind)"
        ),
        "template": (
            "📋 **Detailed Help: /template Command** 📋\n\n"
            "**Purpose:** Save and reuse activity combinations\n\n"
            "**Commands:**\n"
            "• `/template save [name] [activities]` - Save template\n"
            "• `/template use [name]` - Use saved template\n"
            "• `/template list` - Show all templates\n"
            "• `/template delete [name]` - Delete template\n\n"
            "**Examples:**\n"
            "• `/template save morning M20 S30` - Save morning routine\n"
            "• `/template save workout P100 KK40 S20`\n"
            "• `/template use morning` - Log using morning template\n"
            "• `/template delete workout` - Remove workout template\n\n"
            "**Benefits:**\n"
            "• Quick logging of regular routines\n"
            "• Consistent activity combinations\n"
            "• Saves typing time"
        ),
        "edit": (
            "✏️ **Detailed Help: /edit Command** ✏️\n\n"
            "**Purpose:** Edit activities for past days\n\n"
            "**Format:** `/edit [day] [activities]`\n\n"
            "**Day Options:**\n"
            "• `today` - Today (same as /log)\n"
            "• `yesterday` - Previous day\n"
            "• `monday`, `tuesday`, etc. - Specific weekday\n"
            "• `1`, `2`, `3`, etc. - Days ago (max 7)\n\n"
            "**Examples:**\n"
            "• `/edit yesterday M30 S20` - Edit yesterday's log\n"
            "• `/edit monday KK40` - Edit last Monday\n"
            "• `/edit 3 P100` - Edit 3 days ago\n"
            "• `/edit tuesday` - Clear Tuesday's log\n\n"
            "**Limitations:**\n"
            "• Only last 7 days\n"
            "• Only weekdays (Mon-Fri)\n"
            "• Completely replaces existing log for that day"
        ),
        "analytics": (
            "📊 **Detailed Help: /analytics Command** 📊\n\n"
            "**Purpose:** Get personal insights and trends\n\n"
            "**What You'll See:**\n"
            "• Weekly trend analysis (trending up/down/steady)\n"
            "• Most productive day of the week\n"
            "• Activity combinations you often do together\n"
            "• Personal statistics and averages\n"
            "• Current level and progress\n\n"
            "**Examples of Insights:**\n"
            "• \"📈 Trending Up! 25% more units than last week!\"\n"
            "• \"🌟 Most Productive Day: Tuesday (avg 45 units)\"\n"
            "• \"🔗 Activity Combo: You often do M and S together!\"\n\n"
            "**Data Period:**\n"
            "• Analyzes your last 4 weeks of activity\n"
            "• Updates in real-time as you log more"
        )
    }
    
    if command in help_texts:
        await update.message.reply_text(help_texts[command])
    else:
        await update.message.reply_text(
            f"❌ No detailed help available for '{command}'.\n\n"
            "Available detailed help topics:\n"
            "• `/help log` - Logging activities\n"
            "• `/help goals` - Goals system\n"
            "• `/help template` - Templates\n"
            "• `/help edit` - Editing past logs\n"
            "• `/help analytics` - Analytics insights\n\n"
            "Or just use `/help` for the complete command list."
        )

# Motivation quotes system
MOTIVATION_QUOTES = [
    "🌟 Small steps every day lead to big changes every year!",
    "💪 You don't have to be perfect, you just have to be consistent.",
    "🚀 Progress, not perfection, is the goal.",
    "🔥 Every day is a new opportunity to improve yourself.",
    "⭐ The only workout you regret is the one you didn't do.",
    "🌱 Success is the sum of small efforts repeated day in and day out.",
    "💎 Discipline is choosing between what you want now and what you want most.",
    "🎯 You are what you do repeatedly. Excellence is a habit.",
    "🏆 Don't watch the clock; do what it does. Keep going.",
    "🌈 The journey of a thousand miles begins with a single step.",
    "⚡ Your only limit is your mind.",
    "🦋 Change happens when small improvements accumulate.",
    "🔑 Consistency is the key to achieving your goals.",
    "🌟 Believe in yourself and all that you are capable of.",
    "💫 Today's accomplishments were yesterday's impossibilities."
]

def get_motivation_quote():
    """Get a random motivation quote."""
    import random
    return random.choice(MOTIVATION_QUOTES)

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        quote = get_motivation_quote()
        await update.message.reply_text(f"💭 **Daily Motivation** 💭\n\n{quote}")
        logger.info(f"Quote sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in quote command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error getting your motivation quote.")
        except:
            pass

# Backup system functions
def create_backup(db):
    """Create a backup of the database."""
    try:
        timestamp = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.json"
        
        with open(backup_filename, 'w') as f:
            json.dump(db, f, indent=2)
        
        logger.info(f"Backup created: {backup_filename}")
        return backup_filename
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return None

def auto_backup():
    """Perform automatic daily backup."""
    try:
        db = load_database()
        backup_file = create_backup(db)
        
        # Keep only last 7 backups
        import glob
        backups = sorted(glob.glob("backup_*.json"))
        while len(backups) > 7:
            oldest = backups.pop(0)
            os.remove(oldest)
            logger.info(f"Removed old backup: {oldest}")
        
        return backup_file
    except Exception as e:
        logger.error(f"Error in auto backup: {e}")
        return None

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual backup command for admin users."""
    try:
        # Simple admin check - you can enhance this
        user = update.effective_user
        if user.username != "ilo":  # Replace with your admin username
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        db = load_database()
        backup_file = create_backup(db)
        
        if backup_file:
            await update.message.reply_text(f"✅ Backup created: {backup_file}")
        else:
            await update.message.reply_text("❌ Failed to create backup.")
        
        logger.info(f"Manual backup requested by {user.username}")
    except Exception as e:
        logger.error(f"Error in backup command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error creating the backup.")
        except:
            pass

async def log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Log command called by user {update.effective_user.id} ({update.effective_user.username}) with args: {context.args}")
        
        # Check if today is a weekday (Monday=0, Sunday=6)
        today = datetime.now(TIMEZONE)
        if today.weekday() >= 5:  # Saturday=5, Sunday=6
            await update.message.reply_text(
                "🌴 It's the weekend! The accountability challenge only tracks weekdays (Monday-Friday).\n"
                "Enjoy your rest days and see you on Monday! 😊"
            )
            return
        
        # Allow empty logs (no arguments) - this counts as logging an "empty day"
        activities = {}
        if context.args:
            activities_text = " ".join(context.args)
            logger.info(f"Parsing activities: {activities_text}")
            activities = parse_activities(activities_text)
            logger.info(f"Parsed activities: {activities}")
        else:
            logger.info("Empty log command (no arguments) - logging empty day")
        
        logger.info("Loading database...")
        db = load_database()
        logger.info("Database loaded successfully")
        
        user = update.effective_user
        
        # Log the activities with message ID for tracking edits
        logger.info(f"Logging activities for user {user.id}: {activities}")
        result = log_activities(
            db, 
            user.id, 
            user.username or user.first_name, 
            activities,
            update.message.message_id,
            update.effective_chat.id
        )
        
        # Handle both old and new return formats
        if isinstance(result, tuple):
            success, new_achievements = result
        else:
            success = result
            new_achievements = []
        
        logger.info(f"Log activities result: {success}, achievements: {new_achievements}")
        
        if not success:
            logger.error("Failed to log activities")
            await update.message.reply_text(
                "❌ Sorry, there was an error saving your activities. Please try again."
            )
            return
        
        # Get quick stats for response
        quick_stats = get_quick_stats(db, user.id)
        user_data = db["users"][str(user.id)]
        
        # Generate response
        if activities:
            response_text = "✅ Logged successfully:\n"
            for activity, value in activities.items():
                response_text += f"{activity}: {value} units\n"
            
            # Add quick stats
            response_text += f"\n📊 **Quick Stats:**\n"
            response_text += f"Today: {quick_stats['today_activities']} activities, {quick_stats['today_units']} units\n"
            response_text += f"This week: {quick_stats['week_days_logged']}/5 days, {quick_stats['week_units']} total units\n"
            
            # Add streak info
            current_streak = user_data.get("current_streak", 0)
            if current_streak > 1:
                response_text += f"🔥 Current streak: {current_streak} days!\n"
        else:
            response_text = "📝 Empty day logged! Even rest days are part of the journey! 🌱\n"
            response_text += f"\n📊 This week: {quick_stats['week_days_logged']}/5 days logged"
        
        # Add new achievements
        if new_achievements:
            response_text += "\n\n🎉 **NEW ACHIEVEMENTS!** 🎉\n"
            for achievement in new_achievements:
                response_text += f"• {achievement}\n"
        
        logger.info(f"Generated response: {response_text}")
        
        # If in a group chat, send a brief acknowledgment and detailed response in private
        if update.effective_chat.type in ["group", "supergroup"]:
            logger.info("Sending group acknowledgment")
            # Send brief acknowledgment in group
            await update.message.reply_text("✅ Activities logged! Check your private messages for details.")
            
            # Send detailed confirmation in private
            logger.info("Sending private message")
            success = await send_private_message(context, user.id, response_text)
            logger.info(f"Private message result: {success}")
            
            # If private message failed, send full response in the group
            if not success:
                logger.warning("Private message failed, sending full response in group")
                await update.message.reply_text(
                    f"I couldn't send you a private message. Here's your log confirmation:\n\n{response_text}"
                )
        else:
            # If in private chat, just reply directly
            logger.info("Sending direct reply in private chat")
            await update.message.reply_text(response_text)
            
        logger.info("Log command completed successfully")
        
    except Exception as e:
        logger.error(f"Error in log command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error processing your log request. Please try again.")
        except:
            pass

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Status command called by user {update.effective_user.id} ({update.effective_user.username})")
        
        logger.info("Loading database for status command...")
        db = load_database()
        logger.info("Database loaded successfully")
        
        user = update.effective_user
        username = user.username or user.first_name
        logger.info(f"Processing status for user: {username}")
        
        init_user(db, user.id, username)
        logger.info("User initialized")
        
        summary = get_user_weekly_summary(db, user.id)
        logger.info(f"Generated summary: {summary}")
        
        await update.message.reply_text(
            f"📊 Weekly Summary for @{username}:\n\n{summary}"
        )
        logger.info("Status command completed successfully")
        
    except Exception as e:
        logger.error(f"Error in status command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error retrieving your status. Please try again.")
        except:
            pass

async def reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Reminder command called by user {update.effective_user.id} ({update.effective_user.username}) with args: {context.args}")
        
        if not context.args or context.args[0].lower() not in ['on', 'off']:
            await update.message.reply_text(
                "Please specify whether to turn reminders on or off:\n"
                "/reminder on - Enable daily reminders at 21:00\n"
                "/reminder off - Disable daily reminders"
            )
            return
        
        db = load_database()
        user = update.effective_user
        user_id_str = str(user.id)
        
        # Initialize user if needed
        init_user(db, user.id, user.username or user.first_name)
        
        # Update reminder preference
        enable_reminders = context.args[0].lower() == 'on'
        db["users"][user_id_str]["reminders_enabled"] = enable_reminders
        
        save_database(db)
        
        if enable_reminders:
            await update.message.reply_text(
                "✅ Daily reminders enabled! I'll send you a private message at 21:00 each weekday if you haven't logged yet."
            )
        else:
            await update.message.reply_text(
                "🔕 Daily reminders disabled. You can re-enable them anytime with /reminder on"
            )
        
        logger.info(f"Reminder preference updated for user {user.id}: {enable_reminders}")
        
    except Exception as e:
        logger.error(f"Error in reminder command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error updating your reminder preference.")
        except:
            pass

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"History command called by user {update.effective_user.id} ({update.effective_user.username}) with args: {context.args}")
        
        db = load_database()
        user = update.effective_user
        user_id_str = str(user.id)
        
        # Initialize user if needed
        init_user(db, user.id, user.username or user.first_name)
        
        # Determine how many weeks to show (default 4)
        weeks_to_show = 4
        if context.args and context.args[0].isdigit():
            weeks_to_show = min(int(context.args[0]), 12)  # Max 12 weeks
        
        # Get current week and calculate previous weeks
        current_week = get_week_key()
        weeks_to_check = []
        
        # Calculate week keys for the past N weeks
        current_date = datetime.now(TIMEZONE)
        for i in range(weeks_to_show):
            week_date = current_date - timedelta(weeks=i)
            week_key = f"{week_date.year}-W{week_date.strftime('%V')}"
            weeks_to_check.append((week_key, week_date))
        
        history_text = f"📊 **Activity History** ({weeks_to_show} weeks)\n\n"
        
        for week_key, week_date in weeks_to_check:
            week_start = week_date - timedelta(days=week_date.weekday())
            week_end = week_start + timedelta(days=4)  # Friday
            
            history_text += f"**Week {week_date.strftime('%V')}/{week_date.year}** ({week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')})\n"
            
            if week_key in db["weekly_logs"] and user_id_str in db["weekly_logs"][week_key]:
                user_logs = db["weekly_logs"][week_key][user_id_str]["logs"]
                missed_days = db["weekly_logs"][week_key][user_id_str].get("missed_days", [])
                
                # Calculate week stats
                week_units = 0
                week_activities = {}
                days_logged = 0
                
                for day_key, daily_log in user_logs.items():
                    if is_weekday(datetime.strptime(day_key, "%Y-%m-%d")):
                        days_logged += 1
                        for activity, value in daily_log.items():
                            week_units += value
                            if activity not in week_activities:
                                week_activities[activity] = 0
                            week_activities[activity] += value
                
                if week_activities:
                    activities_str = ", ".join([f"{act}:{val}" for act, val in sorted(week_activities.items())])
                    history_text += f"• {days_logged}/5 days, {week_units} total units\n"
                    history_text += f"• Activities: {activities_str}\n"
                else:
                    history_text += "• No activities logged\n"
            else:
                history_text += "• No data available\n"
            
            history_text += "\n"
        
        # Add user statistics
        user_data = db["users"][user_id_str]
        total_units = sum(user_data.get("activity_totals", {}).values())
        current_streak = user_data.get("current_streak", 0)
        longest_streak = user_data.get("longest_streak", 0)
        total_logs = user_data.get("total_logs", 0)
        
        history_text += f"**📈 Overall Stats:**\n"
        history_text += f"• Total logs: {total_logs}\n"
        history_text += f"• Total units: {total_units}\n"
        history_text += f"• Current streak: {current_streak} days\n"
        history_text += f"• Longest streak: {longest_streak} days\n"
        
        # Add achievements
        achievements = user_data.get("achievements", [])
        if achievements:
            history_text += f"\n🏆 **Achievements:** {len(achievements)} earned\n"
        
        await update.message.reply_text(history_text)
        
        logger.info(f"History command completed for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error in history command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error retrieving your history.")
        except:
            pass

async def goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Goals command called by user {update.effective_user.id} ({update.effective_user.username}) with args: {context.args}")
        
        db = load_database()
        user = update.effective_user
        user_id_str = str(user.id)
        
        # Initialize user if needed
        init_user(db, user.id, user.username or user.first_name)
        
        if not context.args:
            # Show current goals
            goals = db["users"][user_id_str].get("goals", {})
            if not goals:
                await update.message.reply_text(
                    "📎 **Weekly Goals**\n\n"
                    "You haven't set any weekly goals yet!\n\n"
                    "Set goals with: `/goals set [Activity] [WeeklyTarget]`\n"
                    "Example: `/goals set M 100` (100 units of M per week)\n\n"
                    "Other commands:\n"
                    "• `/goals` - View current goals\n"
                    "• `/goals set M 100` - Set weekly goal for activity M\n"
                    "• `/goals remove M` - Remove goal for activity M"
                )
            else:
                goals_text = "🎯 **Your Weekly Goals:**\n\n"
                
                # Calculate current week progress
                week_key = get_week_key()
                current_progress = {}
                
                if (week_key in db["weekly_logs"] and 
                    user_id_str in db["weekly_logs"][week_key]):
                    user_logs = db["weekly_logs"][week_key][user_id_str]["logs"]
                    for daily_log in user_logs.values():
                        for activity, value in daily_log.items():
                            if activity not in current_progress:
                                current_progress[activity] = 0
                            current_progress[activity] += value
                
                for activity, target in goals.items():
                    current = current_progress.get(activity, 0)
                    percentage = (current / target * 100) if target > 0 else 0
                    
                    status_emoji = "✅" if current >= target else "🔄" if percentage >= 50 else "❌"
                    goals_text += f"{status_emoji} **{activity}**: {current}/{target} units ({percentage:.0f}%)\n"
                
                goals_text += "\n💡 Use `/goals set [Activity] [Target]` to update goals"
                await update.message.reply_text(goals_text)
            
            return
        
        # Handle goal commands
        command = context.args[0].lower()
        
        if command == "set" and len(context.args) >= 3:
            activity = context.args[1].upper()
            try:
                target = int(context.args[2])
                if target <= 0:
                    await update.message.reply_text("❌ Goal target must be a positive number.")
                    return
                
                if "goals" not in db["users"][user_id_str]:
                    db["users"][user_id_str]["goals"] = {}
                
                db["users"][user_id_str]["goals"][activity] = target
                save_database(db)
                
                await update.message.reply_text(
                    f"🎯 Goal set! You're aiming for **{target} units of {activity}** per week."
                )
                
            except ValueError:
                await update.message.reply_text("❌ Please provide a valid number for the goal target.")
        
        elif command == "remove" and len(context.args) >= 2:
            activity = context.args[1].upper()
            goals = db["users"][user_id_str].get("goals", {})
            
            if activity in goals:
                del goals[activity]
                save_database(db)
                await update.message.reply_text(f"🗑️ Removed weekly goal for activity {activity}.")
            else:
                await update.message.reply_text(f"❌ No goal found for activity {activity}.")
        
        else:
            await update.message.reply_text(
                "❌ Invalid goals command.\n\n"
                "Usage:\n"
                "• `/goals` - View current goals\n"
                "• `/goals set [Activity] [WeeklyTarget]` - Set a weekly goal\n"
                "• `/goals remove [Activity]` - Remove a goal"
            )
        
        logger.info(f"Goals command completed for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error in goals command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error with your goals command.")
        except:
            pass

async def define_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Define command called by user {update.effective_user.id} ({update.effective_user.username}) with args: {context.args}")
        
        db = load_database()
        user = update.effective_user
        user_id_str = str(user.id)
        
        # Initialize user if needed
        init_user(db, user.id, user.username or user.first_name)
        
        if not context.args:
            # Show current definitions
            definitions = db["users"][user_id_str].get("activity_definitions", {})
            if not definitions:
                await update.message.reply_text(
                    "📖 **Activity Definitions**\n\n"
                    "You haven't defined any activity codes yet!\n\n"
                    "Define activities with: `/define [Code] [Description]`\n"
                    "Example: `/define M Meditation` or `/define KK Kickboxing`\n\n"
                    "This helps you remember what each code means!"
                )
            else:
                def_text = "📖 **Your Activity Definitions:**\n\n"
                for code, description in sorted(definitions.items()):
                    def_text += f"**{code}**: {description}\n"
                def_text += "\n💡 Use `/define [Code] [Description]` to add/update definitions"
                await update.message.reply_text(def_text)
            
            return
        
        if len(context.args) >= 2:
            activity_code = context.args[0].upper()
            description = " ".join(context.args[1:])
            
            if "activity_definitions" not in db["users"][user_id_str]:
                db["users"][user_id_str]["activity_definitions"] = {}
            
            db["users"][user_id_str]["activity_definitions"][activity_code] = description
            save_database(db)
            
            await update.message.reply_text(
                f"📝 Definition saved! **{activity_code}** = {description}"
            )
        else:
            await update.message.reply_text(
                "❌ Please provide both an activity code and description.\n\n"
                "Usage: `/define [Code] [Description]`\n"
                "Example: `/define M Meditation and mindfulness practice`"
            )
        
        logger.info(f"Define command completed for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error in define command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error with your define command.")
        except:
            pass

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Edit command called by user {update.effective_user.id} ({update.effective_user.username}) with args: {context.args}")
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "📝 **Bulk Edit Command**\n\n"
                "Edit activities for past days:\n\n"
                "Usage: `/edit [day] [activities]`\n\n"
                "Examples:\n"
                "• `/edit yesterday M20 S30`\n"
                "• `/edit monday KK40`\n"
                "• `/edit 2 P100` (2 days ago)\n"
                "• `/edit today M15` (same as /log)\n\n"
                "**Valid day formats:**\n"
                "• `today`, `yesterday`\n"
                "• `monday`, `tuesday`, `wednesday`, `thursday`, `friday`\n"
                "• Numbers: `1` (yesterday), `2` (day before), etc. (max 7 days)"
            )
            return
        
        db = load_database()
        user = update.effective_user
        user_id_str = str(user.id)
        
        # Initialize user if needed
        init_user(db, user.id, user.username or user.first_name)
        
        # Parse the day argument
        day_arg = context.args[0].lower()
        target_date = None
        today = datetime.now(TIMEZONE).date()
        
        if day_arg == "today":
            target_date = today
        elif day_arg == "yesterday":
            target_date = today - timedelta(days=1)
        elif day_arg.isdigit():
            days_ago = int(day_arg)
            if days_ago > 7:
                await update.message.reply_text("❌ You can only edit activities from the last 7 days.")
                return
            target_date = today - timedelta(days=days_ago)
        elif day_arg in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            # Find the most recent occurrence of this weekday
            weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            target_weekday = weekdays.index(day_arg)
            
            # Calculate days back to reach that weekday
            days_back = (today.weekday() - target_weekday) % 7
            if days_back == 0 and day_arg != ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'][today.weekday()]:
                days_back = 7  # If asking for today's weekday but using name, assume last week
            
            target_date = today - timedelta(days=days_back)
            
            if days_back > 7:
                await update.message.reply_text("❌ You can only edit activities from the last 7 days.")
                return
        
        if not target_date:
            await update.message.reply_text(
                "❌ Invalid day format. Use: today, yesterday, monday-sunday, or number of days ago (1-7)."
            )
            return
        
        # Check if target date is a weekend and we're not allowing weekend logging
        if not is_weekday(target_date) and day_arg != "today":
            await update.message.reply_text(
                "🌴 You can only edit weekday activities (Monday-Friday). "
                "Weekend activities aren't tracked in the accountability challenge."
            )
            return
        
        # Parse activities
        activities_text = " ".join(context.args[1:])
        activities = parse_activities(activities_text)
        
        # Create the day key
        day_key = f"{target_date.year}-{target_date.month}-{target_date.day}"
        week_key = f"{target_date.year}-W{target_date.strftime('%V')}"
        
        # Ensure week structure exists
        if week_key not in db["weekly_logs"]:
            db["weekly_logs"][week_key] = {}
        if user_id_str not in db["weekly_logs"][week_key]:
            db["weekly_logs"][week_key][user_id_str] = {"logs": {}, "missed_days": []}
        
        # Get old activities for this day
        old_activities = db["weekly_logs"][week_key][user_id_str]["logs"].get(day_key, {})
        
        # Update user totals - remove old values first
        for activity, value in old_activities.items():
            if activity in db["users"][user_id_str]["activity_totals"]:
                db["users"][user_id_str]["activity_totals"][activity] -= value
                if db["users"][user_id_str]["activity_totals"][activity] < 0:
                    db["users"][user_id_str]["activity_totals"][activity] = 0
        
        # Add new values
        for activity, value in activities.items():
            if activity not in db["users"][user_id_str]["activity_totals"]:
                db["users"][user_id_str]["activity_totals"][activity] = 0
            db["users"][user_id_str]["activity_totals"][activity] += value
        
        # Update the log
        db["weekly_logs"][week_key][user_id_str]["logs"][day_key] = activities
        
        # Remove from missed days if it was there
        if day_key in db["weekly_logs"][week_key][user_id_str]["missed_days"]:
            db["weekly_logs"][week_key][user_id_str]["missed_days"].remove(day_key)
        
        save_database(db)
        
        # Generate response
        day_name = target_date.strftime("%A")
        if activities:
            response_text = f"✅ **Edited {day_name} ({target_date.strftime('%m/%d')}):**\n"
            for activity, value in activities.items():
                response_text += f"{activity}: {value} units\n"
        else:
            response_text = f"📝 **{day_name} ({target_date.strftime('%m/%d')}) set to empty log**"
        
        await update.message.reply_text(response_text)
        
        logger.info(f"Edit command completed for user {user.id}, date {target_date}")
        
    except Exception as e:
        logger.error(f"Error in edit command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error with your edit command.")
        except:
            pass

async def template_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Template command called by user {update.effective_user.id} ({update.effective_user.username}) with args: {context.args}")
        
        db = load_database()
        user = update.effective_user
        user_id_str = str(user.id)
        
        # Initialize user if needed
        init_user(db, user.id, user.username or user.first_name)
        
        if "templates" not in db["users"][user_id_str]:
            db["users"][user_id_str]["templates"] = {}
        
        if not context.args:
            # Show saved templates
            templates = db["users"][user_id_str]["templates"]
            if not templates:
                await update.message.reply_text(
                    "📋 **Activity Templates**\n\n"
                    "You haven't saved any templates yet!\n\n"
                    "**Commands:**\n"
                    "• `/template save [name] [activities]` - Save a template\n"
                    "• `/template use [name]` - Log using a template\n"
                    "• `/template list` - Show all templates\n"
                    "• `/template delete [name]` - Delete a template\n\n"
                    "**Example:**\n"
                    "`/template save morning M20 S30`\n"
                    "Then later: `/template use morning`"
                )
            else:
                template_text = "📋 **Your Templates:**\n\n"
                for name, activities_str in templates.items():
                    template_text += f"**{name}**: {activities_str}\n"
                template_text += "\n💡 Use `/template use [name]` to log with a template"
                await update.message.reply_text(template_text)
            return
        
        command = context.args[0].lower()
        
        if command == "save" and len(context.args) >= 3:
            template_name = context.args[1].lower()
            activities_text = " ".join(context.args[2:])
            
            # Validate activities
            activities = parse_activities(activities_text)
            if not activities:
                await update.message.reply_text(
                    "❌ Invalid activities format. Please use valid activity codes like M20 S30."
                )
                return
            
            db["users"][user_id_str]["templates"][template_name] = activities_text
            save_database(db)
            
            await update.message.reply_text(
                f"💾 Template **{template_name}** saved: {activities_text}\n\n"
                f"Use it with: `/template use {template_name}`"
            )
        
        elif command == "use" and len(context.args) >= 2:
            template_name = context.args[1].lower()
            templates = db["users"][user_id_str]["templates"]
            
            if template_name not in templates:
                await update.message.reply_text(
                    f"❌ Template **{template_name}** not found.\n\n"
                    "Use `/template list` to see available templates."
                )
                return
            
            # Use the template by logging its activities
            activities_text = templates[template_name]
            activities = parse_activities(activities_text)
            
            # Check if today is a weekday
            today = datetime.now(TIMEZONE)
            if today.weekday() >= 5:
                await update.message.reply_text(
                    "🌴 It's the weekend! Templates can only be used on weekdays."
                )
                return
            
            # Log the activities
            result = log_activities(
                db, user.id, user.username or user.first_name, activities,
                update.message.message_id, update.effective_chat.id
            )
            
            if isinstance(result, tuple):
                success, new_achievements = result
            else:
                success = result
                new_achievements = []
            
            if not success:
                await update.message.reply_text(
                    "❌ Failed to log template activities. Please try again."
                )
                return
            
            # Generate response
            response_text = f"✅ **Template '{template_name}' logged:**\n"
            for activity, value in activities.items():
                response_text += f"{activity}: {value} units\n"
            
            # Add quick stats
            quick_stats = get_quick_stats(db, user.id)
            response_text += f"\n📊 This week: {quick_stats['week_days_logged']}/5 days, {quick_stats['week_units']} total units"
            
            # Add achievements
            if new_achievements:
                response_text += "\n\n🎉 **NEW ACHIEVEMENTS!** 🎉\n"
                for achievement in new_achievements:
                    response_text += f"• {achievement}\n"
            
            await update.message.reply_text(response_text)
        
        elif command == "list":
            templates = db["users"][user_id_str]["templates"]
            if not templates:
                await update.message.reply_text("📋 No templates saved yet.")
            else:
                template_text = "📋 **Your Templates:**\n\n"
                for name, activities_str in templates.items():
                    template_text += f"**{name}**: {activities_str}\n"
                await update.message.reply_text(template_text)
        
        elif command == "delete" and len(context.args) >= 2:
            template_name = context.args[1].lower()
            templates = db["users"][user_id_str]["templates"]
            
            if template_name in templates:
                del templates[template_name]
                save_database(db)
                await update.message.reply_text(f"🗑️ Template **{template_name}** deleted.")
            else:
                await update.message.reply_text(f"❌ Template **{template_name}** not found.")
        
        else:
            await update.message.reply_text(
                "❌ Invalid template command.\n\n"
                "**Usage:**\n"
                "• `/template save [name] [activities]` - Save template\n"
                "• `/template use [name]` - Use template\n"
                "• `/template list` - List templates\n"
                "• `/template delete [name]` - Delete template"
            )
        
        logger.info(f"Template command completed for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error in template command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error with your template command.")
        except:
            pass

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            await update.message.reply_text(
                "Hello everyone! I'm your Accountability Challenge Bot! 👋\n\n"
                "Use `/log` followed by your activities to log your daily progress.\n"
                "For example: `/log M20 S30` (where M=Meditation, S=Sport, followed by minutes/units).\n\n"
                "I'll track your progress and share weekly summaries every Sunday!"
            )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.lower() if update.message.text else ""
    
    # Check for common patterns and provide helpful guidance
    if "log" in message_text:
        await update.message.reply_text(
            "It looks like you're trying to log your activities! Please use the `/log` command instead.\n"
            "For example: `/log M20 S30` for 20 minutes of meditation and 30 minutes of sport.\n\n"
            "Type `/help log` for detailed logging instructions."
        )
    elif any(word in message_text for word in ["help", "how", "command", "what", "?"]):
        await update.message.reply_text(
            "🤔 Need help? I'm here to guide you!\n\n"
            "Type `/help` to see all available commands with examples.\n\n"
            "For specific help on any command, use `/help [command]`\n"
            "For example: `/help log` or `/help goals`"
        )
    elif any(word in message_text for word in ["status", "progress", "week", "summary"]):
        await update.message.reply_text(
            "📊 Want to see your progress? Use `/status` to view your current week summary!\n\n"
            "You can also try:\n"
            "• `/history` - View past weeks\n"
            "• `/analytics` - Get personal insights\n"
            "• `/level` - Check your level and achievements\n\n"
            "Type `/help` for all commands."
        )
    elif update.effective_chat.type == "private":
        # Only respond with general guidance in private chats to avoid spam in groups
        await update.message.reply_text(
            "👋 Hi there! I'm your Accountability Challenge Bot.\n\n"
            "I help you track daily activities and build consistent habits!\n\n"
            "🚀 **Get started:**\n"
            "• Type `/help` to see all available commands\n"
            "• Use `/log M20 S30` to log activities\n"
            "• Try `/status` to see your progress\n\n"
            "Need detailed help? Use `/help [command]` for any specific command!"
        )
    
    # Update group chat information
    db = load_database()
    chat = update.effective_chat
    
    if chat.type in ["group", "supergroup"]:
        if "group_chats" not in db:
            db["group_chats"] = {}
        
        db["group_chats"][str(chat.id)] = {
            "chat_name": chat.title,
            "last_activity": datetime.now(TIMEZONE).isoformat()
        }
        
        save_database(db)

# Handle edited messages - especially for /log commands
async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if it's a command edit
    if not update.edited_message or not update.edited_message.text:
        return
    
    message_text = update.edited_message.text
    user = update.effective_user
    
    # Process only edited /log commands
    if message_text.startswith('/log'):
        # Parse the command arguments
        args = message_text.split(' ')[1:]
        activities = parse_activities(" ".join(args))
        
        if not activities:
            # Try to send privately first
            success = await send_private_message(
                context,
                user.id,
                "I couldn't parse any activities from your edited message. Please use the format:\n"
                "/log [Letter][Number] [Letter][Number] ...\n"
                "For example: /log M20 S30 (M=Meditation 20 minutes, S=Sport 30 minutes)"
            )
            
            # If private message failed, reply in the same chat
            if not success and update.effective_chat.type in ["group", "supergroup"]:
                await update.edited_message.reply_text(
                    "I couldn't parse your edited log. Please check the format and try again."
                )
            return
        
        db = load_database()
        
        # Update the log with the edited information
        success = log_activities(
            db, 
            user.id, 
            user.username or user.first_name, 
            activities,
            update.edited_message.message_id,
            update.effective_chat.id
        )
        
        if not success:
            await send_private_message(
                context, 
                user.id, 
                "❌ Sorry, there was an error updating your activities. Please try again."
            )
            return
        
        # Generate response
        response_text = "✅ Updated log successfully:\n"
        for activity, value in activities.items():
            response_text += f"{activity}: {value} units\n"
        
        # Try to send the confirmation privately
        success = await send_private_message(context, user.id, response_text)
        
        # If in a group chat and private message was successful, send brief acknowledgment
        if update.effective_chat.type in ["group", "supergroup"] and success:
            await update.edited_message.reply_text("✅ Your edited log has been updated! Check your private messages for details.")
        
        # If private message failed and in group chat, send a brief note
        elif update.effective_chat.type in ["group", "supergroup"] and not success:
            await update.edited_message.reply_text(
                f"✅ Updated log. I couldn't send you a private message with the details."
            )
        
        # In private chat, just reply with full info if private message failed
        elif not success:
            await update.edited_message.reply_text(response_text)

# Helper function to get weekly stats
def get_weekly_stats(db, week_key):
    """Get comprehensive weekly statistics for all users."""
    stats = {
        "users": {},
        "activity_totals": {},
        "leader": None,
        "max_units": 0,
        "perfect_attendance": []
    }
    
    if week_key not in db["weekly_logs"]:
        return stats
    
    # Calculate stats for each user
    for user_id, user_week_data in db["weekly_logs"][week_key].items():
        if user_id not in db["users"]:
            continue
            
        username = db["users"][user_id]["username"]
        user_logs = user_week_data["logs"]
        missed_days = user_week_data.get("missed_days", [])
        
        # Count weekdays logged vs total weekdays (5)
        weekdays_logged = len([day for day in user_logs.keys() 
                              if is_weekday(datetime.strptime(day, "%Y-%m-%d"))])
        
        # Calculate user's total units
        user_total_units = 0
        user_activities = {}
        
        for day_key, daily_log in user_logs.items():
            for activity, value in daily_log.items():
                user_total_units += value
                if activity not in user_activities:
                    user_activities[activity] = 0
                user_activities[activity] += value
                
                # Add to global activity totals
                if activity not in stats["activity_totals"]:
                    stats["activity_totals"][activity] = 0
                stats["activity_totals"][activity] += value
        
        # Check for perfect attendance (logged all 5 weekdays)
        if weekdays_logged == 5 and len(missed_days) == 0:
            stats["perfect_attendance"].append(username)
        
        # Check if this user is the leader
        if user_total_units > stats["max_units"]:
            stats["max_units"] = user_total_units
            stats["leader"] = username
        
        stats["users"][user_id] = {
            "username": username,
            "total_units": user_total_units,
            "activities": user_activities,
            "weekdays_logged": weekdays_logged,
            "missed_days": missed_days,
            "logs": user_logs
        }
    
    return stats

# Helper function to format daily breakdown for a user
def format_daily_breakdown(user_logs):
    """Format daily breakdown in 'Monday: K50 L100 M15' format."""
    breakdown = []
    
    # Sort days chronologically
    sorted_days = sorted(user_logs.keys(), key=lambda x: datetime.strptime(x, "%Y-%m-%d"))
    
    for day_key in sorted_days:
        date_obj = datetime.strptime(day_key, "%Y-%m-%d")
        # Only include weekdays
        if not is_weekday(date_obj):
            continue
            
        day_name = date_obj.strftime("%A")
        daily_activities = user_logs[day_key]
        
        if daily_activities:
            # Sort activities alphabetically
            sorted_activities = sorted(daily_activities.items())
            activity_str = " ".join([f"{act}{val}" for act, val in sorted_activities])
            breakdown.append(f"{day_name}: {activity_str}")
        else:
            breakdown.append(f"{day_name}: (empty log)")
    
    return "\n".join(breakdown)

# Send individual weekly breakdown to each user
async def send_individual_breakdowns(context: ContextTypes.DEFAULT_TYPE, db, week_key, stats):
    """Send private weekly breakdown to each participating user."""
    for user_id, user_stats in stats["users"].items():
        try:
            breakdown_text = f"📊 **Your Weekly Breakdown** 📊\n\n"
            
            # Total activities summary
            if user_stats["activities"]:
                breakdown_text += "**Activity Totals:**\n"
                for activity, total in sorted(user_stats["activities"].items()):
                    breakdown_text += f"{activity}: {total} total units\n"
                breakdown_text += "\n"
            
            # Daily breakdown
            breakdown_text += "**Daily Log:**\n"
            daily_breakdown = format_daily_breakdown(user_stats["logs"])
            if daily_breakdown:
                breakdown_text += daily_breakdown
            else:
                breakdown_text += "No activities logged this week."
            
            breakdown_text += "\n\n"
            
            # Attendance summary
            breakdown_text += f"**Attendance:** {user_stats['weekdays_logged']}/5 weekdays\n"
            
            if user_stats["username"] in stats["perfect_attendance"]:
                breakdown_text += "🌟 **Perfect attendance this week!** 🌟\n"
            elif user_stats["missed_days"]:
                breakdown_text += f"Missed: {len(user_stats['missed_days'])} day(s)\n"
            
            # Motivational message
            if user_stats["total_units"] > 0:
                breakdown_text += f"\n💪 Total impact this week: **{user_stats['total_units']} units**!\n"
                breakdown_text += "Keep up the amazing work! 🚀"
            else:
                breakdown_text += "\n🌱 Every journey starts with a single step. Next week is a new opportunity!"
            
            await send_private_message(context, int(user_id), breakdown_text)
            
        except Exception as e:
            logger.error(f"Error sending individual breakdown to user {user_id}: {e}")

# Scheduled job for Sunday celebration message (18:00)
async def send_sunday_celebration(context: ContextTypes.DEFAULT_TYPE):
    db = load_database()
    week_key = get_week_key()
    
    # Get comprehensive weekly stats
    stats = get_weekly_stats(db, week_key)
    
    active_groups = db.get("group_chats", {}).keys()
    
    for chat_id_str in active_groups:
        celebration_message = "🎉 **WEEKLY ACCOUNTABILITY CELEBRATION** 🎉\n\n"
        
        if not stats["users"]:
            celebration_message += "No activity logged this week. Let's make next week count! 💪"
        else:
            # 1. Leader announcement
            if stats["leader"] and stats["max_units"] > 0:
                celebration_message += f"👑 **CHALLENGE LEADER:** @{stats['leader']} with {stats['max_units']} total units! 👑\n\n"
            
            # 2. Total units by activity type
            if stats["activity_totals"]:
                celebration_message += "📈 **Group Totals This Week:**\n"
                for activity, total in sorted(stats["activity_totals"].items()):
                    celebration_message += f"{activity}: {total} total units\n"
                celebration_message += "\n"
            
            # 3. Perfect attendance congratulations
            if stats["perfect_attendance"]:
                celebration_message += "🌟 **PERFECT ATTENDANCE HEROES** 🌟\n"
                celebration_message += "These champions logged every weekday:\n"
                for username in stats["perfect_attendance"]:
                    celebration_message += f"🎯 @{username}\n"
                celebration_message += "\n"
            
            # 4. Friendly encouragement for missed days
            missed_users = []
            for user_stats in stats["users"].values():
                if user_stats["weekdays_logged"] < 5:
                    missed_users.append(user_stats["username"])
            
            if missed_users:
                celebration_message += "💪 **Friendly Nudge** 💪\n"
                celebration_message += "Let's support these folks for even more consistency next week:\n"
                for username in missed_users:
                    celebration_message += f"🤝 @{username}\n"
                celebration_message += "\n"
            
            celebration_message += "🚀 **Great work this week, everyone! Let's keep the momentum going!** 🚀"
        
        try:
            await context.bot.send_message(chat_id=int(chat_id_str), text=celebration_message)
        except Exception as e:
            logger.error(f"Error sending celebration message to chat {chat_id_str}: {e}")
    
    # Send individual breakdowns to all participating users
    await send_individual_breakdowns(context, db, week_key, stats)

# Scheduled job for Monday reminder (08:00)
async def send_monday_reminder(context: ContextTypes.DEFAULT_TYPE):
    db = load_database()
    active_groups = db.get("group_chats", {}).keys()
    
    for chat_id_str in active_groups:
        try:
            await context.bot.send_message(
                chat_id=int(chat_id_str),
                text="🌅 Good morning, accountability champions! A new week begins today!\n\n"
                     "Remember to log your daily activities with `/log`\n"
                     "For example: `/log M20 S30`\n\n"
                     "Let's make it a great week! 💪"
            )
        except Exception as e:
            logger.error(f"Error sending Monday reminder to chat {chat_id_str}: {e}")

# Scheduled job for daily reminder (21:00) - Send private reminders to users who haven't logged
async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    db = load_database()
    week_key = get_week_key()
    day_key = get_day_key()
    
    # Check if today is a weekday
    today = datetime.now(TIMEZONE)
    if not is_weekday(today):
        return  # Don't send reminders on weekends
    
    # Update missed days
    update_missed_days(db)
    
    # Send private reminders to users who haven't logged today and have reminders enabled
    for user_id, user_data in db["users"].items():
        # Check if user has reminders enabled (default to True for existing users)
        reminders_enabled = user_data.get("reminders_enabled", True)
        
        if not reminders_enabled:
            continue
        
        # Check if user hasn't logged today
        has_logged_today = (
            week_key in db["weekly_logs"] and
            user_id in db["weekly_logs"][week_key] and
            day_key in db["weekly_logs"][week_key][user_id]["logs"]
        )
        
        if not has_logged_today:
            reminder_text = (
                "⏰ **Daily Reminder** ⏰\n\n"
                "You haven't logged your activities today yet! 📝\n\n"
                "Use /log to track your progress, or /log with no activities to log an empty day.\n\n"
                "Examples:\n"
                "• /log M20 S30 (Meditation 20, Sport 30)\n"
                "• /log (empty day log)\n\n"
                "_To disable these reminders, use /reminder off_"
            )
            
            try:
                await send_private_message(context, int(user_id), reminder_text)
                logger.info(f"Sent daily reminder to user {user_id} ({user_data['username']})")
            except Exception as e:
                logger.error(f"Error sending daily reminder to user {user_id}: {e}")

async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Analytics command called by user {update.effective_user.id} ({update.effective_user.username})")
        
        db = load_database()
        user = update.effective_user
        user_id_str = str(user.id)
        
        # Initialize user if needed
        init_user(db, user.id, user.username or user.first_name)
        
        # Get user data
        user_data = db["users"][user_id_str]
        
        # Analyze last 4 weeks
        analytics_text = "📊 **Personal Analytics** 📊\n\n"
        
        # Get weekly data for trend analysis
        current_date = datetime.now(TIMEZONE)
        weeks_data = []
        
        for i in range(4):  # Last 4 weeks
            week_date = current_date - timedelta(weeks=i)
            week_key = f"{week_date.year}-W{week_date.strftime('%V')}"
            
            week_units = 0
            week_activities = {}
            week_days = 0
            
            if week_key in db["weekly_logs"] and user_id_str in db["weekly_logs"][week_key]:
                user_logs = db["weekly_logs"][week_key][user_id_str]["logs"]
                for day_key, daily_log in user_logs.items():
                    if is_weekday(datetime.strptime(day_key, "%Y-%m-%d")):
                        week_days += 1
                        for activity, value in daily_log.items():
                            week_units += value
                            week_activities[activity] = week_activities.get(activity, 0) + value
            
            weeks_data.append({
                "week": i,
                "units": week_units,
                "days": week_days,
                "activities": week_activities
            })
        
        # Weekly trend analysis
        if len(weeks_data) >= 2:
            current_week = weeks_data[0]["units"]
            last_week = weeks_data[1]["units"]
            
            if last_week > 0:
                change_percent = ((current_week - last_week) / last_week) * 100
                if change_percent > 5:
                    analytics_text += f"📈 **Trending Up!** {change_percent:.0f}% more units than last week!\n"
                elif change_percent < -5:
                    analytics_text += f"📉 **Trending Down:** {abs(change_percent):.0f}% fewer units than last week.\n"
                else:
                    analytics_text += f"➡️ **Steady:** Similar activity level to last week.\n"
            else:
                analytics_text += f"🆕 **Getting Started:** First week with logged activities!\n"
            
            analytics_text += "\n"
        
        # Best day analysis
        daily_totals = {}
        activity_pairs = {}
        for week_data in weeks_data:
            week_date = current_date - timedelta(weeks=week_data["week"])
            week_key = f"{week_date.year}-W{week_date.strftime('%V')}"
            
            if week_key in db["weekly_logs"] and user_id_str in db["weekly_logs"][week_key]:
                user_logs = db["weekly_logs"][week_key][user_id_str]["logs"]
                for day_key, daily_log in user_logs.items():
                    day_date = datetime.strptime(day_key, "%Y-%m-%d")
                    if is_weekday(day_date):
                        day_name = day_date.strftime("%A")
                        if day_name not in daily_totals:
                            daily_totals[day_name] = []
                        daily_totals[day_name].append(sum(daily_log.values()))
                        
                        # Track activity correlations
                        activities = list(daily_log.keys())
                        for i, act1 in enumerate(activities):
                            for act2 in activities[i+1:]:
                                pair = tuple(sorted([act1, act2]))
                                activity_pairs[pair] = activity_pairs.get(pair, 0) + 1
        
        if daily_totals:
            avg_by_day = {day: sum(values)/len(values) for day, values in daily_totals.items()}
            best_day = max(avg_by_day, key=avg_by_day.get)
            analytics_text += f"🌟 **Most Productive Day:** {best_day} (avg {avg_by_day[best_day]:.0f} units)\n\n"
        
        # Activity correlation analysis
        if activity_pairs:
            most_common_pair = max(activity_pairs, key=activity_pairs.get)
            if activity_pairs[most_common_pair] >= 3:
                analytics_text += f"🔗 **Activity Combo:** You often do {most_common_pair[0]} and {most_common_pair[1]} together! ({activity_pairs[most_common_pair]} times)\n\n"
        
        # Personal statistics
        total_units = sum(user_data.get("activity_totals", {}).values())
        current_streak = user_data.get("current_streak", 0)
        total_logs = user_data.get("total_logs", 0)
        
        if total_logs > 0:
            avg_units_per_log = total_units / total_logs
            analytics_text += f"**📋 Personal Stats:**\n"
            analytics_text += f"• Average units per day: {avg_units_per_log:.1f}\n"
            analytics_text += f"• Current streak: {current_streak} days\n"
            analytics_text += f"• Total logs: {total_logs}\n"
            analytics_text += f"• Total impact: {total_units} units\n"
        
        # Level calculation
        level = calculate_user_level(user_data)
        analytics_text += f"• Current level: **{level}** 🏆\n"
        
        await update.message.reply_text(analytics_text)
        
        logger.info(f"Analytics command completed for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error in analytics command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error generating your analytics.")
        except:
            pass

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Export command called by user {update.effective_user.id} ({update.effective_user.username})")
        
        db = load_database()
        user = update.effective_user
        user_id_str = str(user.id)
        
        # Initialize user if needed
        init_user(db, user.id, user.username or user.first_name)
        
        # Generate CSV-style data summary
        export_text = f"📊 **Data Export for {user.username or user.first_name}** 📊\n\n"
        
        # User summary
        user_data = db["users"][user_id_str]
        total_units = sum(user_data.get("activity_totals", {}).values())
        
        export_text += f"**Summary:**\n"
        export_text += f"• Total logs: {user_data.get('total_logs', 0)}\n"
        export_text += f"• Current streak: {user_data.get('current_streak', 0)} days\n"
        export_text += f"• Longest streak: {user_data.get('longest_streak', 0)} days\n"
        export_text += f"• Total units: {total_units}\n\n"
        
        # Activity totals
        if user_data.get('activity_totals'):
            export_text += f"**Activity Totals:**\n"
            for activity, total in sorted(user_data['activity_totals'].items()):
                export_text += f"• {activity}: {total} units\n"
            export_text += "\n"
        
        # Goals
        if user_data.get('goals'):
            export_text += f"**Current Goals:**\n"
            for activity, target in user_data['goals'].items():
                export_text += f"• {activity}: {target} units/week\n"
            export_text += "\n"
        
        # Achievements
        if user_data.get('achievements'):
            export_text += f"**Achievements:** {len(user_data['achievements'])} earned\n"
            export_text += "\n"
        
        # Recent activity (last 2 weeks)
        export_text += f"**Recent Activity (Last 2 Weeks):**\n"
        current_date = datetime.now(TIMEZONE)
        found_recent = False
        
        for i in range(2):
            week_date = current_date - timedelta(weeks=i)
            week_key = f"{week_date.year}-W{week_date.strftime('%V')}"
            
            if week_key in db["weekly_logs"] and user_id_str in db["weekly_logs"][week_key]:
                user_logs = db["weekly_logs"][week_key][user_id_str]["logs"]
                if user_logs:
                    found_recent = True
                    week_total = sum(sum(daily_log.values()) for daily_log in user_logs.values())
                    export_text += f"Week {week_date.strftime('%V')}/{week_date.year}: {week_total} units, {len(user_logs)} days\n"
        
        if not found_recent:
            export_text += "No recent activity data.\n"
        
        export_text += f"\nExport generated: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')}\n"
        export_text += "\n💾 For full CSV data export, contact the bot administrator."
        
        await update.message.reply_text(export_text)
        
        # Log the export request
        logger.info(f"Data export requested by user {user.id} ({user.username or user.first_name})")
        
    except Exception as e:
        logger.error(f"Error in export command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error generating your data export.")
        except:
            pass

def calculate_user_level(user_data):
    """Calculate user level based on total activity and consistency."""
    total_units = sum(user_data.get("activity_totals", {}).values())
    longest_streak = user_data.get("longest_streak", 0)
    total_logs = user_data.get("total_logs", 0)
    achievements = len(user_data.get("achievements", []))
    
    # Level calculation formula
    level_score = (total_units * 0.5) + (longest_streak * 10) + (total_logs * 2) + (achievements * 15)
    
    if level_score < 50:
        return "Beginner 🌱"
    elif level_score < 150:
        return "Explorer 🚀"
    elif level_score < 300:
        return "Achiever ⭐"
    elif level_score < 500:
        return "Champion 🏆"
    elif level_score < 750:
        return "Master 👑"
    else:
        return "Legend 🌟"

async def level_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Level command called by user {update.effective_user.id} ({update.effective_user.username})")
        
        db = load_database()
        user = update.effective_user
        user_id_str = str(user.id)
        
        # Initialize user if needed
        init_user(db, user.id, user.username or user.first_name)
        
        user_data = db["users"][user_id_str]
        current_level = calculate_user_level(user_data)
        
        # Calculate level components
        total_units = sum(user_data.get("activity_totals", {}).values())
        longest_streak = user_data.get("longest_streak", 0)
        total_logs = user_data.get("total_logs", 0)
        achievements = len(user_data.get("achievements", []))
        
        level_score = (total_units * 0.5) + (longest_streak * 10) + (total_logs * 2) + (achievements * 15)
        
        level_text = f"🏆 **Your Level: {current_level}** 🏆\n\n"
        level_text += f"**Level Score: {level_score:.0f} points**\n\n"
        
        level_text += f"**Components:**\n"
        level_text += f"• Total Units: {total_units} ({total_units * 0.5:.0f} pts)\n"
        level_text += f"• Longest Streak: {longest_streak} days ({longest_streak * 10:.0f} pts)\n"
        level_text += f"• Total Logs: {total_logs} ({total_logs * 2:.0f} pts)\n"
        level_text += f"• Achievements: {achievements} ({achievements * 15:.0f} pts)\n\n"
        
        # Next level requirements
        next_level_thresholds = [50, 150, 300, 500, 750, 1000]
        current_threshold = 0
        next_threshold = None
        
        for threshold in next_level_thresholds:
            if level_score >= threshold:
                current_threshold = threshold
            else:
                next_threshold = threshold
                break
        
        if next_threshold:
            points_needed = next_threshold - level_score
            level_text += f"**Next Level:** {points_needed:.0f} more points needed\n"
            progress = ((level_score - current_threshold) / (next_threshold - current_threshold) * 100)
            level_text += f"Progress: {progress:.0f}% to next level"
        else:
            level_text += f"**🌟 You've reached the maximum level! 🌟**"
        
        await update.message.reply_text(level_text)
        
        logger.info(f"Level command completed for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error in level command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error checking your level.")
        except:
            pass

# Enhanced input validation
def validate_activity_input(text, max_value=10000):
    """Enhanced validation for activity input with detailed feedback."""
    if not text:
        return True, {}  # Empty is valid
    
    issues = []
    valid_activities = {}
    
    parts = text.strip().split()
    for part in parts:
        if not validate_activity_format(part):
            if re.match(r'^[A-Za-z]+$', part):
                issues.append(f"'{part}' - missing number (try {part}20)")
            elif re.match(r'^\d+$', part):
                issues.append(f"'{part}' - missing activity letter (try M{part})")
            elif len(part) > 10:
                issues.append(f"'{part}' - too long (max 10 characters)")
            else:
                issues.append(f"'{part}' - invalid format (use letter(s) + number)")
            continue
        
        match = re.match(r'^([A-Za-z]{1,2})(\d+)$', part)
        if match:
            activity = match.group(1).upper()
            try:
                value = int(match.group(2))
                if value <= 0:
                    issues.append(f"'{part}' - value must be positive")
                elif value > max_value:
                    issues.append(f"'{part}' - value too large (max {max_value})")
                else:
                    valid_activities[activity] = valid_activities.get(activity, 0) + value
            except ValueError:
                issues.append(f"'{part}' - invalid number")
    
    return len(issues) == 0, valid_activities if len(issues) == 0 else issues

async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show calendar view of logging activity."""
    try:
        logger.info(f"Calendar command called by user {update.effective_user.id} ({update.effective_user.username})")
        
        db = load_database()
        user = update.effective_user
        user_id_str = str(user.id)
        
        # Initialize user if needed
        init_user(db, user.id, user.username or user.first_name)
        
        # Determine month to show (default current month)
        current_date = datetime.now(TIMEZONE)
        target_month = current_date.month
        target_year = current_date.year
        
        if context.args and len(context.args) >= 1:
            try:
                if len(context.args) == 1:
                    target_month = int(context.args[0])
                elif len(context.args) == 2:
                    target_month = int(context.args[0])
                    target_year = int(context.args[1])
            except ValueError:
                await update.message.reply_text("❌ Invalid month/year. Use: `/calendar` or `/calendar 12` or `/calendar 12 2024`")
                return
        
        if not (1 <= target_month <= 12):
            await update.message.reply_text("❌ Month must be between 1-12")
            return
        
        # Generate calendar
        import calendar as cal
        cal_text = f"📅 **Activity Calendar - {cal.month_name[target_month]} {target_year}** 📅\n\n"
        
        # Get month calendar
        month_cal = cal.monthcalendar(target_year, target_month)
        
        # Headers
        cal_text += "Mo Tu We Th Fr Sa Su\n"
        cal_text += "─" * 21 + "\n"
        
        # Get user's logs for this month
        user_logs_this_month = {}
        for week_key, week_data in db["weekly_logs"].items():
            if user_id_str in week_data:
                for day_key, daily_log in week_data[user_id_str]["logs"].items():
                    try:
                        log_date = datetime.strptime(day_key, "%Y-%m-%d")
                        if log_date.year == target_year and log_date.month == target_month:
                            total_units = sum(daily_log.values()) if daily_log else 0
                            user_logs_this_month[log_date.day] = total_units
                    except:
                        continue
        
        # Build calendar grid
        for week in month_cal:
            week_line = ""
            for day in week:
                if day == 0:
                    week_line += "   "  # Empty day
                else:
                    # Check if this day has logs
                    if day in user_logs_this_month:
                        units = user_logs_this_month[day]
                        if units > 0:
                            week_line += f"{day:2d}●"  # Day with activities
                        else:
                            week_line += f"{day:2d}○"  # Empty log
                    else:
                        # Check if it's a weekday and in the past
                        day_date = datetime(target_year, target_month, day)
                        if is_weekday(day_date) and day_date.date() < current_date.date():
                            week_line += f"{day:2d}✗"  # Missed weekday
                        else:
                            week_line += f"{day:2d} "  # No data/future/weekend
            cal_text += week_line + "\n"
        
        cal_text += "\n**Legend:**\n"
        cal_text += "● = Activities logged\n"
        cal_text += "○ = Empty day logged\n"
        cal_text += "✗ = Missed weekday\n"
        cal_text += "  = Weekend/future/no data\n\n"
        
        # Monthly stats
        logged_days = len([d for d in user_logs_this_month.keys() if user_logs_this_month[d] >= 0])
        total_units = sum(user_logs_this_month.values())
        
        cal_text += f"**Monthly Stats:**\n"
        cal_text += f"• Days logged: {logged_days}\n"
        cal_text += f"• Total units: {total_units}\n"
        
        # Calculate weekdays in month for completion percentage
        weekdays_in_month = sum(1 for week in month_cal for day in week 
                               if day > 0 and is_weekday(datetime(target_year, target_month, day)))
        if weekdays_in_month > 0:
            completion = (logged_days / weekdays_in_month) * 100
            cal_text += f"• Completion: {completion:.0f}%\n"
        
        await update.message.reply_text(cal_text)
        
        logger.info(f"Calendar command completed for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error in calendar command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Sorry, there was an error generating your calendar.")
        except:
            pass

# Monthly milestone checking
def check_monthly_milestones(db, user_id):
    """Check and award monthly milestones."""
    user_id_str = str(user_id)
    user = db["users"][user_id_str]
    achievements = user.get("achievements", [])
    new_achievements = []
    
    current_date = datetime.now(TIMEZONE)
    current_month = current_date.strftime("%Y-%m")
    
    # Calculate this month's stats
    month_units = 0
    month_days = 0
    month_activities = set()
    
    for week_key, week_data in db["weekly_logs"].items():
        if user_id_str in week_data:
            for day_key, daily_log in week_data[user_id_str]["logs"].items():
                try:
                    log_date = datetime.strptime(day_key, "%Y-%m-%d")
                    if log_date.strftime("%Y-%m") == current_month:
                        month_days += 1
                        for activity, value in daily_log.items():
                            month_units += value
                            month_activities.add(activity)
                except:
                    continue
    
    # Monthly achievements
    milestone_key = f"monthly_{current_month}"
    
    # First month milestone
    if month_days >= 5 and f"first_month" not in achievements:
        achievements.append("first_month")
        new_achievements.append("🎊 First Month Warrior!")
    
    # Monthly consistency (20+ days)
    if month_days >= 20 and milestone_key + "_consistent" not in achievements:
        achievements.append(milestone_key + "_consistent")
        new_achievements.append("📅 Monthly Consistency Champion!")
    
    # Monthly variety (5+ different activities)
    if len(month_activities) >= 5 and milestone_key + "_variety" not in achievements:
        achievements.append(milestone_key + "_variety")
        new_achievements.append("🌈 Activity Variety Master!")
    
    # Monthly powerhouse (1000+ units)
    if month_units >= 1000 and milestone_key + "_powerhouse" not in achievements:
        achievements.append(milestone_key + "_powerhouse")
        new_achievements.append("⚡ Monthly Powerhouse!")
    
    user["achievements"] = achievements
    return new_achievements

# Enhanced achievement checking that includes monthly milestones
def check_all_achievements(db, user_id):
    """Check both regular and monthly achievements."""
    regular_achievements = check_achievements(db, user_id)
    monthly_achievements = check_monthly_milestones(db, user_id)
    return regular_achievements + monthly_achievements

def main():
    # Create the Application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("log", log_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("reminder", reminder_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("goals", goals_command))
    application.add_handler(CommandHandler("define", define_command))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("template", template_command))
    application.add_handler(CommandHandler("analytics", analytics_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("level", level_command))
    application.add_handler(CommandHandler("quote", quote_command))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(CommandHandler("calendar", calendar_command))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    
    # Add edited message handler FIRST - must come before regular text handler
    application.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & filters.TEXT, handle_edited_message))
    
    # Add regular text message handler AFTER edited handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.UpdateType.EDITED_MESSAGE, handle_text_message))
    
    # Add scheduled jobs
    job_queue = application.job_queue
    
    # Sunday celebration message (18:00)
    job_queue.run_daily(
        send_sunday_celebration,
        time=datetime.strptime("18:00", "%H:%M").time(),
        days=[6]  # Sunday (0=Monday, 6=Sunday in python-telegram-bot)
    )
    
    # Monday reminder (08:00)
    job_queue.run_daily(
        send_monday_reminder,
        time=datetime.strptime("08:00", "%H:%M").time(),
        days=[0]  # Monday
    )
    
    # Daily reminder (21:00) - Only weekdays
    job_queue.run_daily(
        send_daily_reminder,
        time=datetime.strptime("21:00", "%H:%M").time(),
        days=[0, 1, 2, 3, 4]  # Monday to Friday only (weekdays)
    )
    
    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
