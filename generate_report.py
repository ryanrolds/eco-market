import json
import re
import requests
from datetime import datetime

# Configuration
MIN_PROFIT_THRESHOLD = 10  # Minimum total profit to show opportunities

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

def get_item_emoji(item_name):
    """Get creative emoji for item based on name"""
    item_lower = item_name.lower()
    
    # Materials & Resources
    if any(word in item_lower for word in ['iron', 'steel', 'metal']):
        return '⚔️'
    elif any(word in item_lower for word in ['wood', 'lumber', 'board', 'log']):
        return '🪵'
    elif any(word in item_lower for word in ['stone', 'granite', 'limestone', 'rock']):
        return '🪨'
    elif any(word in item_lower for word in ['coal', 'charcoal']):
        return '⚫'
    elif any(word in item_lower for word in ['oil', 'petroleum']):
        return '🛢️'
    elif any(word in item_lower for word in ['glass']):
        return '🔮'
    elif any(word in item_lower for word in ['clay', 'pottery']):
        return '🏺'
    elif any(word in item_lower for word in ['sand']):
        return '⏳'
    elif any(word in item_lower for word in ['cement', 'concrete', 'mortar']):
        return '🧱'
    elif any(word in item_lower for word in ['copper']):
        return '🔶'
    elif any(word in item_lower for word in ['gold']):
        return '✨'
    
    # Food & Agriculture
    elif any(word in item_lower for word in ['meat', 'bacon', 'sausage']):
        return '🥓'
    elif any(word in item_lower for word in ['vegetable', 'salad', 'beet', 'corn']):
        return '🥗'
    elif any(word in item_lower for word in ['fruit', 'berry', 'apple', 'pineapple']):
        return '🍍'
    elif any(word in item_lower for word in ['bread', 'flour', 'wheat']):
        return '🍞'
    elif any(word in item_lower for word in ['soup', 'stew']):
        return '🍲'
    elif any(word in item_lower for word in ['fish', 'seafood']):
        return '🐟'
    elif any(word in item_lower for word in ['milk', 'cheese']):
        return '🥛'
    elif any(word in item_lower for word in ['sugar', 'syrup']):
        return '🍯'
    elif any(word in item_lower for word in ['bean', 'seed']):
        return '🌱'
    elif any(word in item_lower for word in ['mushroom']):
        return '🍄'
    
    # Tools & Equipment
    elif any(word in item_lower for word in ['axe', 'hammer', 'pickaxe', 'shovel', 'tool']):
        return '🔨'
    elif any(word in item_lower for word in ['wheel', 'gear', 'mechanical']):
        return '⚙️'
    elif any(word in item_lower for word in ['cart', 'wagon']):
        return '🛒'
    elif any(word in item_lower for word in ['mill', 'windmill']):
        return '🌀'
    elif any(word in item_lower for word in ['pump']):
        return '🔧'
    elif any(word in item_lower for word in ['saw', 'blade']):
        return '🪚'
    elif any(word in item_lower for word in ['drill']):
        return '🔩'
    elif any(word in item_lower for word in ['anchor']):
        return '⚓'
    
    # Clothing & Textiles
    elif any(word in item_lower for word in ['fabric', 'cloth', 'textile', 'yarn']):
        return '🧵'
    elif any(word in item_lower for word in ['shirt', 'clothing']):
        return '👕'
    elif any(word in item_lower for word in ['pants', 'trousers']):
        return '👖'
    elif any(word in item_lower for word in ['shoes', 'boots']):
        return '👢'
    elif any(word in item_lower for word in ['hat', 'cap']):
        return '🎩'
    elif any(word in item_lower for word in ['backpack', 'bag']):
        return '🎒'
    elif any(word in item_lower for word in ['belt']):
        return '🔗'
    elif any(word in item_lower for word in ['canvas']):
        return '🎨'
    
    # Furniture & Home
    elif any(word in item_lower for word in ['table', 'desk']):
        return '🪑'
    elif any(word in item_lower for word in ['chair', 'bench']):
        return '🪑'
    elif any(word in item_lower for word in ['bed']):
        return '🛏️'
    elif any(word in item_lower for word in ['door']):
        return '🚪'
    elif any(word in item_lower for word in ['rug', 'carpet']):
        return '🏠'
    elif any(word in item_lower for word in ['couch', 'sofa']):
        return '🛋️'
    elif any(word in item_lower for word in ['lamp', 'light']):
        return '💡'
    elif any(word in item_lower for word in ['mirror']):
        return '🪞'
    elif any(word in item_lower for word in ['fountain']):
        return '⛲'
    
    # Chemicals & Compounds
    elif any(word in item_lower for word in ['powder', 'dust']):
        return '💨'
    elif any(word in item_lower for word in ['acid', 'chemical']):
        return '🧪'
    elif any(word in item_lower for word in ['fertilizer', 'compost']):
        return '🌿'
    elif any(word in item_lower for word in ['ink', 'dye']):
        return '🖋️'
    elif any(word in item_lower for word in ['explosive', 'powder']):
        return '💥'
    
    # Art & Decoration
    elif any(word in item_lower for word in ['art', 'paint', 'canvas']):
        return '🎨'
    elif any(word in item_lower for word in ['tapestry', 'decoration']):
        return '🖼️'
    elif any(word in item_lower for word in ['bunting', 'streamer']):
        return '🎊'
    elif any(word in item_lower for word in ['sign']):
        return '🪧'
    elif any(word in item_lower for word in ['plaque']):
        return '🏷️'
    
    # Misc
    elif any(word in item_lower for word in ['paper', 'research']):
        return '📄'
    elif any(word in item_lower for word in ['nail', 'screw']):
        return '📎'
    elif any(word in item_lower for word in ['rope', 'cord']):
        return '🪢'
    elif any(word in item_lower for word in ['fiber']):
        return '🧶'
    elif any(word in item_lower for word in ['waste', 'dirt', 'trash']):
        return '🗑️'
    
    # Default for unmatched items
    return '📦'

