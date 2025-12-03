# Simulation Modules

Core Python implementation of OmniPair's GAMM protocol mechanisms, extracted directly from Solana smart contracts.

---

## Modules Overview

### config.py
**Purpose**: Protocol constants and configuration presets

**Contents**:
- Universal constants (NAD, BPS_DENOMINATOR, etc.)
- Protocol parameters (collateral factors, liquidation thresholds)
- EMA configuration (half-life, natural log constants)
- Simulation configuration class with presets

**Usage**: Import constants and create `SimulationConfig` objects for different test scenarios.

---

### ema_engine.py
**Purpose**: EMA (Exponential Moving Average) pricing mechanism

**Key Functions**:
- `compute_ema()`: Time-weighted EMA calculation
- `taylor_exp()`: Taylor series exponential approximation

**Validation**: Replicates exact logic from `programs/omnipair/src/utils/math.rs`

**Tests**: Unit tests included (run: `python ema_engine.py`)

---

### collateral_factor.py
**Purpose**: Dynamic collateral factor calculation

**Key Functions**:
- `curve_y_from_v()`: Solve AMM curve for exact reserves
- `pessimistic_max_debt()`: Calculate max debt based on AMM curve
- `get_pessimistic_cf_bps()`: Apply spot/EMA divergence cap

**Validation**: Replicates exact logic from `programs/omnipair/src/utils/gamm_math.rs`

**Tests**: Unit tests included (run: `python collateral_factor.py`)

---

### liquidation_engine.py
**Purpose**: Liquidation mechanics and threshold calculations

**Key Functions**:
- `calculate_liquidation()`: Determine liquidatability and amounts
- Implements partial liquidation (close factor)
- Handles insolvency detection

**Validation**: Replicates exact logic from `programs/omnipair/src/instructions/lending/liquidate.rs`

**Tests**: Unit tests included (run: `python liquidation_engine.py`)

---

### gamm_pool.py
**Purpose**: Complete pool state management and simulation orchestration

**Key Classes**:
- `GAMMPool`: Main simulation engine
- `BorrowerPosition`: User position tracking

**Functions**:
- `step()`: Advance simulation by one time step
- Integrates EMA, collateral factor, and liquidation logic
- Tracks protocol health metrics

**Tests**: Comprehensive integration tests (run: `python gamm_pool.py`)

---

## Running Tests

Each module includes unit tests that can be run independently:

```bash
# Test individual modules
python modules/ema_engine.py
python modules/collateral_factor.py
python modules/liquidation_engine.py
python modules/gamm_pool.py

# All tests should pass (19/19 total)
```

---

## Dependencies

See `requirements.txt` in root directory. Primary dependency: `numpy` for numerical operations.

```bash
pip install -r requirements.txt
```

---

## Architecture

```
User Script (run_all_scenarios.py)
        ↓
    GAMMPool (gamm_pool.py)
        ↓
    ┌───────┴───────┐
    ↓               ↓
EMA Engine      Collateral Factor
(ema_engine.py) (collateral_factor.py)
        ↓               ↓
        └───────┬───────┘
                ↓
        Liquidation Engine
        (liquidation_engine.py)
                ↓
            Results
```

---

## Contract Mapping

| Module | Smart Contract Source |
|--------|----------------------|
| `config.py` | `programs/omnipair/src/constants.rs` |
| `ema_engine.py` | `programs/omnipair/src/utils/math.rs` |
| `collateral_factor.py` | `programs/omnipair/src/utils/gamm_math.rs` |
| `liquidation_engine.py` | `programs/omnipair/src/instructions/lending/liquidate.rs` |
| `gamm_pool.py` | `programs/omnipair/src/state/pair.rs` |

See `analysis/contract_analysis.md` for detailed formula extraction documentation.

---

## Code Quality

- **Type Hints**: All functions include type annotations
- **Docstrings**: Comprehensive documentation for all public functions
- **Unit Tests**: 19 tests covering critical logic paths
- **Validation**: All calculations verified against smart contract specifications

---

Last Updated: December 2, 2025



