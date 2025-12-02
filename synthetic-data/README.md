# Synthetic Crisis Data

Historical price data for three major DeFi crisis events, used to test OmniPair GAMM protocol resilience.

---

## Data Sources

### mango_exploit/
**Event**: Mango Markets Oracle Manipulation Exploit  
**Date**: October 11, 2022  
**Token**: MNGO/USDC  
**Price Movement**: $0.03 → $0.91 → $0.03 (20 minutes)  
**Attack Type**: Oracle manipulation via market orders  
**Real Loss**: $110M+ stolen from protocol

**Files**:
- `mngo_usdc_prices.csv` - Time-series price data
- `mngo_usdc_prices_metadata.json` - Event documentation

---

### luna_collapse/
**Event**: LUNA/UST Algorithmic Stablecoin Collapse  
**Date**: May 7-13, 2022  
**Token**: LUNA/USDC  
**Price Movement**: $80 → $0.0001 (6 days, -99.99%)  
**Attack Type**: Death spiral, liquidity crisis  
**Real Loss**: $40B+ market cap destroyed

**Files**:
- `luna_usdc_prices.csv` - Time-series price data
- `luna_usdc_prices_metadata.json` - Event documentation

---

### ftt_collapse/
**Event**: FTX Exchange Token Collapse  
**Date**: November 6-15, 2022  
**Token**: FTT/USDC  
**Price Movement**: $22 → $2 (10 days, -90%)  
**Attack Type**: Liquidity crisis, exchange failure  
**Real Loss**: $8B+ user funds trapped

**Files**:
- `ftt_usdc_prices.csv` - Time-series price data
- `ftt_usdc_prices_metadata.json` - Event documentation

---

## Data Format

### CSV Files
**Columns**:
- `timestamp` - Unix timestamp (seconds)
- `price_usd` - Token price in USD
- `datetime` - Human-readable timestamp (ISO 8601)

**Example**:
```csv
timestamp,price_usd,datetime
1665446400,0.030000,2022-10-11T00:00:00Z
1665447000,0.350000,2022-10-11T00:10:00Z
1665447600,0.910000,2022-10-11T00:20:00Z
```

### Metadata Files
**Contents**:
- Event name and date
- Token information
- Price range (min/max)
- Crisis type and description
- Data granularity (time resolution)
- Source methodology

---

## Data Generation

These datasets were generated using `create_synthetic_data.py`, which produces realistic price movements based on documented historical events.

**Method**: Synthetic generation based on:
- Published post-mortem reports
- Blockchain analysis
- Market data documentation
- Crisis timelines

**Validation**: Price ranges and timelines verified against multiple sources.

---

## Usage in Simulation

The simulation framework:
1. Loads CSV price data
2. Steps through time chronologically
3. Updates EMA, collateral factors, and liquidation thresholds
4. Tracks protocol health metrics
5. Compares against baseline configurations

See `run_all_scenarios.py` for implementation.

---

## Limitations

**Synthetic Nature**: While based on real events, exact tick-by-tick price data is reconstructed, not recorded.

**Simplified Dynamics**: Does not include:
- Order book depth changes
- Cross-exchange arbitrage
- Network congestion effects
- Cascading liquidation dynamics

**Conservative Approach**: Price movements are representative but simplified to focus on protocol mechanism testing.

---

## Data Quality

**Temporal Resolution**:
- Mango: 10-minute intervals (rapid manipulation)
- LUNA: 2-hour intervals (multi-day collapse)
- FTT: 6-hour intervals (gradual decline)

**Coverage**: Complete crisis event from pre-crisis to post-crisis stabilization.

**Consistency**: All datasets use consistent format and validation.

---

## Regenerating Data

To regenerate synthetic data:

```bash
python create_synthetic_data.py
```

This will recreate all CSV and metadata files in their respective folders.

---

Last Updated: December 2, 2025


