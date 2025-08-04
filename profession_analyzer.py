import json
import re
import requests
import os
from datetime import datetime
from collections import defaultdict
from generate_report import fetch_data, clean_store_name, get_item_emoji, ECO_BASE_URL

# Configuration
MIN_PROFESSION_PROFIT = 10  # Minimum total profit to include profession in analysis
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
                # Filter out excluded stores from buyers
                if store_name not in EXCLUDED_BUYER_STORES:
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

def analyze_profession_profits():
    """Analyze crafting opportunities by profession"""
    recipe_data = fetch_recipes()
    if not recipe_data:
        return {}
    
    market_prices = get_market_prices()
    if not market_prices:
        return {}
    
    # Group opportunities by profession
    profession_opportunities = defaultdict(list)
    
    for recipe in recipe_data.get('Recipes', []):
        recipe_name = recipe['Key']
        
        # Skip skill books and research recipes
        if any(word in recipe_name.lower() for word in ['skill book', 'research paper']):
            continue
        
        for variant in recipe.get('Variants', []):
            variant_name = variant['Name']
            ingredients = variant.get('Ingredients', [])
            products = variant.get('Products', [])
            skill_needs = recipe.get('SkillNeeds', [])
            
            if not ingredients or not products or not skill_needs:
                continue
            
            # Get primary profession (first skill listed)
            primary_profession = skill_needs[0]['Skill']
            
            # Calculate ingredient costs (ignore availability, assume we can get ingredients)
            ingredient_cost = 0
            missing_ingredients = []
            ingredient_details = []
            
            for ingredient in ingredients:
                ingredient_name = ingredient['Name'] if ingredient['IsSpecificItem'] else ingredient.get('Tag', 'Unknown')
                amount_needed = ingredient['Ammount']
                
                # Handle tagged ingredients
                if not ingredient['IsSpecificItem'] and ingredient.get('Tag'):
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
                            ingredient_name = cheapest_item
                            ingredient_cost += cheapest_price * amount_needed
                            ingredient_details.append({
                                'name': ingredient_name,
                                'amount': amount_needed,
                                'unit_price': cheapest_price,
                                'total_cost': cheapest_price * amount_needed,
                                'store': market_prices[cheapest_item]['buy']['store']
                            })
                        else:
                            missing_ingredients.append(f"{ingredient['Tag']} (tag)")
                    else:
                        missing_ingredients.append(f"{ingredient['Tag']} (unknown tag)")
                else:
                    # Specific item
                    if ingredient_name in market_prices and market_prices[ingredient_name]['buy']:
                        unit_price = market_prices[ingredient_name]['buy']['price']
                        ingredient_cost += unit_price * amount_needed
                        ingredient_details.append({
                            'name': ingredient_name,
                            'amount': amount_needed,
                            'unit_price': unit_price,
                            'total_cost': unit_price * amount_needed,
                            'store': market_prices[ingredient_name]['buy']['store']
                        })
                    else:
                        missing_ingredients.append(f"{ingredient_name} (no sellers)")
            
            # Skip only if we can't price ingredients at all
            if missing_ingredients:
                continue
            
            # Calculate product revenue
            total_revenue = 0
            product_details = []
            missing_products = []
            
            for product in products:
                product_name = product['Name']
                amount_produced = product['Ammount']
                
                if product_name in market_prices and market_prices[product_name]['all_buyers']:
                    all_buyers = market_prices[product_name]['all_buyers']
                    
                    total_demand = sum(buyer['qty'] for buyer in all_buyers)
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
            
            # Skip if can't sell products
            if missing_products:
                continue
            
            # Calculate profit
            profit = total_revenue - ingredient_cost
            
            if profit > 0:
                margin = (profit / ingredient_cost * 100) if ingredient_cost > 0 else 0
                craft_time = recipe.get('BaseCraftTime', 1)
                profit_per_second = profit / max(craft_time, 0.1)
                
                # Calculate total profit based purely on demand (ignore ingredient availability)
                total_profit_all_buyers = 0
                
                for prod in product_details:
                    for buyer in prod['all_buyers']:
                        batches_buyer_wants = buyer['qty'] // prod['amount']
                        
                        if batches_buyer_wants > 0:
                            profit_per_unit = buyer['price'] - (ingredient_cost / sum(p['amount'] for p in product_details))
                            profit_this_buyer = profit_per_unit * prod['amount'] * batches_buyer_wants
                            total_profit_all_buyers += profit_this_buyer
                
                # Calculate total theoretical demand (all buyers combined)
                total_theoretical_demand = sum(prod['total_demand'] for prod in product_details)
                
                opportunity = {
                    'recipe': recipe_name,
                    'variant': variant_name,
                    'ingredient_cost': ingredient_cost,
                    'revenue': total_revenue,
                    'profit': profit,
                    'margin': margin,
                    'profit_per_second': profit_per_second,
                    'total_possible_profit': total_profit_all_buyers,
                    'total_theoretical_demand': total_theoretical_demand,
                    'ingredient_details': ingredient_details,
                    'product_details': product_details,
                    'crafting_table': recipe.get('CraftingTable', 'Unknown'),
                    'skill_needs': skill_needs,
                    'craft_time': craft_time,
                    'labor_cost': recipe.get('BaseLaborCost', 0)
                }
                
                profession_opportunities[primary_profession].append(opportunity)
    
    return profession_opportunities

