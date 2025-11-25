"""
Position Reconciliation Error Alerts System - Standalone Version
================================================================
A simplified, single-file reconciliation system that runs out of the box.

To run: python reconciliation_standalone.py

Author: Rahul Yatagiri
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from enum import Enum
import os
import warnings
warnings.filterwarnings('ignore')


# =============================================================================
# ENUMS AND CONFIGURATION
# =============================================================================

class BreakType(Enum):
    QUANTITY_MISMATCH = "Quantity Mismatch"
    PRICE_MISMATCH = "Price Mismatch"
    MARKET_VALUE_MISMATCH = "Market Value Mismatch"
    MISSING_IN_SOURCE = "Missing in Source"
    MISSING_IN_TARGET = "Missing in Target"


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Tolerance configuration
TOLERANCES = {
    'quantity_pct': 1.0,        # 1% tolerance for quantity
    'price_pct': 0.1,           # 0.1% for price
    'market_value_pct': 2.0,    # 2% for market value
    'min_threshold': 100        # $100 de minimis
}


# =============================================================================
# SAMPLE DATA GENERATOR
# =============================================================================

def generate_sample_data() -> tuple:
    """Generate sample position files for Internal System and Prime Broker"""
    
    print("📊 Generating sample position data...")
    
    # Stock universe
    stocks = [
        {'symbol': 'AAPL', 'price': 178.50},
        {'symbol': 'GOOGL', 'price': 141.25},
        {'symbol': 'MSFT', 'price': 378.90},
        {'symbol': 'AMZN', 'price': 178.25},
        {'symbol': 'META', 'price': 505.75},
        {'symbol': 'NVDA', 'price': 875.50},
        {'symbol': 'TSLA', 'price': 248.75},
        {'symbol': 'JPM', 'price': 198.40},
        {'symbol': 'V', 'price': 278.60},
        {'symbol': 'JNJ', 'price': 156.80}
    ]
    
    accounts = ['HEDGE_FUND_01', 'HEDGE_FUND_02']
    trade_date = datetime.now() - timedelta(days=2)
    settle_date = datetime.now()
    
    np.random.seed(42)
    
    # Generate Internal System positions
    internal_positions = []
    for stock in stocks:
        for account in accounts:
            qty = np.random.randint(1000, 15000)
            price = stock['price']
            internal_positions.append({
                'symbol': stock['symbol'],
                'account_id': account,
                'quantity': qty,
                'price': price,
                'market_value': round(qty * price, 2),
                'currency': 'USD',
                'trade_date': trade_date.strftime('%Y-%m-%d'),
                'settle_date': settle_date.strftime('%Y-%m-%d')
            })
    
    internal_df = pd.DataFrame(internal_positions)
    
    # Generate Prime Broker positions with intentional breaks
    pb_positions = []
    for i, row in internal_df.iterrows():
        pb_row = row.copy()
        
        # Introduce quantity breaks (~20% of positions)
        if np.random.random() < 0.20:
            variance = np.random.randint(-500, 500)
            pb_row['quantity'] = row['quantity'] + variance
            pb_row['market_value'] = round(pb_row['quantity'] * pb_row['price'], 2)
        
        # Introduce price breaks (~15% of positions)
        if np.random.random() < 0.15:
            price_change = row['price'] * np.random.uniform(-0.03, 0.03)
            pb_row['price'] = round(row['price'] + price_change, 2)
            pb_row['market_value'] = round(pb_row['quantity'] * pb_row['price'], 2)
        
        pb_positions.append(pb_row.to_dict())
    
    # Add an extra position in PB (missing in internal)
    pb_positions.append({
        'symbol': 'NFLX',
        'account_id': 'HEDGE_FUND_01',
        'quantity': 2500,
        'price': 625.00,
        'market_value': 1562500.00,
        'currency': 'USD',
        'trade_date': trade_date.strftime('%Y-%m-%d'),
        'settle_date': settle_date.strftime('%Y-%m-%d')
    })
    
    pb_df = pd.DataFrame(pb_positions)
    
    print(f"   ✓ Generated {len(internal_df)} internal positions")
    print(f"   ✓ Generated {len(pb_df)} prime broker positions")
    
    return internal_df, pb_df


# =============================================================================
# RECONCILIATION ENGINE
# =============================================================================

def calculate_severity(variance: float, variance_pct: float) -> Severity:
    """Determine break severity based on dollar amount and percentage"""
    abs_var = abs(variance)
    abs_pct = abs(variance_pct)
    
    if abs_var > 100000 or abs_pct > 10:
        return Severity.CRITICAL
    elif abs_var > 50000 or abs_pct > 5:
        return Severity.HIGH
    elif abs_var > 10000 or abs_pct > 2:
        return Severity.MEDIUM
    else:
        return Severity.LOW


def reconcile_positions(internal_df: pd.DataFrame, pb_df: pd.DataFrame) -> List[Dict]:
    """
    Compare positions between Internal System and Prime Broker
    Returns list of breaks/exceptions found
    """
    
    print("\n🔍 Running reconciliation...")
    
    breaks = []
    
    # Create position keys for matching
    internal_df['pos_key'] = internal_df['symbol'] + '|' + internal_df['account_id']
    pb_df['pos_key'] = pb_df['symbol'] + '|' + pb_df['account_id']
    
    internal_keys = set(internal_df['pos_key'])
    pb_keys = set(pb_df['pos_key'])
    
    # Check for missing positions
    missing_in_pb = internal_keys - pb_keys
    missing_in_internal = pb_keys - internal_keys
    
    for key in missing_in_pb:
        pos = internal_df[internal_df['pos_key'] == key].iloc[0]
        breaks.append({
            'break_id': f"BRK-{len(breaks)+1:04d}",
            'break_type': BreakType.MISSING_IN_TARGET.value,
            'severity': calculate_severity(pos['market_value'], 100).value,
            'symbol': pos['symbol'],
            'account_id': pos['account_id'],
            'internal_value': pos['market_value'],
            'pb_value': 0,
            'variance': pos['market_value'],
            'variance_pct': 100.0,
            'details': f"Position exists in Internal but not in Prime Broker"
        })
    
    for key in missing_in_internal:
        pos = pb_df[pb_df['pos_key'] == key].iloc[0]
        breaks.append({
            'break_id': f"BRK-{len(breaks)+1:04d}",
            'break_type': BreakType.MISSING_IN_SOURCE.value,
            'severity': calculate_severity(pos['market_value'], 100).value,
            'symbol': pos['symbol'],
            'account_id': pos['account_id'],
            'internal_value': 0,
            'pb_value': pos['market_value'],
            'variance': -pos['market_value'],
            'variance_pct': -100.0,
            'details': f"Position exists in Prime Broker but not in Internal"
        })
    
    # Compare matching positions
    common_keys = internal_keys & pb_keys
    
    for key in common_keys:
        int_pos = internal_df[internal_df['pos_key'] == key].iloc[0]
        pb_pos = pb_df[pb_df['pos_key'] == key].iloc[0]
        
        # Check quantity
        qty_var = int_pos['quantity'] - pb_pos['quantity']
        if int_pos['quantity'] != 0:
            qty_var_pct = (qty_var / int_pos['quantity']) * 100
        else:
            qty_var_pct = 0
            
        if abs(qty_var_pct) > TOLERANCES['quantity_pct']:
            dollar_impact = abs(qty_var * int_pos['price'])
            breaks.append({
                'break_id': f"BRK-{len(breaks)+1:04d}",
                'break_type': BreakType.QUANTITY_MISMATCH.value,
                'severity': calculate_severity(dollar_impact, qty_var_pct).value,
                'symbol': int_pos['symbol'],
                'account_id': int_pos['account_id'],
                'internal_value': int_pos['quantity'],
                'pb_value': pb_pos['quantity'],
                'variance': qty_var,
                'variance_pct': round(qty_var_pct, 2),
                'details': f"Quantity: Internal={int_pos['quantity']:,.0f} vs PB={pb_pos['quantity']:,.0f}"
            })
        
        # Check price
        price_var = int_pos['price'] - pb_pos['price']
        if int_pos['price'] != 0:
            price_var_pct = (price_var / int_pos['price']) * 100
        else:
            price_var_pct = 0
            
        if abs(price_var_pct) > TOLERANCES['price_pct']:
            dollar_impact = abs(price_var * int_pos['quantity'])
            breaks.append({
                'break_id': f"BRK-{len(breaks)+1:04d}",
                'break_type': BreakType.PRICE_MISMATCH.value,
                'severity': calculate_severity(dollar_impact, price_var_pct).value,
                'symbol': int_pos['symbol'],
                'account_id': int_pos['account_id'],
                'internal_value': int_pos['price'],
                'pb_value': pb_pos['price'],
                'variance': round(price_var, 2),
                'variance_pct': round(price_var_pct, 2),
                'details': f"Price: Internal=${int_pos['price']:,.2f} vs PB=${pb_pos['price']:,.2f}"
            })
        
        # Check market value
        mv_var = int_pos['market_value'] - pb_pos['market_value']
        if int_pos['market_value'] != 0:
            mv_var_pct = (mv_var / int_pos['market_value']) * 100
        else:
            mv_var_pct = 0
            
        if abs(mv_var_pct) > TOLERANCES['market_value_pct'] and abs(mv_var) > TOLERANCES['min_threshold']:
            breaks.append({
                'break_id': f"BRK-{len(breaks)+1:04d}",
                'break_type': BreakType.MARKET_VALUE_MISMATCH.value,
                'severity': calculate_severity(mv_var, mv_var_pct).value,
                'symbol': int_pos['symbol'],
                'account_id': int_pos['account_id'],
                'internal_value': int_pos['market_value'],
                'pb_value': pb_pos['market_value'],
                'variance': round(mv_var, 2),
                'variance_pct': round(mv_var_pct, 2),
                'details': f"MV: Internal=${int_pos['market_value']:,.2f} vs PB=${pb_pos['market_value']:,.2f}"
            })
    
    print(f"   ✓ Found {len(breaks)} breaks/exceptions")
    
    return breaks


# =============================================================================
# ALERTING SYSTEM
# =============================================================================

def generate_alerts(breaks: List[Dict]) -> None:
    """Generate alerts for critical and high severity breaks"""
    
    critical_high = [b for b in breaks if b['severity'] in ['CRITICAL', 'HIGH']]
    
    if not critical_high:
        print("\n✅ No critical or high severity breaks - no immediate alerts needed")
        return
    
    print(f"\n🚨 ALERT: {len(critical_high)} Critical/High severity breaks detected!")
    print("=" * 70)
    
    # Slack message format (would send via webhook in production)
    slack_message = f"""
