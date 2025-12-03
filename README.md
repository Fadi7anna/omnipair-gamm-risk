# OmniPair GAMM Protocol - Risk Analysis

Comprehensive quantitative risk analysis and simulation framework for OmniPair's Generalized Automated Market Maker (GAMM) protocol.

---

## Executive Summary

This repository contains a complete risk analysis of OmniPair's GAMM protocol, testing its protection mechanisms against three major DeFi crisis scenarios. The analysis validates the protocol's claims through quantitative simulation.

**Key Finding**: OmniPair's multi-layered protection system achieves **97% risk reduction** compared to traditional oracle-based lending protocols.

---

## Quick Navigation

### For Managers & Stakeholders
- **[Executive Summary](results/EXECUTIVE_SUMMARY.md)** - Start here (10-minute read)
- **[Key Results Tables](results/EXECUTIVE_SUMMARY.md#key-findings)** - Quick reference

### For Technical Review
- **[Detailed Analysis](results/DETAILED_SIMULATION_RESULTS.md)** - Complete methodology and results
- **[Contract Analysis](analysis/contract_analysis.md)** - Formula extraction documentation

### For Developers
- **[Interactive Jupyter Notebook](OmniPair_GAMM_Risk_Analysis.ipynb)** - Run simulations interactively with visualizations
- **[Simulation Modules](modules/)** - Core Python implementation
- **[Requirements](requirements.txt)** - Dependencies
- **[Run All Scenarios](run_all_scenarios.py)** - Execute complete test suite

### Data & Results
- **[Analysis Results](analysis_results.json)** - Raw numerical data
- **[Crisis Data](synthetic-data/)** - Historical price data (CSV format)

---

## Key Findings

| Metric | Result |
|--------|--------|
| **EMA Pricing Effectiveness** | 88% bad debt reduction |
| **Full GAMM Stack** | 97% bad debt reduction |
| **vs Actual Mango Exploit** | 46,400x improvement |
| **LUNA Collapse Performance** | 0% bad debt |
| **FTT Collapse Performance** | 0% bad debt |

### Component Attribution

```
Traditional Lending:        $80,838 bad debt (baseline)
+ EMA Pricing:             $9,784 bad debt  (-88%)
+ Pessimistic Cap + Buffer: $2,368 bad debt  (-97% total)
```

**Conclusion**: EMA provides primary protection (88%), with additional layers catching edge cases (another 76% improvement).

---

## Scenarios Tested

### 1. Mango Markets Exploit (October 2022)
- **Type**: Oracle manipulation attack
- **Price Movement**: $0.03 → $0.91 → $0.03 (20 minutes)
- **Result**: 97% bad debt reduction vs traditional lending

### 2. LUNA/UST Collapse (May 2022)
- **Type**: Systemic death spiral
- **Price Movement**: $80 → $0.0001 (6 days, -99.99%)
- **Result**: 0% bad debt (all configurations)

### 3. FTX Token Collapse (November 2022)
- **Type**: Liquidity crisis
- **Price Movement**: $22 → $2 (10 days, -90%)
- **Result**: 0% bad debt (all configurations)

---

## Repository Structure

```
omnipair-gamm-risk/
│
├── README.md                        # This file
├── requirements.txt                 # Python dependencies
├── analysis_results.json            # Raw simulation data
├── .gitignore                       # Git exclusions
│
├── results/                         # Professional documentation
│   ├── EXECUTIVE_SUMMARY.md         # Start here
│   └── DETAILED_SIMULATION_RESULTS.md
│
├── modules/                         # Core simulation framework
│   ├── config.py                    # Protocol constants & configurations
│   ├── ema_engine.py                # EMA pricing mechanism
│   ├── collateral_factor.py         # Dynamic CF calculator
│   ├── liquidation_engine.py        # Liquidation logic
│   └── gamm_pool.py                 # Complete pool simulation
│
├── synthetic-data/                  # Crisis price datasets
│   ├── mango_exploit/               # MNGO token (Oct 2022)
│   ├── luna_collapse/               # LUNA token (May 2022)
│   └── ftt_collapse/                # FTT token (Nov 2022)
│
├── analysis/                        # Technical documentation
│   └── contract_analysis.md         # Contract formula extraction
│
├── run_all_scenarios.py             # Execute complete test suite
├── create_synthetic_data.py         # Generate synthetic crisis data
└── data_collector.py                # API data fetcher (reference)
```

---

## Quick Start

### Run Simulations

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run all scenario tests
python run_all_scenarios.py

# 3. View results
cat analysis_results.json
```

### Test Individual Components

```bash
# Test EMA engine
python modules/ema_engine.py

# Test collateral factor calculator
python modules/collateral_factor.py

# Test liquidation engine
python modules/liquidation_engine.py

# Test complete pool simulation
python modules/gamm_pool.py
```

---

## Methodology

### Simulation Approach

1. **Contract Analysis**: Extracted exact formulas from OmniPair Solana smart contracts
2. **Framework Development**: Built Python simulation replicating contract logic (19 unit tests passing)
3. **Scenario Testing**: Simulated 3 historical crises with 5 different protocol configurations
4. **Component Isolation**: Tested each protection mechanism independently to measure contribution
5. **Comparative Analysis**: Benchmarked against traditional lending and actual historical outcomes

### Configurations Tested

1. **Traditional Lending** - Spot pricing, fixed 75% CF (baseline)
2. **EMA Only** - Time-smoothed pricing, fixed CF
3. **Dynamic CF Only** - Spot pricing, AMM curve-based CF
4. **EMA + Dynamic CF** - Combined but no pessimistic cap
5. **Full GAMM** - All protections enabled

---

## Technical Validation

All protocol mechanisms validated against smart contract specifications:

- EMA calculation (60s half-life default)
- Dynamic collateral factor (AMM curve solution)
- Pessimistic divergence cap (min(CF, CF × spot/EMA))
- LTV safety buffer (5%)
- Partial liquidation (50% close factor)

**Test Coverage**: 19/19 unit tests passing

---

## Results Summary

### By Configuration (Mango Scenario)

| Configuration | Bad Debt | Improvement |
|--------------|----------|-------------|
| Traditional Lending | $80,838 | Baseline |
| EMA Only | $9,784 | +88% |
| Dynamic CF Only | $80,838 | 0% |
| EMA + Dynamic CF | $9,784 | +88% |
| **Full GAMM** | **$2,368** | **+97%** |

### By Scenario (Full GAMM)

| Scenario | Bad Debt | Status |
|----------|----------|---------|
| Mango Markets | $2,368 | Minimal |
| LUNA Collapse | $0 | Perfect |
| FTT Collapse | $0 | Perfect |
| **Average** | **$789** | **Excellent** |

---

## Limitations

1. **Synthetic Data**: Used simulated crisis price data based on documented events
2. **Idealized Liquidations**: Assumed instant execution (real-world has delays)
3. **Single Pool**: Tested isolated pools (no cross-protocol contagion)
4. **Representative Positions**: Used synthetic borrower profiles

**Confidence**: Results are directionally accurate for mechanism validation. Comparative ratios (88%, 97%) are robust to parameter variations.

---

## Citation

When referencing this analysis:

**Format**: OmniPair GAMM Protocol Risk Analysis, Quantitative Simulation Study, December 2025

**GitHub**: https://github.com/Fadi7anna/omnipair-gamm-risk

---

## License

This analysis and simulation framework are provided for review and validation purposes.

---

## Contact

For questions regarding methodology, results, or technical implementation, please refer to documentation or open an issue in this repository.

**Analysis Date**: December 2, 2025  
**Status**: Complete and ready for review  
**Version**: 1.0


