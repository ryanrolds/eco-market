# Discord Bot Setup Guide

## 1. Create a Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application" and give it a name
3. Go to the "Bot" section in the left sidebar
4. Click "Add Bot"
5. Copy the bot token (keep this secret!)

## 2. Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set your values:
   ```
   DISCORD_TOKEN=your_actual_bot_token
   DISCORD_CHANNEL_ID=your_channel_id
   ```

### To get Channel ID:
1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
2. Right-click on the channel where you want reports
3. Click "Copy ID"

### Alternative: Set environment variables directly:
```bash
export DISCORD_TOKEN="your_bot_token"
export DISCORD_CHANNEL_ID="your_channel_id"
```

## 3. Add Bot to Your Server

1. In the Discord Developer Portal, go to "OAuth2" > "URL Generator"
2. Select scopes: `bot`
3. Select permissions: `Send Messages`, `Read Message History`, `View Channels`
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

## 4. Install Dependencies and Run

```bash
pip install -r requirements.txt

# If using .env file, you may need python-dotenv:
pip install python-dotenv

# Run the bot
python discord_bot.py
```

### Using .env file (recommended):
If you want to use a `.env` file, install python-dotenv and load it:
```bash
pip install python-dotenv
```
Then add this to the top of `discord_bot.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

## Bot Commands

Users can interact with the bot using these commands in the configured channel:

- `!market` or `!report` - Get current arbitrage report
- `!arbitrage` or `!deals` - Same as !market
- `!help` or `!commands` - Show available commands

## Configuration Options

- `MIN_PROFIT_THRESHOLD`: Minimum profit to show opportunities (default: 10)
- Reports are sent every hour automatically
- Bot limits to top 10 opportunities to avoid message length limits
- Bot only responds to commands in the configured channel

## Troubleshooting

- Make sure the bot has permissions to send messages in the target channel
- Check that the channel ID is correct
- Verify the bot token is valid
- Ensure the bot is online and connected to your server