# 🏆 Telegram Accountability Challenge Bot

> **The Ultimate Accountability Bot - Track habits, build streaks, and achieve your goals!**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://core.telegram.org/bots)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🚀 Features

### 📊 **Core Accountability System**
- **Weekday-only tracking** (Monday-Friday focus)
- **Empty day logging** support (`/log` without activities still counts!)
- **Double letter activities** (KK40, MM15, etc.)
- **Real-time message editing** with automatic stats updates
- **Smart private messaging** with group chat fallback

### 🎮 **Advanced Gamification**
- **6-tier level system** (Beginner → Legend)
- **Achievement badges** for streaks, milestones, and consistency
- **Monthly challenges** with special recognition
- **Streak tracking** with consecutive day counting
- **Personal goals** with weekly targets and progress tracking

### 💡 **Power User Features**
- **Bulk editing** (`/edit yesterday M20 S30`)
- **Activity templates** for common combinations
- **Multi-week history** with detailed analytics
- **Data export** functionality
- **Custom activity definitions**
- **Calendar view** with visual activity indicators

### 🤖 **Smart Automation**
- **Sunday 18:00**: Weekly celebration with leader boards
- **Sunday evening**: Private weekly breakdowns
- **Weekdays 21:00**: Optional daily reminders
- **Intelligent help system** for unrecognized messages

## 📚 Quick Start

### Prerequisites
- Python 3.8+
- A Telegram Bot Token ([Get one from @BotFather](https://t.me/botfather))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/telegram-accountability-bot.git
   cd telegram-accountability-bot
   ```

2. **Install dependencies**
   ```bash
   pip install python-telegram-bot pytz
   ```

3. **Set up your bot token**
   ```bash
   # Create token file
   mkdir -p ~/bin/telegram_bot_robert
   echo "YOUR_BOT_TOKEN_HERE" > ~/bin/telegram_bot_robert/token
   ```

4. **Run the bot**
   ```bash
   python3 telegram_bot_robert.py
   ```

## 🎯 Usage Guide

### Core Commands

```bash
/log M20 S30        # Log 20 min meditation, 30 min sport
/log KK40           # Log 40 units of kickboxing (double letters supported)
/log                # Log empty day (counts for attendance!)
/status             # View current week progress
/help               # Complete command guide
```

### Analytics & Progress

```bash
/history            # Last 4 weeks of activity
/history 8          # Last 8 weeks
/analytics          # Personal insights and trends
/level              # Check level and achievements
/calendar           # Visual monthly calendar
```

### Goals & Customization

```bash
/goals              # View current weekly goals
/goals set M 100    # Set 100 units of M per week
/define M Meditation # Define what activity codes mean
/reminder on/off    # Toggle 21:00 daily reminders
```

### Power Features

```bash
/edit yesterday M30 S20     # Edit past activities
/template save morning M20 S30  # Save activity templates
/template use morning       # Use saved template
/export                     # Export your data
```

## 🏗️ Architecture

- **Database**: JSON-based local storage with automatic backups
- **Timezone**: Configurable (default: Europe/Helsinki)
- **Scheduling**: Built-in job queue for automated messages
- **Error Handling**: Comprehensive logging and graceful recovery

## 🎮 Gamification System

### Level Progression
- **Beginner** 🌱 (0-49 points)
- **Explorer** 🚀 (50-149 points)
- **Achiever** ⭐ (150-299 points)
- **Champion** 🏆 (300-499 points)
- **Master** 👑 (500-749 points)
- **Legend** 🌟 (750+ points)

### Achievements
- **Streak Badges**: 7, 14, 30+ day streaks
- **Unit Milestones**: 100, 500, 1000+ total units
- **Monthly Awards**: Consistency, Variety, Powerhouse
- **Special Recognition**: Early Bird, First Month Warrior

## 📅 Automation Schedule

- **Sunday 18:00**: Weekly celebration with stats and leader board
- **Sunday evening**: Individual weekly breakdown (private message)
- **Monday 08:00**: New week motivation message
- **Weekdays 21:00**: Daily reminders (if enabled and not logged)

## 🛠️ Configuration

### Token Setup
Update the `TOKEN_FILE_PATH` in the script:
```python
TOKEN_FILE_PATH = "/path/to/your/token/file"
```

### Timezone
```python
TIMEZONE = pytz.timezone('Your/Timezone')  # e.g., 'America/New_York'
```

### Admin Features
Update admin username for backup commands:
```python
if user.username != "your_admin_username":
```

## 📁 File Structure

```
telegram_bot_robert/
├── telegram_bot_robert.py           # Main bot file
├── accountability_db.json          # Database (auto-created)
├── backup_YYYYMMDD_HHMMSS.json    # Automatic backups
├── README.md                       # This file
├── requirements.txt                # Python dependencies
├── DEPLOYMENT_GUIDE.md            # Detailed deployment guide
├── IMPLEMENTATION_STATUS.md       # Development progress
└── FEATURE_CHECKLIST.md           # Feature selection guide
```

## 🐛 Troubleshooting

### Common Issues

1. **"Token file not found"**
   - Ensure the token file exists and contains only your bot token
   - Check file permissions

2. **"Database corruption"**
   - Bot automatically restores from backup
   - Manual restore: copy a backup file to `accountability_db.json`

3. **"Private messages not working"**
   - Users must start a conversation with the bot first
   - Bot gracefully falls back to group messages

### Logging
Logs are written to console with INFO level. For debugging:
```python
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📊 Database Schema

```json
{
  "users": {
    "user_id": {
      "username": "string",
      "joined_date": "ISO_date",
      "activity_totals": {"M": 100, "S": 200},
      "current_streak": 5,
      "longest_streak": 12,
      "achievements": ["streak_7", "total_100"],
      "goals": {"M": 100},
      "templates": {"morning": "M20 S30"}
    }
  },
  "weekly_logs": {
    "2024-W01": {
      "user_id": {
        "logs": {"2024-1-1": {"M": 20, "S": 30}},
        "missed_days": []
      }
    }
  }
}
```

## 🔒 Privacy & Security

- All data stored locally in JSON format
- No external API calls except to Telegram
- User data never shared or transmitted
- Automatic backup system with rotation
- Graceful error handling prevents data loss

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- Timezone handling by [pytz](https://pythonhosted.org/pytz/)
- Inspired by the accountability and habit-tracking community

## 📞 Support

Need help? Check out:
- [Deployment Guide](DEPLOYMENT_GUIDE.md) for setup instructions
- [Implementation Status](IMPLEMENTATION_STATUS.md) for feature details
- Open an issue for bugs or feature requests

---

**Made with ❤️ for the accountability community**

> *"Small steps every day lead to big changes every year!"* 🌟

