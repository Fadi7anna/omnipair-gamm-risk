"""
Create Synthetic Crisis Data
Generates realistic price data based on actual historical crisis events
"""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
import math


def generate_mango_exploit_data():
    """
    Simulate Mango Markets exploit (Oct 11, 2022)
    
    Actual event: MNGO manipulated from ~$0.03 to ~$0.91 in minutes,
    then crashed back down. Oracle manipulation attack.
    """
    output_dir = Path("data/mango_exploit")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Start time: Oct 11, 2022, 17:00 UTC (1 hour before attack)
    start_time = datetime(2022, 10, 11, 17, 0, 0)
    
    price_data = []
    
    # Phase 1: Stable price before attack (17:00-18:00)
    base_price = 0.0295
    for minute in range(60):
        timestamp = int((start_time + timedelta(minutes=minute)).timestamp())
        price = base_price + (0.0005 * math.sin(minute / 10))  # Small fluctuations
        price_data.append((timestamp, price))
    
    # Phase 2: Rapid manipulation (18:00-18:20, 20 minutes)
    attack_start = start_time + timedelta(hours=1)
    for minute in range(20):
        timestamp = int((attack_start + timedelta(minutes=minute)).timestamp())
        # Exponential pump to $0.91
        progress = minute / 20
        price = base_price + (0.91 - base_price) * (progress ** 0.5)  # Square root curve
        price_data.append((timestamp, price))
    
    # Phase 3: Peak and immediate crash (18:20-18:40, 20 minutes)
    crash_start = attack_start + timedelta(minutes=20)
    peak_price = 0.91
    for minute in range(20):
        timestamp = int((crash_start + timedelta(minutes=minute)).timestamp())
        progress = minute / 20
        # Sharp drop back down
        price = peak_price - (peak_price - 0.04) * (progress ** 2)  # Quadratic drop
        price_data.append((timestamp, price))
    
    # Phase 4: Aftermath volatility (18:40-22:00, ~200 minutes)
    aftermath_start = crash_start + timedelta(minutes=20)
    for minute in range(200):
        timestamp = int((aftermath_start + timedelta(minutes=minute)).timestamp())
        # Gradual decline with high volatility
        base = 0.04 - (0.01 * (minute / 200))
        volatility = 0.005 * math.sin(minute / 5)
        price = max(0.025, base + volatility)
        price_data.append((timestamp, price))
    
    # Save to CSV
    filepath = output_dir / "mngo_usdc_prices.csv"
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "datetime", "price_usd"])
        for ts, price in price_data:
            dt = datetime.fromtimestamp(ts).isoformat()
            writer.writerow([ts, dt, f"{price:.6f}"])
    
    # Save metadata
    metadata = {
        "event_name": "Mango Markets Exploit (Synthetic)",
        "description": "Oracle manipulation attack simulation based on actual event",
        "date": "2022-10-11",
        "price_range": {"start": base_price, "peak": peak_price, "end": price_data[-1][1]},
        "data_points": len(price_data),
        "note": "Synthetic data simulating actual price movements",
    }
    
    with open(output_dir / "mngo_usdc_prices_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Created Mango exploit data: {len(price_data)} points")
    return str(filepath)


def generate_luna_collapse_data():
    """
    Simulate LUNA collapse (May 7-13, 2022)
    
    Actual event: LUNA went from ~$80 to near-zero in days.
    Death spiral triggered by UST depeg.
    """
    output_dir = Path("data/luna_collapse")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    start_time = datetime(2022, 5, 7, 0, 0, 0)
    
    price_data = []
    
    # Phase 1: Pre-depeg stability (May 7, 24 hours)
    start_price = 79.5
    for hour in range(24):
        timestamp = int((start_time + timedelta(hours=hour)).timestamp())
        price = start_price + (2 * math.sin(hour / 4))  # Normal volatility
        price_data.append((timestamp, price))
    
    # Phase 2: UST depeg begins, slow decline (May 8, 24 hours)
    day2_start = start_time + timedelta(days=1)
    for hour in range(24):
        timestamp = int((day2_start + timedelta(hours=hour)).timestamp())
        progress = hour / 24
        price = start_price - (start_price * 0.15 * progress)  # -15% first day
        price_data.append((timestamp, price))
    
    # Phase 3: Panic selling begins (May 9, 24 hours)
    day3_start = start_time + timedelta(days=2)
    for hour in range(24):
        timestamp = int((day3_start + timedelta(hours=hour)).timestamp())
        progress = hour / 24
        current_start = start_price * 0.85
        price = current_start * (1 - 0.40 * (progress ** 1.5))  # -40%, accelerating
        price_data.append((timestamp, price))
    
    # Phase 4: Death spiral (May 10-11, 48 hours)
    day4_start = start_time + timedelta(days=3)
    for hour in range(48):
        timestamp = int((day4_start + timedelta(hours=hour)).timestamp())
        progress = hour / 48
        current_start = start_price * 0.51
        # Exponential collapse
        price = current_start * math.exp(-5 * progress)
        price = max(0.0001, price)  # Floor at near-zero
        price_data.append((timestamp, price))
    
    # Phase 5: Near-zero aftermath (May 12-13, 24 hours)
    day6_start = start_time + timedelta(days=5)
    for hour in range(24):
        timestamp = int((day6_start + timedelta(hours=hour)).timestamp())
        price = 0.0001 + (0.00005 * math.sin(hour))  # Essentially zero
        price_data.append((timestamp, price))
    
    # Save
    filepath = output_dir / "luna_usdc_prices.csv"
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "datetime", "price_usd"])
        for ts, price in price_data:
            dt = datetime.fromtimestamp(ts).isoformat()
            writer.writerow([ts, dt, f"{price:.6f}"])
    
    metadata = {
        "event_name": "LUNA/UST Collapse (Synthetic)",
        "description": "Death spiral simulation based on actual collapse",
        "date_range": "2022-05-07 to 2022-05-13",
        "price_range": {"start": start_price, "bottom": price_data[-1][1], "drop_pct": 99.99},
        "data_points": len(price_data),
    }
    
    with open(output_dir / "luna_usdc_prices_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Created LUNA collapse data: {len(price_data)} points")
    return str(filepath)


