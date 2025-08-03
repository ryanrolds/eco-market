import json
import re
import requests
from datetime import datetime
from generate_report import fetch_data, clean_store_name, get_item_emoji

# Configuration
MIN_CRAFTING_PROFIT = 1  # Minimum profit for crafting opportunities
MIN_INGREDIENT_QUANTITY = 50  # Minimum quantity available for ingredients (be conservative)
MIN_RECIPE_BATCHES = 5  # Ensure we can make at least 5 batches of the recipe
DEBUG = True  # Show debug information

def fetch_recipes():
    """Fetch recipe data from API"""
    try:
        response = requests.get("http://144.217.255.182:3001/api/v1/plugins/EcoPriceCalculator/recipes", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch recipe data: {e}")
        return None

def get_market_prices():
    """Get current market prices for all items"""
    data = fetch_data()
    if not data:
        return {}
    
    market_prices = {}
    
    for store in data['Stores']:
        store_name = clean_store_name(store['Name'])
        
        for offer in store.get('AllOffers', []):
            item = offer['ItemName']
            price = offer['Price']
            quantity = offer['Quantity']
            is_buying = offer['Buying']
            
            # Skip invalid prices and zero quantities
            if price >= 999999 or quantity <= 0:
                continue
            
            if item not in market_prices:
                market_prices[item] = {'buy_prices': [], 'sell_prices': []}
            
            if is_buying:
                market_prices[item]['sell_prices'].append({'price': price, 'qty': quantity, 'store': store_name})
            else:
                market_prices[item]['buy_prices'].append({'price': price, 'qty': quantity, 'store': store_name})
    
    # Calculate best prices for each item
    best_prices = {}
    for item, prices in market_prices.items():
        best_buy_price = None
        best_sell_price = None
        
        if prices['buy_prices']:
            best_buy_price = min(prices['buy_prices'], key=lambda x: x['price'])
        
        if prices['sell_prices']:
            best_sell_price = max(prices['sell_prices'], key=lambda x: x['price'])
        
        best_prices[item] = {
            'buy': best_buy_price,
            'sell': best_sell_price
        }
    
    return best_prices

def analyze_crafting_profits():
    """Analyze crafting opportunities for profit"""
    recipe_data = fetch_recipes()
    if not recipe_data:
        return []
    
    market_prices = get_market_prices()
    if not market_prices:
        return []
    
    crafting_opportunities = []
    
    for recipe in recipe_data.get('Recipes', []):
        recipe_name = recipe['Key']
        
        # Skip skill books and research recipes (usually not profitable to craft for sale)
        if any(word in recipe_name.lower() for word in ['skill book', 'research paper']):
            continue
        
        for variant in recipe.get('Variants', []):
            variant_name = variant['Name']
            ingredients = variant.get('Ingredients', [])
            products = variant.get('Products', [])
            
            if not ingredients or not products:
                continue
            
            # Calculate ingredient costs
            ingredient_cost = 0
            missing_ingredients = []
            insufficient_quantity = []
            ingredient_details = []
            
            for ingredient in ingredients:
                ingredient_name = ingredient['Name'] if ingredient['IsSpecificItem'] else ingredient.get('Tag', 'Unknown')
                amount_needed = ingredient['Ammount']
                
                # For tagged ingredients, find cheapest item with that tag
                if not ingredient['IsSpecificItem'] and ingredient.get('Tag'):
                    # Common tag mappings
                    tag_items = {
                        'Wood': ['Lumber', 'Board'],
                        'Wood Board': ['Board'],
                        'Lumber': ['Lumber'],
                        'Rock': ['Stone', 'Granite', 'Limestone'],
                        'Oil': ['Oil', 'Flaxseed Oil']
                    }
                    
                    if ingredient['Tag'] in tag_items:
                        cheapest_price = float('inf')
                        cheapest_item = None
                        
                        for tag_item in tag_items[ingredient['Tag']]:
                            if tag_item in market_prices and market_prices[tag_item]['buy']:
                                item_price = market_prices[tag_item]['buy']['price']
                                if item_price < cheapest_price:
                                    cheapest_price = item_price
                                    cheapest_item = tag_item
                        
                        if cheapest_item:
                            # Check if there's enough quantity available for multiple batches
                            available_qty = market_prices[cheapest_item]['buy']['qty']
                            needed_for_batches = amount_needed * MIN_RECIPE_BATCHES
                            
                            if available_qty < max(MIN_INGREDIENT_QUANTITY, needed_for_batches):
                                insufficient_quantity.append(f"{cheapest_item} (need {max(MIN_INGREDIENT_QUANTITY, needed_for_batches)}, have {available_qty})")
                            else:
                                ingredient_name = cheapest_item
                                ingredient_cost += cheapest_price * amount_needed
                                ingredient_details.append({
                                    'name': ingredient_name,
                                    'amount': amount_needed,
                                    'unit_price': cheapest_price,
                                    'total_cost': cheapest_price * amount_needed,
                                    'store': market_prices[cheapest_item]['buy']['store'],
                                    'available_qty': available_qty,
                                    'max_batches': available_qty // amount_needed
                                })
                        else:
                            missing_ingredients.append(f"{ingredient['Tag']} (tag)")
                    else:
                        missing_ingredients.append(f"{ingredient['Tag']} (unknown tag)")
                else:
                    # Specific item - must have seller data
                    if ingredient_name in market_prices and market_prices[ingredient_name]['buy']:
                        unit_price = market_prices[ingredient_name]['buy']['price']
                        available_qty = market_prices[ingredient_name]['buy']['qty']
                        needed_for_batches = amount_needed * MIN_RECIPE_BATCHES
                        
                        if available_qty < max(MIN_INGREDIENT_QUANTITY, needed_for_batches):
                            insufficient_quantity.append(f"{ingredient_name} (need {max(MIN_INGREDIENT_QUANTITY, needed_for_batches)}, have {available_qty})")
                        else:
                            ingredient_cost += unit_price * amount_needed
                            ingredient_details.append({
                                'name': ingredient_name,
                                'amount': amount_needed,
                                'unit_price': unit_price,
                                'total_cost': unit_price * amount_needed,
                                'store': market_prices[ingredient_name]['buy']['store'],
                                'available_qty': available_qty,
                                'max_batches': available_qty // amount_needed
                            })
                    else:
                        missing_ingredients.append(f"{ingredient_name} (no sellers)")
            
            # Skip if we're missing ingredient prices or insufficient quantities
            if missing_ingredients or insufficient_quantity:
                continue
            
            # Calculate product revenue - must have buyer data
            total_revenue = 0
            product_details = []
            missing_products = []
            
            for product in products:
                product_name = product['Name']
                amount_produced = product['Ammount']
                
                # Must have actual buyers, not just sellers
                if product_name in market_prices and market_prices[product_name]['sell']:
                    unit_price = market_prices[product_name]['sell']['price']
                    buyer_demand = market_prices[product_name]['sell']['qty']
                    
                    # Ensure there's reasonable demand for the product
                    if buyer_demand < MIN_RECIPE_BATCHES:
                        missing_products.append(f"{product_name} (insufficient demand: {buyer_demand})")
                    else:
                        total_revenue += unit_price * amount_produced
                        product_details.append({
                            'name': product_name,
                            'amount': amount_produced,
                            'unit_price': unit_price,
                            'total_revenue': unit_price * amount_produced,
                            'store': market_prices[product_name]['sell']['store'],
                            'buyer_demand': buyer_demand
                        })
                else:
                    missing_products.append(f"{product_name} (no buyers)")
            
            # Skip if we can't sell the products
            if missing_products:
                continue
            
            # Calculate profit
            profit = total_revenue - ingredient_cost
            
            if profit >= MIN_CRAFTING_PROFIT:
                margin = (profit / ingredient_cost * 100) if ingredient_cost > 0 else 0
                craft_time = recipe.get('BaseCraftTime', 1)  # Avoid division by zero
                profit_per_second = profit / max(craft_time, 0.1)  # Min 0.1s to avoid infinity
                
                crafting_opportunities.append({
                    'recipe': recipe_name,
                    'variant': variant_name,
                    'ingredient_cost': ingredient_cost,
                    'revenue': total_revenue,
                    'profit': profit,
                    'margin': margin,
                    'profit_per_second': profit_per_second,
                    'ingredient_details': ingredient_details,
                    'product_details': product_details,
                    'crafting_table': recipe.get('CraftingTable', 'Unknown'),
                    'skill_needs': recipe.get('SkillNeeds', []),
                    'craft_time': craft_time,
                    'labor_cost': recipe.get('BaseLaborCost', 0)
                })
    
    # Calculate total profit limited by both ingredient availability and product demand
    for opp in crafting_opportunities:
        # Max batches limited by ingredient availability
        max_batches_by_ingredients = min(ing['max_batches'] for ing in opp['ingredient_details'])
        
        # Max batches limited by product demand (how much buyers want)
        max_batches_by_demand = float('inf')
        for prod in opp['product_details']:
            batches_supportable = prod['buyer_demand'] // prod['amount']
            max_batches_by_demand = min(max_batches_by_demand, batches_supportable)
        
        # Take the minimum of both constraints
        max_realistic_batches = min(max_batches_by_ingredients, max_batches_by_demand)
        
        opp['total_possible_profit'] = opp['profit'] * max_realistic_batches
        opp['max_craftable_batches'] = max_realistic_batches
        opp['max_batches_by_ingredients'] = max_batches_by_ingredients
        opp['max_batches_by_demand'] = max_batches_by_demand
    
    # Filter by total profit threshold and sort
    crafting_opportunities = [opp for opp in crafting_opportunities if opp['total_possible_profit'] >= MIN_CRAFTING_PROFIT]
    crafting_opportunities.sort(key=lambda x: x['total_possible_profit'], reverse=True)
    return crafting_opportunities

def format_crafting_report(opportunities):
    """Format crafting opportunities into a readable report"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = f"**Crafting Profit Report** - {timestamp}\n"
    message += f"Found {len(opportunities)} profitable crafting opportunities:\n\n"
    
    if not opportunities:
        message += "No profitable crafting opportunities found."
        return message
    
    for i, opp in enumerate(opportunities[:20], 1):  # Top 20
        emoji = get_item_emoji(opp['variant'])
        
        # Highlight high total profits (make total profit most prominent)
        if opp['total_possible_profit'] >= 100:
            total_profit_text = f"🚨 ${opp['total_possible_profit']:.2f} TOTAL PROFIT 🚨"
        elif opp['total_possible_profit'] >= 50:
            total_profit_text = f"⭐ ${opp['total_possible_profit']:.2f} TOTAL PROFIT ⭐"
        else:
            total_profit_text = f"${opp['total_possible_profit']:.2f} TOTAL PROFIT"
        
        message += f"**{i}. {emoji} {opp['variant']}** - {total_profit_text}\n"
        message += f"Unit profit: ${opp['profit']:.2f} | Profit/sec: ${opp['profit_per_second']:.2f} | {opp['margin']:.1f}% margin\n"
        message += f"Table: {opp['crafting_table']} | Time: {opp['craft_time']}s"
        
        if opp['skill_needs']:
            skills = [f"{s['Skill']} Lv.{s['Level']}" for s in opp['skill_needs']]
            message += f" | Skills: {', '.join(skills)}"
        
        message += f" | Time: {opp['craft_time']}s\n"
        
        # Show ingredients
        message += "Ingredients: "
        ing_list = []
        for ing in opp['ingredient_details']:
            ing_list.append(f"{ing['amount']}x {ing['name']} (${ing['unit_price']:.2f}, {ing['available_qty']} avail)")
        message += ", ".join(ing_list) + "\n"
        
        # Show products
        message += "Products: "
        prod_list = []
        for prod in opp['product_details']:
            prod_list.append(f"{prod['amount']}x {prod['name']} (${prod['unit_price']:.2f}, demand: {prod['buyer_demand']})")
        message += ", ".join(prod_list) + "\n"
        
        # Show constraints
        constraint_info = f"Max craftable: {opp['max_craftable_batches']} batches "
        if opp['max_batches_by_ingredients'] != opp['max_batches_by_demand']:
            constraint_info += f"(limited by {'ingredients' if opp['max_craftable_batches'] == opp['max_batches_by_ingredients'] else 'demand'}: "
            constraint_info += f"ingredients={opp['max_batches_by_ingredients']}, demand={opp['max_batches_by_demand']}) "
        constraint_info += f"(${opp['total_possible_profit']:.2f} total profit)\n\n"
        message += constraint_info
    
    if len(opportunities) > 20:
        message += f"...and {len(opportunities) - 20} more opportunities\n"
    
    return message

if __name__ == "__main__":
    print("Analyzing crafting opportunities...")
    
    if DEBUG:
        print("Fetching market prices...")
        market_prices = get_market_prices()
        print(f"Found market data for {len(market_prices)} items")
        
        # Show some example prices
        example_items = ['Iron Bar', 'Lumber', 'Board', 'Stone', 'Iron Axe']
        for item in example_items:
            if item in market_prices:
                buy_info = market_prices[item]['buy']
                sell_info = market_prices[item]['sell']
                buy_text = f"${buy_info['price']:.2f}" if buy_info else "None"
                sell_text = f"${sell_info['price']:.2f}" if sell_info else "None"
                print(f"  {item}: Buy={buy_text}, Sell={sell_text}")
            else:
                print(f"  {item}: No market data")
        
        print("\nFetching recipes...")
        recipe_data = fetch_recipes()
        if recipe_data:
            print(f"Found {len(recipe_data.get('Recipes', []))} recipes")
        else:
            print("No recipe data found")
        print()
    
    opportunities = analyze_crafting_profits()
    
    if DEBUG and not opportunities:
        print("No opportunities found. This could be because:")
        print("1. Market prices are missing for ingredients or products")
        print("2. All recipes have negative profit margins")
        print("3. Recipe parsing issues")
        print("\nTrying with lower profit threshold...")
    
    report = format_crafting_report(opportunities)
    print(report)