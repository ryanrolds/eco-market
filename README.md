# ECO Market Discord Bot Setup Guide

## 1. Create a Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application" and give it a name
3. Go to the "Bot" section in the left sidebar
4. Click "Add Bot"
5. Copy the bot token (keep this secret!)

## 2. Set Environment Variables

Set the required environment variables:

```bash
# Discord Bot Configuration
export DISCORD_TOKEN="asdfasdfasdf"
export DISCORD_CHANNEL_ID="your_channel_id"

# ECO Server Configuration (optional - default shown)
export ECO_SERVER_URL="http://144.217.255.182:3001"  # Default: http://144.217.255.182:3001

# Currency Filter (optional - filters stores by currency)
export CURRENCY_FILTER="Gold Coins,USD"  # Only show stores using these currencies
```

### To get Channel ID:
1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
2. Right-click on the channel where you want reports
3. Click "Copy ID"

## 3. Add Bot to Your Server

1. In the Discord Developer Portal, go to "OAuth2" > "URL Generator"
2. Select scopes: `bot`
3. Select permissions: `Send Messages`, `Read Message History`, `View Channels`
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

## 4. Install Dependencies

```bash
pip3 install -r requirements.txt
```

## Usage

### Terminal Market Report

Get a market report directly in your terminal:

```bash
python3 generate_report.py
```

This will fetch current market data and display all arbitrage opportunities with profit >= $5.

You can also filter by specific currencies using command line arguments:
```bash
python3 generate_report.py "Gold Coins" "USD"
```

### Deal Monitor

Monitor for good deals in real-time with change notifications:

```bash
python3 monitor_deals.py
```

This will:
- Show current good deals (>= $50 profit) on startup
- Check for new deals every 5 minutes
- Alert when new deals appear or existing deals disappear
- Run continuously until stopped with Ctrl+C

### Crafting Profit Analyzer

Analyze profitable crafting opportunities:

```bash
python3 crafting_analyzer.py
```

This will:
- Fetch current market prices and crafting recipes
- Calculate ingredient costs vs product sale prices
- Show profitable crafting opportunities with required skills/tables
- Include ingredient sourcing and product selling information

### Profession Profit Analyzer

Analyze profit potential by profession:

```bash
python3 profession_analyzer.py
```

This will:
- Calculate theoretical maximum profit for each profession
- Rank professions by total market demand value
- Show top opportunities for each profession
- Ignore ingredient availability constraints

### Discord Bot

Run the Discord bot for automated hourly reports and slash commands:

```bash
python3 discord_bot.py
```

**Bot Commands:**
- `/market` - Get current arbitrage report
- `/help` - Show available commands

## Configuration Options

### Environment Variables

#### Required for Discord Bot
- `DISCORD_TOKEN`: Your Discord bot token (required for discord_bot.py)
- `DISCORD_CHANNEL_ID`: Discord channel ID for automated reports (required for discord_bot.py)

#### Optional Configuration
- `ECO_SERVER_URL`: Full ECO server URL including protocol and port
  - Default: `"http://144.217.255.182:3001"`
  - Used by: All scripts (generate_report.py, crafting_analyzer.py, profession_analyzer.py, monitor_deals.py, discord_bot.py)
  - Example: `"http://your-eco-server.com:3001"`

- `CURRENCY_FILTER`: Comma-separated list of currency names to filter by
  - Default: `None` (includes all currencies)
  - Used by: generate_report.py, discord_bot.py
  - Example: `"USD,EUR,Gold Coins"` (only show stores using these currencies)
  - Note: Command line arguments override this environment variable

### Script Settings
- `MIN_PROFIT_THRESHOLD`: Minimum profit to show opportunities (default: varies by script)
- Reports are sent at :00 and :30 minutes of each hour
- Bot limits to top 10 opportunities to avoid message length limits
- Uses slash commands (no privileged intents required)
- No report sent on startup - waits for next scheduled time

## Troubleshooting

- Make sure the bot has permissions to send messages in the target channel
- Check that the channel ID is correct
- Verify the bot token is valid
- Ensure the bot is online and connected to your server
- Slash commands may take a few minutes to appear after first run