*🚨 POSITION RECONCILIATION ALERT*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Breaks Requiring Attention: {len(critical_high)}

"""
    for brk in critical_high[:10]:
        slack_message += f"""
*[{brk['severity']}]* {brk['symbol']} ({brk['account_id']})
• Type: {brk['break_type']}
• Variance: ${abs(brk['variance']):,.2f} ({brk['variance_pct']:+.2f}%)
• {brk['details']}
"""
    
    print(slack_message)
    
    # Email format
    print("\n📧 Email Alert Preview:")
    print("-" * 50)
    print(f"To: ops-team@hedgefund.com, risk@hedgefund.com")
    print(f"Subject: [URGENT] Position Recon: {len(critical_high)} Breaks Detected")
    print(f"Body: {len(critical_high)} position breaks require immediate attention...")
    print("-" * 50)


# =============================================================================
# REPORT GENERATOR
# =============================================================================

def generate_report(breaks: List[Dict], internal_df: pd.DataFrame, pb_df: pd.DataFrame) -> str:
    """Generate comprehensive reconciliation report"""
    
    report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    POSITION RECONCILIATION REPORT                             ║
║                    {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^40}                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

EXECUTIVE SUMMARY
─────────────────
Total Internal Positions:     {len(internal_df):>10,}
Total Prime Broker Positions: {len(pb_df):>10,}
Total Breaks Identified:      {len(breaks):>10,}

BREAKS BY SEVERITY
──────────────────
"""
    
    severity_counts = {}
    for brk in breaks:
        sev = brk['severity']
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        count = severity_counts.get(sev, 0)
        bar = '█' * min(count * 2, 30)
        report += f"  {sev:10} : {count:>3} {bar}\n"
    
    report += """
BREAKS BY TYPE
──────────────
"""
    
    type_counts = {}
    for brk in breaks:
        bt = brk['break_type']
        type_counts[bt] = type_counts.get(bt, 0) + 1
    
    for bt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        report += f"  {bt:30} : {count:>3}\n"
    
    total_variance = sum(abs(b['variance']) for b in breaks if 'market_value' in b['break_type'].lower() or 'missing' in b['break_type'].lower())
    report += f"""
TOTAL MARKET VALUE VARIANCE: ${total_variance:>15,.2f}

DETAILED BREAK LIST
───────────────────
"""
    
    # Sort by severity and variance
    severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    sorted_breaks = sorted(breaks, key=lambda x: (severity_order.get(x['severity'], 4), -abs(x.get('variance', 0))))
    
    for brk in sorted_breaks:
        report += f"""
┌─ [{brk['severity']:8}] {brk['break_id']} ─────────────────────────────────
│  Symbol:      {brk['symbol']}
│  Account:     {brk['account_id']}
│  Type:        {brk['break_type']}
│  Internal:    {brk['internal_value']:>15,.2f}
│  Prime Broker:{brk['pb_value']:>15,.2f}
│  Variance:    {brk['variance']:>+15,.2f} ({brk['variance_pct']:+.2f}%)
│  Details:     {brk['details']}
└──────────────────────────────────────────────────────────────────
"""
    
    report += """
══════════════════════════════════════════════════════════════════════════════
                              END OF REPORT
══════════════════════════════════════════════════════════════════════════════
"""
    
    return report


