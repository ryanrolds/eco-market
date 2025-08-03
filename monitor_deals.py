import json
import re
import requests
import time
from datetime import datetime
from generate_report import fetch_data, clean_store_name, get_item_emoji

# Configuration
GOOD_DEAL_THRESHOLD = 50  # Minimum profit for "good deals"
CHECK_INTERVAL = 300  # 5 minutes in seconds

class DealMonitor:
    def __init__(self):
        self.tracked_deals = {}  # key: deal_id, value: deal_data
        self.startup = True
        
    def create_deal_id(self, opp):
        """Create unique identifier for a deal"""
        return f"{opp['item']}_{opp['buy_store']}_{opp['sell_store']}"
    
    def analyze_opportunities(self):
        """Analyze current arbitrage opportunities and return good deals"""
        data = fetch_data()
        if not data:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Failed to fetch market data")
            return []
        
        stores = data['Stores']
        
        # Build store info and price comparison
        store_info = {}
        items = {}
        for store in stores:
            store_name = clean_store_name(store['Name'])
            store_info[store_name] = {
                'balance': store.get('Balance', 0),
                'currency': store.get('CurrencyName', 'Unknown')
            }
            
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
                            
                            if total_profit >= GOOD_DEAL_THRESHOLD:
                                # Calculate investment required and check liquidity risk
                                investment_required = min_sell['price'] * max_trade_qty
                                buy_store_balance = store_info[min_sell['store']]['balance']
                                low_liquidity_warning = buy_store_balance - investment_required < 50
                                
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
                                    'total_profit': total_profit,
                                    'buy_store_balance': buy_store_balance,
                                    'sell_store_balance': store_info[max_buy['store']]['balance'],
                                    'investment_required': investment_required,
                                    'low_liquidity_warning': low_liquidity_warning
                                })

        # Sort by total profit
        arbitrage.sort(key=lambda x: x['total_profit'], reverse=True)
        return arbitrage
    
    def format_deal(self, opp):
        """Format a deal for display"""
        warning = " ⚠️ LOW LIQUIDITY" if opp['low_liquidity_warning'] else ""
        item_emoji = get_item_emoji(opp['item'])
        
        # Add siren emojis for high profit opportunities
        if opp['total_profit'] >= 100:
            profit_highlight = f"🚨 ${opp['total_profit']:.2f} profit 🚨"
        else:
            profit_highlight = f"${opp['total_profit']:.2f} profit"
        
        lines = []
        lines.append(f"{item_emoji} {opp['item']} ({profit_highlight}){warning}")
        lines.append(f"  ${opp['buy_price']:.2f} → ${opp['sell_price']:.2f} ({opp['margin']:.0f}% margin)")
        lines.append(f"  Buy: {opp['buy_store']} (${opp['buy_store_balance']:,.0f}) qty:{opp['buy_qty']}")
        lines.append(f"  Sell: {opp['sell_store']} (${opp['sell_store_balance']:,.0f}) qty:{opp['sell_qty']}")
        lines.append(f"  Max trade: {opp['max_trade_qty']} units")
        
        if opp['low_liquidity_warning']:
            remaining = opp['buy_store_balance'] - opp['investment_required']
            lines.append(f"  (Investment: ${opp['investment_required']:.2f}, Remaining: ${remaining:.2f})")
        
        return "\n".join(lines)
    
    def check_deals(self):
        """Check for new and completed deals"""
        current_deals = self.analyze_opportunities()
        current_deal_ids = set()
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if self.startup:
            self.startup = False
            if current_deals:
                print(f"[{timestamp}] 📊 Current good deals (${GOOD_DEAL_THRESHOLD}+ profit):")
                print("=" * 60)
                for i, deal in enumerate(current_deals, 1):
                    deal_id = self.create_deal_id(deal)
                    self.tracked_deals[deal_id] = deal
                    current_deal_ids.add(deal_id)
                    
                    print(f"{i}. {self.format_deal(deal)}")
                    print()
                print(f"Found {len(current_deals)} good deals. Monitoring for changes every 5 minutes...")
            else:
                print(f"[{timestamp}] No good deals found (${GOOD_DEAL_THRESHOLD}+ profit). Monitoring...")
            print()
            return
        
        # Build current deals map
        current_deals_map = {}
        for deal in current_deals:
            deal_id = self.create_deal_id(deal)
            current_deals_map[deal_id] = deal
            current_deal_ids.add(deal_id)
        
        # Check for new deals
        new_deals = []
        for deal_id, deal in current_deals_map.items():
            if deal_id not in self.tracked_deals:
                new_deals.append(deal)
        
        # Check for completed deals
        completed_deals = []
        for deal_id, deal in self.tracked_deals.items():
            if deal_id not in current_deal_ids:
                completed_deals.append(deal)
        
        # Output new deals
        if new_deals:
            print(f"[{timestamp}] 🆕 NEW GOOD DEALS:")
            print("-" * 40)
            for deal in new_deals:
                print(self.format_deal(deal))
                print()
        
        # Output completed deals
        if completed_deals:
            print(f"[{timestamp}] ❌ COMPLETED DEALS:")
            print("-" * 40)
            for deal in completed_deals:
                print(f"{get_item_emoji(deal['item'])} {deal['item']} (${deal['total_profit']:.2f} profit) - NO LONGER AVAILABLE")
            print()
        
        # Update tracked deals
        self.tracked_deals = current_deals_map.copy()
        
        # Show status if no changes
        if not new_deals and not completed_deals:
            print(f"[{timestamp}] 🔄 No changes. Monitoring {len(current_deals)} good deals...")
    
    def run(self):
        """Main monitoring loop"""
        print(f"🔍 Deal Monitor Started - Watching for ${GOOD_DEAL_THRESHOLD}+ profit opportunities")
        print(f"📡 Checking every {CHECK_INTERVAL//60} minutes")
        print("=" * 60)
        
        try:
            while True:
                self.check_deals()
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🛑 Monitor stopped by user")
        except Exception as e:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {e}")

if __name__ == "__main__":
    monitor = DealMonitor()
    monitor.run()