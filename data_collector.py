"""
Data Collector - Historical Crisis Data
Fetches price data from CoinGecko API for DeFi crisis scenarios
"""

import requests
import time
import json
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from config import float_to_nad


# ============================================================================
# API CONFIGURATION
# ============================================================================

COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"
RATE_LIMIT_DELAY = 1.5  # Seconds between requests (free tier: ~50 calls/min)


# ============================================================================
# CRISIS EVENT METADATA
# ============================================================================

CRISIS_EVENTS = {
    "mango_exploit": {
        "name": "Mango Markets Exploit",
        "coin_id": "mango-markets",
        "start_date": datetime(2022, 10, 10),  # Day before
        "end_date": datetime(2022, 10, 13),    # Day after
        "description": "Oracle manipulation attack, $110M loss",
        "key_timestamps": {
            "pre_attack": "2022-10-11T17:00:00Z",
            "attack_start": "2022-10-11T18:00:00Z",
            "peak_manipulation": "2022-10-11T18:20:00Z",
            "liquidations_begin": "2022-10-11T18:25:00Z",
            "aftermath": "2022-10-12T00:00:00Z",
        }
    },
    "luna_collapse": {
        "name": "LUNA/UST Death Spiral",
        "coin_id": "terra-luna",
        "start_date": datetime(2022, 5, 5),
        "end_date": datetime(2022, 5, 15),
        "description": "$40B+ ecosystem collapse, death spiral",
        "key_timestamps": {
            "pre_depeg": "2022-05-07T00:00:00Z",
            "ust_depeg_start": "2022-05-09T00:00:00Z",
            "panic_selling": "2022-05-10T00:00:00Z",
            "collapse": "2022-05-11T00:00:00Z",
            "aftermath": "2022-05-13T00:00:00Z",
        }
    },
    "ftt_collapse": {
        "name": "FTX Token Collapse",
        "coin_id": "ftx-token",
        "start_date": datetime(2022, 11, 1),
        "end_date": datetime(2022, 11, 12),
        "description": "Gradual then rapid crash, liquidity crisis",
        "key_timestamps": {
            "balance_sheet_leak": "2022-11-02T00:00:00Z",
            "binance_announcement": "2022-11-06T00:00:00Z",
            "panic_begins": "2022-11-08T00:00:00Z",
            "collapse": "2022-11-09T00:00:00Z",
            "trading_halt": "2022-11-10T00:00:00Z",
        }
    }
}


# ============================================================================
# API FUNCTIONS
# ============================================================================

def fetch_coingecko_market_chart(
    coin_id: str,
    start_timestamp: int,
    end_timestamp: int,
    vs_currency: str = "usd"
) -> Optional[Dict]:
    """
    Fetch historical market data from CoinGecko.
    
    Args:
        coin_id: CoinGecko coin identifier (e.g., "mango-markets")
        start_timestamp: Start unix timestamp
        end_timestamp: End unix timestamp
        vs_currency: Quote currency (default: "usd")
    
    Returns:
        API response dict or None if error
    """
    url = f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart/range"
    
    params = {
        "vs_currency": vs_currency,
        "from": start_timestamp,
        "to": end_timestamp
    }
    
    try:
        print(f"📡 Fetching {coin_id} data from {datetime.fromtimestamp(start_timestamp)} to {datetime.fromtimestamp(end_timestamp)}...")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Received {len(data.get('prices', []))} price points")
        
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")
        return None


def process_price_data(raw_data: Dict) -> List[Tuple[int, float]]:
    """
    Process CoinGecko API response into clean price data.
    
    Args:
        raw_data: CoinGecko API response
    
    Returns:
        List of (timestamp_seconds, price_usd) tuples
    """
    if not raw_data or "prices" not in raw_data:
        return []
    
    # CoinGecko returns [timestamp_ms, price]
    prices = raw_data["prices"]
    
    # Convert to (timestamp_seconds, price) and sort
    processed = [
        (int(ts_ms / 1000), price)
        for ts_ms, price in prices
    ]
    
    processed.sort(key=lambda x: x[0])
    
    return processed


