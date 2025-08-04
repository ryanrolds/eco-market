import json
import re
import requests
import os
from datetime import datetime
from generate_report import fetch_data, clean_store_name, get_item_emoji, ECO_BASE_URL

# Configuration
MIN_CRAFTING_PROFIT = 1  # Minimum profit for crafting opportunities
MIN_INGREDIENT_QUANTITY = 50  # Minimum quantity available for ingredients (be conservative)
MIN_RECIPE_BATCHES = 5  # Ensure we can make at least 5 batches of the recipe
DEBUG = True  # Show debug information

# Stores to filter out from buyers (won't sell to these stores)
EXCLUDED_BUYER_STORES = [
    "Low Hanging Fruit"
]

def fetch_recipes():
    """Fetch recipe data from API"""
    try:
        url = f"{ECO_BASE_URL}/api/v1/plugins/EcoPriceCalculator/recipes"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch recipe data ({url}): {e}")
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
    
    # Calculate best prices for each item and keep all buyers
    best_prices = {}
    for item, prices in market_prices.items():
        best_buy_price = None
        best_sell_price = None
        all_buyers = []
        
        if prices['buy_prices']:
            best_buy_price = min(prices['buy_prices'], key=lambda x: x['price'])
        
        if prices['sell_prices']:
            # Filter out excluded stores from buyers
            filtered_sell_prices = [p for p in prices['sell_prices'] if p['store'] not in EXCLUDED_BUYER_STORES]
            
            if filtered_sell_prices:
                best_sell_price = max(filtered_sell_prices, key=lambda x: x['price'])
                # Sort all buyers by price (highest first) for profit analysis
                all_buyers = sorted(filtered_sell_prices, key=lambda x: x['price'], reverse=True)
            else:
                best_sell_price = None
                all_buyers = []
        
        best_prices[item] = {
            'buy': best_buy_price,
            'sell': best_sell_price,
            'all_buyers': all_buyers
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
                if product_name in market_prices and market_prices[product_name]['all_buyers']:
                    all_buyers = market_prices[product_name]['all_buyers']
                    
                    # Check if there's any reasonable demand
                    total_demand = sum(buyer['qty'] for buyer in all_buyers)
                    if total_demand < MIN_RECIPE_BATCHES:
                        missing_products.append(f"{product_name} (insufficient demand: {total_demand})")
                    else:
                        # Use best buyer for base revenue calculation
                        best_buyer = all_buyers[0]  # Already sorted by price desc
                        total_revenue += best_buyer['price'] * amount_produced
                        
                        product_details.append({
                            'name': product_name,
                            'amount': amount_produced,
                            'best_price': best_buyer['price'],
                            'best_store': best_buyer['store'],
                            'best_demand': best_buyer['qty'],
                            'all_buyers': all_buyers,
                            'total_demand': total_demand
                        })
                else:
                    missing_products.append(f"{product_name} (no buyers)")
            
            # Skip if we can't sell the products
            if missing_products:
                continue
            
            # Calculate profit
            profit = total_revenue - ingredient_cost
            
            if profit > 0:
                # Filter for only mining and masonry skills
                skill_needs = recipe.get('SkillNeeds', [])
                required_skills = [skill['Skill'].lower() for skill in skill_needs]
                
                # Only show mining and masonry crafts
                if any(skill in ['mining', 'masonry'] for skill in required_skills) or not skill_needs:
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
                        'skill_needs': skill_needs,
                        'craft_time': craft_time,
                        'labor_cost': recipe.get('BaseLaborCost', 0)
                    })
    
    # Calculate total profit limited by both ingredient availability and product demand
    for opp in crafting_opportunities:
        # Max batches limited by ingredient availability
        max_batches_by_ingredients = min(ing['max_batches'] for ing in opp['ingredient_details'])
        
        # Calculate total profit by filling all buyer orders
        total_profit_all_buyers = 0
        max_batches_by_demand = 0
        
        for prod in opp['product_details']:
            # Sort buyers by price (highest first) and calculate cumulative profit
            remaining_ingredient_batches = max_batches_by_ingredients
            cumulative_batches_sold = 0
            
            for buyer in prod['all_buyers']:
                if remaining_ingredient_batches <= 0:
                    break
                
                # Calculate how many batches this buyer can take
                batches_buyer_wants = buyer['qty'] // prod['amount']
                batches_to_sell = min(remaining_ingredient_batches, batches_buyer_wants)
                
                if batches_to_sell > 0:
                    # Calculate profit for selling to this buyer
                    profit_per_unit = buyer['price'] - (opp['ingredient_cost'] / sum(p['amount'] for p in opp['product_details']))
                    profit_this_buyer = profit_per_unit * prod['amount'] * batches_to_sell
                    total_profit_all_buyers += profit_this_buyer
                    
                    remaining_ingredient_batches -= batches_to_sell
                    cumulative_batches_sold += batches_to_sell
            
            max_batches_by_demand = max(max_batches_by_demand, cumulative_batches_sold)
        
        # Use the total profit from filling all orders
        opp['total_possible_profit'] = total_profit_all_buyers
        opp['max_craftable_batches'] = min(max_batches_by_ingredients, max_batches_by_demand)
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
    message += f"Found {len(opportunities)} profitable crafting opportunities:\n"
    if EXCLUDED_BUYER_STORES:
        message += f"Excluded buyer stores: {', '.join(EXCLUDED_BUYER_STORES)}\n"
    message += "\n"
    
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
        
        # Show products with all buying stores and their actual contribution to total profit
        for prod in opp['product_details']:
            message += f"Product: {prod['amount']}x {prod['name']} (Total demand: {prod['total_demand']})\n"
            message += f"  Buyers ({len(prod['all_buyers'])} total, sorted by profit contribution):\n"
            
            # Calculate actual profit contribution from each buyer in order
            remaining_batches = opp['max_batches_by_ingredients']
            for buyer in prod['all_buyers']:
                if remaining_batches <= 0:
                    profit_per_unit = buyer['price'] - (opp['ingredient_cost'] / sum(p['amount'] for p in opp['product_details']))
                    message += f"    • {buyer['store']}: ${buyer['price']:.2f} (qty:{buyer['qty']}) - 0 batches (no ingredients left) - ${profit_per_unit:.2f}/unit\n"
                    continue
                    
                batches_buyer_wants = buyer['qty'] // prod['amount']
                batches_to_sell = min(remaining_batches, batches_buyer_wants)
                
                profit_per_unit = buyer['price'] - (opp['ingredient_cost'] / sum(p['amount'] for p in opp['product_details']))
                if batches_to_sell > 0:
                    actual_profit_contribution = profit_per_unit * prod['amount'] * batches_to_sell
                    message += f"    • {buyer['store']}: ${buyer['price']:.2f} (qty:{buyer['qty']}) - {batches_to_sell} batches → ${actual_profit_contribution:.2f} profit\n"
                    remaining_batches -= batches_to_sell
                else:
                    message += f"    • {buyer['store']}: ${buyer['price']:.2f} (qty:{buyer['qty']}) - 0 batches (insufficient demand) - ${profit_per_unit:.2f}/unit\n"
        
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
    
    # Debug output - show which crafts are considered mining and masonry
    print("\n" + "="*60)
    print("DEBUG: Mining and Masonry Crafts Analysis")
    print("="*60)
    print(f"Excluded buyer stores: {', '.join(EXCLUDED_BUYER_STORES)}")
    print("="*60)
    
    recipe_data = fetch_recipes()
    if recipe_data:
        mining_crafts = []
        masonry_crafts = []
        no_skill_crafts = []
        other_skill_crafts = []
        
        for recipe in recipe_data.get('Recipes', []):
            recipe_name = recipe['Key']
            skill_needs = recipe.get('SkillNeeds', [])
            
            if not skill_needs:
                no_skill_crafts.append(recipe_name)
            else:
                required_skills = [skill['Skill'].lower() for skill in skill_needs]
                if 'mining' in required_skills:
                    mining_crafts.append((recipe_name, [f"{s['Skill']} Lv.{s['Level']}" for s in skill_needs]))
                elif 'masonry' in required_skills:
                    masonry_crafts.append((recipe_name, [f"{s['Skill']} Lv.{s['Level']}" for s in skill_needs]))
                else:
                    other_skill_crafts.append((recipe_name, [f"{s['Skill']} Lv.{s['Level']}" for s in skill_needs]))
        
        print(f"\nMINING CRAFTS ({len(mining_crafts)}):")
        for craft, skills in mining_crafts[:10]:  # Show first 10
            print(f"  • {craft} - Skills: {', '.join(skills)}")
        if len(mining_crafts) > 10:
            print(f"  ... and {len(mining_crafts) - 10} more")
        
        print(f"\nMASONRY CRAFTS ({len(masonry_crafts)}):")
        for craft, skills in masonry_crafts[:10]:  # Show first 10
            print(f"  • {craft} - Skills: {', '.join(skills)}")
        if len(masonry_crafts) > 10:
            print(f"  ... and {len(masonry_crafts) - 10} more")
        
        print(f"\nNO SKILL CRAFTS ({len(no_skill_crafts)}):")
        for craft in no_skill_crafts[:10]:  # Show first 10
            print(f"  • {craft}")
        if len(no_skill_crafts) > 10:
            print(f"  ... and {len(no_skill_crafts) - 10} more")
        
        print(f"\nOTHER SKILL CRAFTS ({len(other_skill_crafts)}) - NOT SHOWN:")
        sample_skills = set()
        for craft, skills in other_skill_crafts:
            for skill in skills:
                sample_skills.add(skill.split(' ')[0])  # Get skill name without level
        print(f"  Sample skills: {', '.join(sorted(list(sample_skills))[:10])}")
        
        total_filtered = len(mining_crafts) + len(masonry_crafts) + len(no_skill_crafts)
        print(f"\nFILTER SUMMARY:")
        print(f"  Total recipes: {len(recipe_data.get('Recipes', []))}")
        print(f"  Recipes shown (mining/masonry/no-skill): {total_filtered}")
        print(f"  Recipes filtered out: {len(other_skill_crafts)}")
    else:
        print("Could not fetch recipe data for debug analysis")