def save_breaks_to_csv(breaks: List[Dict], filename: str = "reconciliation_breaks.csv") -> None:
    """Save breaks to CSV file"""
    if breaks:
        df = pd.DataFrame(breaks)
        df.to_csv(filename, index=False)
        print(f"\n💾 Breaks saved to: {filename}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution function"""
    
    print("""
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║       POSITION RECONCILIATION ERROR ALERTS SYSTEM                     ║
    ║       ─────────────────────────────────────────────                   ║
    ║                                                                       ║
    ║   Automated reconciliation monitoring for hedge fund operations       ║
    ║   Compares: Internal Trading System vs Prime Broker                   ║
    ║                                                                       ║
    ║   Author: Rahul Yatagiri                                              ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Step 1: Generate sample data
    print("\n[STEP 1/4] Generating Position Data")
    print("─" * 50)
    internal_df, pb_df = generate_sample_data()
    
    # Step 2: Run reconciliation
    print("\n[STEP 2/4] Running Position Reconciliation")
    print("─" * 50)
    breaks = reconcile_positions(internal_df, pb_df)
    
    # Step 3: Generate alerts
    print("\n[STEP 3/4] Processing Alerts")
    print("─" * 50)
    generate_alerts(breaks)
    
    # Step 4: Generate report
    print("\n[STEP 4/4] Generating Report")
    print("─" * 50)
    report = generate_report(breaks, internal_df, pb_df)
    print(report)
    
    # Save outputs
    save_breaks_to_csv(breaks)
    
    # Save report to file
    with open("reconciliation_report.txt", "w") as f:
        f.write(report)
    print(f"📄 Report saved to: reconciliation_report.txt")
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ RECONCILIATION COMPLETE")
    print("=" * 70)
    print(f"   Total Breaks Found: {len(breaks)}")
    print(f"   Critical/High: {len([b for b in breaks if b['severity'] in ['CRITICAL', 'HIGH']])}")
    print(f"   Files Generated: reconciliation_breaks.csv, reconciliation_report.txt")
    print("=" * 70)


if __name__ == "__main__":
    main()
