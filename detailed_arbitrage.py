#!/usr/bin/env python3
"""
Detailed Arbitrage Analysis
Focus on the most profitable and actionable arbitrage opportunities
"""

import json
import re
import requests
from collections import defaultdict
from typing import Dict, List, Tuple, Any

def clean_store_name(name):
    """Remove color tags from store names"""
    return re.sub(r'<color=[^>]*>|</color>', '', name)

def load_data(filename: str = None) -> Dict:
    """Load and parse the JSON data from API or file"""
    try:
        print("Fetching data from API...")
        response = requests.get("http://144.217.255.182:3001/api/v1/plugins/EcoPriceCalculator/stores", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch from API ({e}), using local file...")
        filename = filename or 'stores_data.json'
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("No local file found. Please ensure stores_data.json exists or API is accessible.")
            exit(1)

def find_detailed_arbitrage(data: Dict) -> List[Dict]:
    """Find detailed arbitrage opportunities with thorough analysis"""
    
    # Dictionary to store all offers for each item
    item_offers = defaultdict(list)
    
    # Process all stores and their offers
    for store in data.get('Stores', []):
        store_name = clean_store_name(store['Name'])
        balance = store.get('Balance', 0)
        currency = store.get('CurrencyName', 'Unknown')
        enabled = store.get('Enabled', False)
        
        for offer in store.get('AllOffers', []):
            item_name = offer['ItemName']
            price = offer['Price']
            quantity = offer['Quantity']
            is_buying = offer['Buying']
            
            # Only consider valid offers with quantity > 0
            if enabled and quantity > 0 and 0 < price < 999999.0:
                offer_data = {
                    'store': store_name,
                    'price': price,
                    'quantity': quantity,
                    'is_buying': is_buying,
                    'balance': balance,
                    'currency': currency
                }
                
                item_offers[item_name].append(offer_data)
    
    arbitrage_opportunities = []
    
    for item_name, offers in item_offers.items():
        buy_offers = [o for o in offers if o['is_buying']]
        sell_offers = [o for o in offers if not o['is_buying']]
        
        if buy_offers and sell_offers:
            # Sort to find best prices
            buy_offers.sort(key=lambda x: x['price'], reverse=True)  # Highest buy prices first
            sell_offers.sort(key=lambda x: x['price'])  # Lowest sell prices first
            
            for sell_offer in sell_offers:
                for buy_offer in buy_offers:
                    profit_per_unit = buy_offer['price'] - sell_offer['price']
                    
                    if profit_per_unit > 0:
                        max_quantity = min(sell_offer['quantity'], buy_offer['quantity'])
                        total_profit = profit_per_unit * max_quantity
                        profit_margin = (profit_per_unit / sell_offer['price']) * 100
                        
                        # Calculate investment required
                        investment = sell_offer['price'] * max_quantity
                        roi = (total_profit / investment) * 100 if investment > 0 else 0
                        
                        arbitrage_opportunities.append({
                            'item': item_name,
                            'buy_from_store': sell_offer['store'],
                            'buy_price': sell_offer['price'],
                            'buy_quantity_available': sell_offer['quantity'],
                            'sell_to_store': buy_offer['store'],
                            'sell_price': buy_offer['price'],
                            'sell_quantity_demand': buy_offer['quantity'],
                            'profit_per_unit': profit_per_unit,
                            'profit_margin_percent': profit_margin,
                            'max_trade_quantity': max_quantity,
                            'total_profit': total_profit,
                            'investment_required': investment,
                            'roi_percent': roi,
                            'seller_balance': sell_offer['balance'],
                            'buyer_balance': buy_offer['balance']
                        })
    
    # Sort by total profit potential
    arbitrage_opportunities.sort(key=lambda x: x['total_profit'], reverse=True)
    return arbitrage_opportunities

def categorize_arbitrage_opportunities(opportunities: List[Dict]) -> Dict[str, List[Dict]]:
    """Categorize arbitrage opportunities by profitability and risk"""
    
    categories = {
        'high_profit_high_volume': [],
        'high_roi_opportunities': [],
        'low_risk_steady_profit': [],
        'bulk_trade_opportunities': []
    }
    
    for op in opportunities:
        # High profit, high volume (>$50 total profit)
        if op['total_profit'] >= 50:
            categories['high_profit_high_volume'].append(op)
        
        # High ROI (>50% return)
        if op['roi_percent'] >= 50:
            categories['high_roi_opportunities'].append(op)
        
        # Low risk, steady profit (investment < $20, profit > $5)
        if op['investment_required'] <= 20 and op['total_profit'] >= 5:
            categories['low_risk_steady_profit'].append(op)
        
        # Bulk trade opportunities (can trade >100 units)
        if op['max_trade_quantity'] >= 100:
            categories['bulk_trade_opportunities'].append(op)
    
    return categories

def print_detailed_analysis(opportunities: List[Dict], categories: Dict[str, List[Dict]]):
    """Print detailed arbitrage analysis"""
    
    print("ARBITRAGE ANALYSIS")
    print("=" * 50)
    
    # Top Overall Opportunities
    print("\nTOP 10 MOST PROFITABLE:")
    for i, op in enumerate(opportunities[:10], 1):
        print(f"{i:2d}. {op['item']}")
        print(f"    BUY:  {op['buy_from_store']} @ ${op['buy_price']:.2f} (qty: {op['buy_quantity_available']})")
        print(f"    SELL: {op['sell_to_store']} @ ${op['sell_price']:.2f} (qty: {op['sell_quantity_demand']})")
        print(f"    PROFIT: ${op['total_profit']:.2f} ({op['profit_margin_percent']:.1f}% margin, {op['roi_percent']:.1f}% ROI)")
        print()
    
    # High Profit, High Volume
    print("\nHIGH PROFIT (>$50):")
    if categories['high_profit_high_volume']:
        for i, op in enumerate(categories['high_profit_high_volume'][:5], 1):
            print(f"{i}. {op['item']}: ${op['buy_price']:.2f} -> ${op['sell_price']:.2f} (${op['total_profit']:.2f} profit)")
    else:
        print("None found.")
    
    # High ROI Opportunities
    print("\nHIGH ROI (>50%):")
    if categories['high_roi_opportunities']:
        for i, op in enumerate(categories['high_roi_opportunities'][:5], 1):
            print(f"{i}. {op['item']}: {op['roi_percent']:.1f}% ROI (${op['total_profit']:.2f} profit)")
    else:
        print("None found.")
    
    # Low Risk, Steady Profit
    print("\nLOW RISK:")
    if categories['low_risk_steady_profit']:
        for i, op in enumerate(categories['low_risk_steady_profit'][:5], 1):
            print(f"{i}. {op['item']}: ${op['investment_required']:.2f} -> ${op['total_profit']:.2f}")
    else:
        print("None found.")
    
    # Bulk Trade Opportunities
    print("\nBULK TRADE (>100 units):")
    if categories['bulk_trade_opportunities']:
        for i, op in enumerate(categories['bulk_trade_opportunities'][:5], 1):
            print(f"{i}. {op['item']}: {op['max_trade_quantity']} units (${op['total_profit']:.2f} profit)")
    else:
        print("None found.")

def find_free_items_arbitrage(data: Dict) -> List[Dict]:
    """Find items being sold for free that can be sold elsewhere"""
    free_arbitrage = []
    
    for store in data.get('Stores', []):
        store_name = clean_store_name(store['Name'])
        enabled = store.get('Enabled', False)
        
        if not enabled:
            continue
            
        for offer in store.get('AllOffers', []):
            item_name = offer['ItemName']
            price = offer['Price']
            quantity = offer['Quantity']
            is_buying = offer['Buying']
            
            # Find items being sold for free with quantity > 0
            if not is_buying and price == 0.0 and quantity > 0:
                # Check if anyone is buying this item for > 0
                for other_store in data.get('Stores', []):
                    other_store_name = clean_store_name(other_store['Name'])
                    if other_store_name == store_name or not other_store.get('Enabled', False):
                        continue
                        
                    for other_offer in other_store.get('AllOffers', []):
                        if (other_offer['ItemName'] == item_name and 
                            other_offer['Buying'] and 
                            other_offer['Price'] > 0 and 
                            other_offer['Quantity'] > 0):
                            
                            max_quantity = min(quantity, other_offer['Quantity'])
                            total_profit = other_offer['Price'] * max_quantity
                            
                            free_arbitrage.append({
                                'item': item_name,
                                'free_from': store_name,
                                'free_quantity': quantity,
                                'sell_to': other_store_name,
                                'sell_price': other_offer['Price'],
                                'sell_demand': other_offer['Quantity'],
                                'max_trade': max_quantity,
                                'total_profit': total_profit
                            })
    
    free_arbitrage.sort(key=lambda x: x['total_profit'], reverse=True)
    return free_arbitrage

def main():
    """Main analysis function"""
    try:
        # Load data
        data = load_data()
        
        # Find arbitrage opportunities
        opportunities = find_detailed_arbitrage(data)
        
        # Categorize opportunities
        categories = categorize_arbitrage_opportunities(opportunities)
        
        # Print detailed analysis
        print_detailed_analysis(opportunities, categories)
        
        # Find free items arbitrage
        free_arbitrage = find_free_items_arbitrage(data)
        
        if free_arbitrage:
            print("\nFREE ITEMS ARBITRAGE:")
            for i, op in enumerate(free_arbitrage[:5], 1):
                print(f"{i}. {op['item']}: FREE from {op['free_from']} -> ${op['sell_price']:.2f} at {op['sell_to']} (${op['total_profit']:.2f} profit)")
        
        print(f"\nSUMMARY: {len(opportunities)} total opportunities")
        print(f"High profit (>$50): {len(categories['high_profit_high_volume'])}")
        print(f"High ROI (>50%): {len(categories['high_roi_opportunities'])}")
        print(f"Low risk: {len(categories['low_risk_steady_profit'])}")
        print(f"Bulk trade: {len(categories['bulk_trade_opportunities'])}")
        print(f"Free items: {len(free_arbitrage)}")
        
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()