def format_profession_report(profession_opportunities):
    """Format profession analysis into a readable report"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = f"**Profession Profit Analysis Report** - {timestamp}\n"
    if EXCLUDED_BUYER_STORES:
        message += f"Excluded buyer stores: {', '.join(EXCLUDED_BUYER_STORES)}\n"
    message += "\n"
    
    message += "**METHODOLOGY:**\n"
    message += "This analysis calculates the theoretical maximum profit potential for each profession\n"
    message += "based purely on market demand, ignoring ingredient availability constraints.\n"
    message += "• Ingredient costs: Uses cheapest available market prices\n"
    message += "• Profit calculation: (Sell price - ingredient cost) × total demand from all buyers\n"
    message += "• Total potential: Sum of profits from filling ALL buyer orders for each recipe\n"
    message += "• Ranking: Professions ranked by combined profit potential across all their recipes\n"
    message += "\n"
    
    if not profession_opportunities:
        message += "No profitable crafting opportunities found for any profession."
        return message
    
    # Calculate total profit potential for each profession
    profession_totals = {}
    for profession, opportunities in profession_opportunities.items():
        # Filter opportunities by minimum profit threshold
        profitable_opps = [opp for opp in opportunities if opp['total_possible_profit'] >= MIN_PROFESSION_PROFIT]
        
        if profitable_opps:
            total_profit = sum(opp['total_possible_profit'] for opp in profitable_opps)
            avg_profit_per_recipe = total_profit / len(profitable_opps)
            best_opportunity = max(profitable_opps, key=lambda x: x['total_possible_profit'])
            
            profession_totals[profession] = {
                'total_profit': total_profit,
                'recipe_count': len(profitable_opps),
                'avg_profit_per_recipe': avg_profit_per_recipe,
                'best_opportunity': best_opportunity,
                'all_opportunities': profitable_opps
            }
    
    # Sort professions by total profit potential
    sorted_professions = sorted(profession_totals.items(), key=lambda x: x[1]['total_profit'], reverse=True)
    
    message += f"**PROFESSION RANKINGS** (by total profit potential):\n"
    message += "=" * 60 + "\n\n"
    
    for rank, (profession, data) in enumerate(sorted_professions, 1):
        emoji = get_profession_emoji(profession)
        
        # Highlight top professions
        if data['total_profit'] >= 1000:
            profit_text = f"🚨 ${data['total_profit']:.2f} TOTAL POTENTIAL 🚨"
        elif data['total_profit'] >= 500:
            profit_text = f"⭐ ${data['total_profit']:.2f} TOTAL POTENTIAL ⭐"
        else:
            profit_text = f"${data['total_profit']:.2f} TOTAL POTENTIAL"
        
        message += f"**{rank}. {emoji} {profession}** - {profit_text}\n"
        message += f"Profitable recipes: {data['recipe_count']} | Avg profit per recipe: ${data['avg_profit_per_recipe']:.2f}\n"
        message += f"Best opportunity: {data['best_opportunity']['variant']} (${data['best_opportunity']['total_possible_profit']:.2f})\n"
        
        # Show top 3 opportunities for this profession
        top_opportunities = sorted(data['all_opportunities'], key=lambda x: x['total_possible_profit'], reverse=True)[:3]
        message += "Top opportunities (based on demand):\n"
        for i, opp in enumerate(top_opportunities, 1):
            opp_emoji = get_item_emoji(opp['variant'])
            total_demand = opp['total_theoretical_demand']
            message += f"  {i}. {opp_emoji} {opp['variant']}: ${opp['total_possible_profit']:.2f} (demand: {total_demand} units, ${opp['profit']:.2f}/unit)\n"
        
        message += "\n"
    
    # Summary statistics
    total_all_professions = sum(data['total_profit'] for _, data in sorted_professions)
    message += f"**SUMMARY:**\n"
    message += f"Total analyzed professions: {len(sorted_professions)}\n"
    message += f"Combined profit potential: ${total_all_professions:.2f}\n"
    message += f"Most profitable profession: {sorted_professions[0][0]} (${sorted_professions[0][1]['total_profit']:.2f})\n"
    
    return message

def get_profession_emoji(profession):
    """Get emoji for profession"""
    profession_lower = profession.lower()
    
    if 'mining' in profession_lower:
        return '⛏️'
    elif 'masonry' in profession_lower:
        return '🧱'
    elif 'carpentry' in profession_lower or 'wood' in profession_lower:
        return '🪚'
    elif 'smithing' in profession_lower or 'metal' in profession_lower:
        return '🔨'
    elif 'tailoring' in profession_lower or 'fabric' in profession_lower:
        return '🧵'
    elif 'cooking' in profession_lower or 'culinary' in profession_lower:
        return '👨‍🍳'
    elif 'farming' in profession_lower or 'agriculture' in profession_lower:
        return '🌾'
    elif 'hunting' in profession_lower:
        return '🏹'
    elif 'gathering' in profession_lower:
        return '🌿'
    elif 'engineering' in profession_lower or 'mechanic' in profession_lower:
        return '⚙️'
    elif 'glassworking' in profession_lower:
        return '🔮'
    elif 'pottery' in profession_lower:
        return '🏺'
    else:
        return '🛠️'

if __name__ == "__main__":
    print("Analyzing profession profit potential...")
    
    if DEBUG:
        print("Fetching market prices...")
        market_prices = get_market_prices()
        print(f"Found market data for {len(market_prices)} items")
        
        print("\nFetching recipes...")
        recipe_data = fetch_recipes()
        if recipe_data:
            print(f"Found {len(recipe_data.get('Recipes', []))} recipes")
        else:
            print("No recipe data found")
        print()
    
    profession_opportunities = analyze_profession_profits()
    
    if DEBUG:
        print(f"Found opportunities for {len(profession_opportunities)} professions:")
        for profession, opps in profession_opportunities.items():
            profitable_opps = [opp for opp in opps if opp['total_possible_profit'] >= MIN_PROFESSION_PROFIT]
            print(f"  {profession}: {len(profitable_opps)} profitable opportunities")
        print()
    
    report = format_profession_report(profession_opportunities)
    print(report)