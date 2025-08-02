import json
import re
import requests

# Configuration
MIN_PROFIT_THRESHOLD = 10  # Minimum total profit to show opportunities

def clean_store_name(name):
    """Remove color tags from store names"""
    return re.sub(r'<color=[^>]*>|</color>', '', name)

def fetch_data():
    """Fetch data from API or use local file as fallback"""
    try:
        print("Fetching data from API...")
        response = requests.get("http://144.217.255.182:3001/api/v1/plugins/EcoPriceCalculator/stores", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch from API ({e}), using local file...")
        try:
            with open('stores_data.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("No local file found. Please ensure stores_data.json exists or API is accessible.")
            exit(1)

data = fetch_data()
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
print('ARBITRAGE OPPORTUNITIES:')
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

# Filter for high profit opportunities and sort by total profit potential
high_profit_arbitrage = [opp for opp in arbitrage if opp['total_profit'] >= MIN_PROFIT_THRESHOLD]
high_profit_arbitrage.sort(key=lambda x: x['total_profit'], reverse=True)

print(f"Found {len(high_profit_arbitrage)} opportunities with >=${MIN_PROFIT_THRESHOLD} profit:")
for opp in high_profit_arbitrage:
    print(f"{opp['item']}: ${opp['buy_price']:.2f} -> ${opp['sell_price']:.2f} (${opp['total_profit']:.2f} total profit)")
    print(f"  Buy from: {opp['buy_store']} (qty: {opp['buy_qty']})")
    print(f"  Sell to: {opp['sell_store']} (qty: {opp['sell_qty']})")
    print(f"  Max trade: {opp['max_trade_qty']} units, {opp['margin']:.0f}% margin")