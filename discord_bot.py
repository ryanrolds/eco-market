import discord
import asyncio
import os
from datetime import datetime
from discord.ext import tasks, commands
from generate_report import analyze_arbitrage

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

class MarketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        # No need for message_content intent with slash commands
        super().__init__(command_prefix='!', intents=intents)
        self.first_run = True
        
    async def setup_hook(self):
        # Sync slash commands
        await self.tree.sync()
        print("Slash commands synced!")
        
    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        print(f'Bot is in {len(self.guilds)} guilds')
        
        # Debug: List all channels the bot can see
        channel = self.get_channel(CHANNEL_ID)
        if channel:
            print(f'Found target channel: {channel.name} in {channel.guild.name}')
        else:
            print(f'Could not find channel with ID {CHANNEL_ID}')
            print('Available channels:')
            for guild in self.guilds:
                print(f'  Guild: {guild.name}')
                for channel in guild.text_channels:
                    print(f'    #{channel.name} (ID: {channel.id})')
        
        # Start the scheduler task instead of the loop
        self.schedule_reports.start()
    
    async def send_market_report(self):
        """Send the actual market report"""
        try:
            channel = self.get_channel(CHANNEL_ID)
            if channel:
                message = analyze_arbitrage()
                
                # Split message if it's too long for Discord (2000 char limit)
                if len(message) > 2000:
                    chunks = [message[i:i+2000] for i in range(0, len(message), 2000)]
                    for chunk in chunks:
                        await channel.send(chunk)
                else:
                    await channel.send(message)
            else:
                print(f"Could not find channel with ID {CHANNEL_ID}")
        except Exception as e:
            print(f"Error sending market report: {e}")
    
    @tasks.loop(minutes=1)
    async def schedule_reports(self):
        """Check every minute if it's time to send a report (on :00 and :30)"""
        now = datetime.now()
        
        # Send report at :00 and :30 minutes
        if now.minute in [0, 30] and now.second < 10:  # Small window to avoid duplicate sends
            if self.first_run:
                self.first_run = False
                # Calculate next report time
                if now.minute == 0:
                    next_time = "30 minutes"
                else:
                    next_time = f"{60 - now.minute} minutes" 
                print(f"Bot started at {now.strftime('%H:%M')}. Next report in {next_time}.")
                return
            
            print(f"Sending scheduled report at {now.strftime('%H:%M')}")
            await self.send_market_report()
    
    @schedule_reports.before_loop
    async def before_schedule_reports(self):
        await self.wait_until_ready()

# Create bot instance
bot = MarketBot()

@bot.tree.command(name="market", description="Get current market arbitrage report")
async def market_command(interaction: discord.Interaction):
    await interaction.response.defer()
    
    try:
        report = analyze_arbitrage()
        
        # Split message if it's too long for Discord (2000 char limit)
        if len(report) > 2000:
            chunks = [report[i:i+2000] for i in range(0, len(report), 2000)]
            await interaction.followup.send(chunks[0])
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk)
        else:
            await interaction.followup.send(report)
    except Exception as e:
        await interaction.followup.send(f"❌ Error generating report: {str(e)}")

@bot.tree.command(name="help", description="Show available bot commands")
async def help_command(interaction: discord.Interaction):
    help_text = """**Market Bot Commands:**
• `/market` - Get current arbitrage report
• `/help` - Show this help

Automatic reports sent at :00 and :30 minutes."""
    await interaction.response.send_message(help_text)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Please set the DISCORD_TOKEN environment variable")
        exit(1)
    
    if CHANNEL_ID == 0:
        print("Please set the DISCORD_CHANNEL_ID environment variable")
        exit(1)
    
    bot.run(DISCORD_TOKEN)