def generate_ftt_collapse_data():
    """
    Simulate FTT collapse (Nov 1-10, 2022)
    
    Actual event: FTT went from ~$22 to ~$2 over 8 days.
    Gradual then accelerating collapse after Alameda balance sheet leak.
    """
    output_dir = Path("data/ftt_collapse")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    start_time = datetime(2022, 11, 1, 0, 0, 0)
    
    price_data = []
    
    start_price = 22.0
    
    # Phase 1: Normal trading (Nov 1, 24 hours)
    for hour in range(24):
        timestamp = int((start_time + timedelta(hours=hour)).timestamp())
        price = start_price + (0.5 * math.sin(hour / 3))
        price_data.append((timestamp, price))
    
    # Phase 2: Balance sheet leak, uncertainty (Nov 2-5, 4 days)
    leak_start = start_time + timedelta(days=1)
    for hour in range(96):  # 4 days
        timestamp = int((leak_start + timedelta(hours=hour)).timestamp())
        day_progress = hour / 96
        price = start_price * (1 - 0.25 * day_progress)  # -25% over 4 days
        volatility = 0.5 * math.sin(hour / 6)
        price_data.append((timestamp, price + volatility))
    
    # Phase 3: Binance announcement, selling pressure (Nov 6-7, 2 days)
    binance_start = start_time + timedelta(days=5)
    for hour in range(48):
        timestamp = int((binance_start + timedelta(hours=hour)).timestamp())
        progress = hour / 48
        current_start = start_price * 0.75
        price = current_start * (1 - 0.40 * (progress ** 1.2))  # -40%, accelerating
        price_data.append((timestamp, price))
    
    # Phase 4: Panic collapse (Nov 8-9, 2 days)
    panic_start = start_time + timedelta(days=7)
    for hour in range(48):
        timestamp = int((panic_start + timedelta(hours=hour)).timestamp())
        progress = hour / 48
        current_start = start_price * 0.45
        price = current_start * (1 - 0.75 * (progress ** 2))  # -75%, quadratic
        price = max(2.0, price)
        price_data.append((timestamp, price))
    
    # Phase 5: Aftermath (Nov 10, 12 hours)
    aftermath_start = start_time + timedelta(days=9)
    for hour in range(12):
        timestamp = int((aftermath_start + timedelta(hours=hour)).timestamp())
        price = 2.0 + (0.3 * math.sin(hour / 2))  # Stabilized at ~$2
        price_data.append((timestamp, price))
    
    # Save
    filepath = output_dir / "ftt_usdc_prices.csv"
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "datetime", "price_usd"])
        for ts, price in price_data:
            dt = datetime.fromtimestamp(ts).isoformat()
            writer.writerow([ts, dt, f"{price:.6f}"])
    
    metadata = {
        "event_name": "FTX Token Collapse (Synthetic)",
        "description": "Gradual then rapid collapse simulation",
        "date_range": "2022-11-01 to 2022-11-10",
        "price_range": {"start": start_price, "bottom": 2.0, "drop_pct": 90.9},
        "data_points": len(price_data),
    }
    
    with open(output_dir / "ftt_usdc_prices_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Created FTT collapse data: {len(price_data)} points")
    return str(filepath)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔬 Generating Synthetic Crisis Data")
    print("="*70 + "\n")
    
    mango_path = generate_mango_exploit_data()
    luna_path = generate_luna_collapse_data()
    ftt_path = generate_ftt_collapse_data()
    
    print("\n" + "="*70)
    print("✅ All Synthetic Data Generated!")
    print("="*70)
    print(f"\n  Mango: {mango_path}")
    print(f"  LUNA: {luna_path}")
    print(f"  FTT: {ftt_path}")
    print("\n💡 These simulate actual crisis events for testing the framework")
    print("   Ready to run simulations!\n")

