import json
import re
import requests
import discord
import asyncio
import os
from datetime import datetime
from discord.ext import tasks

# Configuration
MIN_PROFIT_THRESHOLD = 10  # Minimum total profit to show opportunities
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

def clean_store_name(name):
    """Remove color tags from store names"""
    return re.sub(r'<color=[^>]*>|</color>', '', name)

def fetch_data():
    """Fetch data from API or use local file as fallback"""
    try:
        response = requests.get("http://144.217.255.182:3001/api/v1/plugins/EcoPriceCalculator/stores", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch from API: {e}")
        return None

def analyze_arbitrage():
    """Analyze arbitrage opportunities and return formatted message"""
    data = fetch_data()
    if not data:
        return "❌ Failed to fetch market data"
    
    stores = data['Stores']
    
    # Build price comparison
    items = {}
    for store in stores:
        store_name = clean_store_name(store['Name'])
        for offer in store.get('AllOffers', []):
            item = offer['ItemName']
            price = offer['Price']
            buying = offer['Buying']
            quantity = offer['Quantity']
            
            if item not in items:
                items[item] = {'sellers': [], 'buyers': []}
            
            if buying:
                items[item]['buyers'].append({'store': store_name, 'price': price, 'qty': quantity})
            else:
                items[item]['sellers'].append({'store': store_name, 'price': price, 'qty': quantity})

    # Find arbitrage opportunities
    arbitrage = []
    for item, data in items.items():
        if data['sellers'] and data['buyers']:
            # Filter sellers and buyers with quantity > 0
            sellers_with_stock = [s for s in data['sellers'] if s['qty'] > 0]
            buyers_with_demand = [b for b in data['buyers'] if b['qty'] > 0]
            
            if sellers_with_stock and buyers_with_demand:
                min_sell = min(sellers_with_stock, key=lambda x: x['price'])
                max_buy = max(buyers_with_demand, key=lambda x: x['price'])
                
                if max_buy['price'] > min_sell['price'] and min_sell['price'] < 999999:
                    profit = max_buy['price'] - min_sell['price']
                    if min_sell['price'] > 0:
                        margin = (profit / min_sell['price']) * 100
                    else:
                        margin = 0
                    if profit > 0.1:
                        max_trade_qty = min(min_sell['qty'], max_buy['qty'])
                        total_profit = profit * max_trade_qty
                        arbitrage.append({
                            'item': item,
                            'buy_store': min_sell['store'],
                            'buy_price': min_sell['price'],
                            'buy_qty': min_sell['qty'],
                            'sell_store': max_buy['store'],
                            'sell_price': max_buy['price'],
                            'sell_qty': max_buy['qty'],
                            'profit': profit,
                            'margin': margin,
                            'max_trade_qty': max_trade_qty,
                            'total_profit': total_profit
                        })

    # Filter for high profit opportunities
    high_profit_arbitrage = [opp for opp in arbitrage if opp['total_profit'] >= MIN_PROFIT_THRESHOLD]
    high_profit_arbitrage.sort(key=lambda x: x['total_profit'], reverse=True)
    
    # Format message
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"🔄 **Market Arbitrage Report** - {timestamp}\n"
    message += f"Found {len(high_profit_arbitrage)} opportunities with >=${MIN_PROFIT_THRESHOLD} profit:\n\n"
    
    if not high_profit_arbitrage:
        message += "No profitable arbitrage opportunities found."
        return message
    
    # Limit to top 10 to avoid Discord message length limits
    for i, opp in enumerate(high_profit_arbitrage[:10], 1):
        message += f"**{i}. {opp['item']}**\n"
        message += f"💰 ${opp['buy_price']:.2f} → ${opp['sell_price']:.2f} (${opp['total_profit']:.2f} profit)\n"
        message += f"📦 Buy from: {opp['buy_store']} (qty: {opp['buy_qty']})\n"
        message += f"🏪 Sell to: {opp['sell_store']} (qty: {opp['sell_qty']})\n"
        message += f"📊 Max trade: {opp['max_trade_qty']} units, {opp['margin']:.0f}% margin\n\n"
    
    if len(high_profit_arbitrage) > 10:
        message += f"... and {len(high_profit_arbitrage) - 10} more opportunities\n"
    
    return message

class MarketBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Needed to read message content
        super().__init__(intents=intents)
        
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
        
        self.market_report.start()
    
    async def on_message(self, message):
        # Don't respond to the bot's own messages
        if message.author == self.user:
            return
        
        # Check if message is in the target channel
        if message.channel.id != CHANNEL_ID:
            return
        
        # Check for commands
        content = message.content.lower().strip()
        
        if content in ['!market', '!report', '!arbitrage', '!deals']:
            try:
                await message.channel.send("🔄 Generating market report...")
                report = analyze_arbitrage()
                
                # Split message if it's too long for Discord (2000 char limit)
                if len(report) > 2000:
                    chunks = [report[i:i+2000] for i in range(0, len(report), 2000)]
                    for chunk in chunks:
                        await message.channel.send(chunk)
                else:
                    await message.channel.send(report)
            except Exception as e:
                await message.channel.send(f"❌ Error generating report: {str(e)}")
        
        elif content in ['!help', '!commands']:
            help_text = """
📊 **Market Bot Commands:**
• `!market` or `!report` - Get current arbitrage report
• `!arbitrage` or `!deals` - Same as !market
• `!help` or `!commands` - Show this help

ℹ️ Automatic reports are sent every hour.
"""
            await message.channel.send(help_text)
    
    @tasks.loop(hours=1)
    async def market_report(self):
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
    
    @market_report.before_loop
    async def before_market_report(self):
        await self.wait_until_ready()

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Please set the DISCORD_TOKEN environment variable")
        exit(1)
    
    if CHANNEL_ID == 0:
        print("Please set the DISCORD_CHANNEL_ID environment variable")
        exit(1)
    
    bot = MarketBot()
    bot.run(DISCORD_TOKEN)