def save_price_data_csv(
    price_data: List[Tuple[int, float]],
    filepath: str,
    metadata: Optional[Dict] = None
):
    """
    Save price data to CSV file.
    
    Args:
        price_data: List of (timestamp, price) tuples
        filepath: Output CSV file path
        metadata: Optional metadata to save alongside
    """
    # Create directory if needed
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    # Write CSV
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "datetime", "price_usd"])
        
        for timestamp, price in price_data:
            dt = datetime.fromtimestamp(timestamp).isoformat()
            writer.writerow([timestamp, dt, price])
    
    print(f"💾 Saved {len(price_data)} price points to {filepath}")
    
    # Save metadata if provided
    if metadata:
        metadata_path = filepath.replace(".csv", "_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        print(f"💾 Saved metadata to {metadata_path}")


def load_price_data_csv(filepath: str) -> List[Tuple[int, int]]:
    """
    Load price data from CSV and convert to NAD-scaled.
    
    Args:
        filepath: CSV file path
    
    Returns:
        List of (timestamp, price_nad) tuples
    """
    price_data = []
    
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = int(row["timestamp"])
            price_usd = float(row["price_usd"])
            price_nad = float_to_nad(price_usd)
            price_data.append((timestamp, price_nad))
    
    return price_data


# ============================================================================
# CRISIS-SPECIFIC COLLECTORS
# ============================================================================

def collect_mango_exploit_data(output_dir: str = "data/mango_exploit") -> str:
    """
    Collect Mango Markets exploit data (Oct 11-12, 2022).
    
    Returns:
        Path to saved CSV file
    """
    event = CRISIS_EVENTS["mango_exploit"]
    
    start_ts = int(event["start_date"].timestamp())
    end_ts = int(event["end_date"].timestamp())
    
    # Fetch data
    raw_data = fetch_coingecko_market_chart(
        coin_id=event["coin_id"],
        start_timestamp=start_ts,
        end_timestamp=end_ts
    )
    
    if not raw_data:
        print("❌ Failed to collect Mango exploit data")
        return ""
    
    # Process and save
    price_data = process_price_data(raw_data)
    filepath = f"{output_dir}/mngo_usdc_prices.csv"
    
    save_price_data_csv(
        price_data=price_data,
        filepath=filepath,
        metadata={
            "event_name": event["name"],
            "description": event["description"],
            "coin_id": event["coin_id"],
            "date_range": f"{event['start_date']} to {event['end_date']}",
            "key_timestamps": event["key_timestamps"],
            "source": "CoinGecko API",
            "collected_at": datetime.now().isoformat(),
        }
    )
    
    time.sleep(RATE_LIMIT_DELAY)
    return filepath


def collect_luna_collapse_data(output_dir: str = "data/luna_collapse") -> str:
    """
    Collect LUNA collapse data (May 7-15, 2022).
    
    Returns:
        Path to saved CSV file
    """
    event = CRISIS_EVENTS["luna_collapse"]
    
    start_ts = int(event["start_date"].timestamp())
    end_ts = int(event["end_date"].timestamp())
    
    # Fetch data
    raw_data = fetch_coingecko_market_chart(
        coin_id=event["coin_id"],
        start_timestamp=start_ts,
        end_timestamp=end_ts
    )
    
    if not raw_data:
        print("❌ Failed to collect LUNA collapse data")
        return ""
    
    # Process and save
    price_data = process_price_data(raw_data)
    filepath = f"{output_dir}/luna_usdc_prices.csv"
    
    save_price_data_csv(
        price_data=price_data,
        filepath=filepath,
        metadata={
            "event_name": event["name"],
            "description": event["description"],
            "coin_id": event["coin_id"],
            "date_range": f"{event['start_date']} to {event['end_date']}",
            "key_timestamps": event["key_timestamps"],
            "source": "CoinGecko API",
            "collected_at": datetime.now().isoformat(),
        }
    )
    
    time.sleep(RATE_LIMIT_DELAY)
    return filepath


def collect_ftt_collapse_data(output_dir: str = "data/ftt_collapse") -> str:
    """
    Collect FTT collapse data (Nov 1-12, 2022).
    
    Returns:
        Path to saved CSV file
    """
    event = CRISIS_EVENTS["ftt_collapse"]
    
    start_ts = int(event["start_date"].timestamp())
    end_ts = int(event["end_date"].timestamp())
    
    # Fetch data
    raw_data = fetch_coingecko_market_chart(
        coin_id=event["coin_id"],
        start_timestamp=start_ts,
        end_timestamp=end_ts
    )
    
    if not raw_data:
        print("❌ Failed to collect FTT collapse data")
        return ""
    
    # Process and save
    price_data = process_price_data(raw_data)
    filepath = f"{output_dir}/ftt_usdc_prices.csv"
    
    save_price_data_csv(
        price_data=price_data,
        filepath=filepath,
        metadata={
            "event_name": event["name"],
            "description": event["description"],
            "coin_id": event["coin_id"],
            "date_range": f"{event['start_date']} to {event['end_date']}",
            "key_timestamps": event["key_timestamps"],
            "source": "CoinGecko API",
            "collected_at": datetime.now().isoformat(),
        }
    )
    
    time.sleep(RATE_LIMIT_DELAY)
    return filepath


def collect_all_crisis_data():
    """
    Collect data for all three crisis scenarios.
    """
    print("\n" + "="*70)
    print("📊 Collecting Historical Crisis Data")
    print("="*70 + "\n")
    
    results = {}
    
    # Mango Markets
    print("\n🔴 Mango Markets Exploit (Oct 2022)")
    print("-" * 70)
    results["mango"] = collect_mango_exploit_data()
    
    # LUNA Collapse
    print("\n🌙 LUNA/UST Collapse (May 2022)")
    print("-" * 70)
    results["luna"] = collect_luna_collapse_data()
    
    # FTT Collapse
    print("\n💥 FTX Token Collapse (Nov 2022)")
    print("-" * 70)
    results["ftt"] = collect_ftt_collapse_data()
    
    print("\n" + "="*70)
    print("✅ Data Collection Complete!")
    print("="*70 + "\n")
    
    for event, filepath in results.items():
        if filepath:
            print(f"  {event}: {filepath}")
    
    return results


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def analyze_price_data(filepath: str):
    """
    Quick analysis of collected price data.
    
    Args:
        filepath: Path to CSV file
    """
    prices = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prices.append(float(row["price_usd"]))
    
    if not prices:
        print("No price data found")
        return
    
    print(f"\n📈 Price Data Analysis: {filepath}")
    print(f"   Data points: {len(prices)}")
    print(f"   Starting price: ${prices[0]:.4f}")
    print(f"   Ending price: ${prices[-1]:.4f}")
    print(f"   Peak price: ${max(prices):.4f}")
    print(f"   Bottom price: ${min(prices):.4f}")
    
    total_change = ((prices[-1] - prices[0]) / prices[0]) * 100
    max_drawdown = ((min(prices) - max(prices)) / max(prices)) * 100
    
    print(f"   Total change: {total_change:+.1f}%")
    print(f"   Max drawdown: {max_drawdown:.1f}%")


def verify_data_quality(filepath: str) -> bool:
    """
    Verify data quality and completeness.
    
    Args:
        filepath: Path to CSV file
    
    Returns:
        True if data is good quality
    """
    try:
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        if len(rows) == 0:
            print(f"❌ {filepath}: No data")
            return False
        
        # Check for missing values
        for i, row in enumerate(rows):
            if not row.get("price_usd") or float(row["price_usd"]) <= 0:
                print(f"❌ {filepath}: Invalid price at row {i}")
                return False
        
        # Check timestamp ordering
        timestamps = [int(row["timestamp"]) for row in rows]
        if timestamps != sorted(timestamps):
            print(f"❌ {filepath}: Timestamps not in order")
            return False
        
        print(f"✅ {filepath}: Data quality good ({len(rows)} points)")
        return True
    
    except Exception as e:
        print(f"❌ {filepath}: Error - {e}")
        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n🚀 OmniPair Risk Analysis - Data Collection\n")
    
    # Collect all data
    results = collect_all_crisis_data()
    
    # Verify and analyze
    print("\n📊 Verifying Data Quality...\n")
    for event, filepath in results.items():
        if filepath:
            verify_data_quality(filepath)
            analyze_price_data(filepath)
    
    print("\n✅ All data collected and verified!")
    print("\n💡 Next: Run simulations with collected data")
    print("   Example: python gamm_pool.py")