def analyze_arbitrage():
    """Analyze arbitrage opportunities and return formatted message"""
    data = fetch_data()
    if not data:
        return "Failed to fetch market data"
    
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

    # Filter for high profit opportunities
    high_profit_arbitrage = [opp for opp in arbitrage if opp['total_profit'] >= MIN_PROFIT_THRESHOLD]
    high_profit_arbitrage.sort(key=lambda x: x['total_profit'], reverse=True)
    
    # Format message
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = f"**Market Report** - {timestamp}\n"
    message += f"Found {len(high_profit_arbitrage)} opportunities with >=${MIN_PROFIT_THRESHOLD} profit:\n\n"
    
    if not high_profit_arbitrage:
        message += "No profitable opportunities found."
        return message
    
    # Show all opportunities (not limited to 10 for standalone script)
    for i, opp in enumerate(high_profit_arbitrage, 1):
        warning = " ⚠️ LOW LIQUIDITY" if opp['low_liquidity_warning'] else ""
        item_emoji = get_item_emoji(opp['item'])
        
        # Add siren emojis for high profit opportunities
        if opp['total_profit'] >= 100:
            profit_highlight = f"🚨 ${opp['total_profit']:.2f} profit 🚨"
        else:
            profit_highlight = f"${opp['total_profit']:.2f} profit"
        
        message += f"**{i}. {item_emoji} {opp['item']}** ({profit_highlight}){warning}\n"
        message += f"${opp['buy_price']:.2f} → ${opp['sell_price']:.2f} ({opp['margin']:.0f}% margin)\n"
        message += f"Buy: {opp['buy_store']} (${opp['buy_store_balance']:,.0f}) qty:{opp['buy_qty']}\n"
        message += f"Sell: {opp['sell_store']} (${opp['sell_store_balance']:,.0f}) qty:{opp['sell_qty']}\n"
        message += f"Max trade: {opp['max_trade_qty']} units"
        if opp['low_liquidity_warning']:
            remaining = opp['buy_store_balance'] - opp['investment_required']
            message += f" (Investment: ${opp['investment_required']:.2f}, Remaining: ${remaining:.2f})"
        message += "\n\n"
    
    return message

if __name__ == "__main__":
    report = analyze_arbitrage()
    print(report)