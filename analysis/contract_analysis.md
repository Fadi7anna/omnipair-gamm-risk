# OmniPair Contract Analysis
**Date**: 2025-12-02  
**Purpose**: Extract exact formulas and parameters for simulation

---

## 1. Protocol Constants (from `constants.rs`)

### Core Precision & Scaling
```rust
NAD = 1_000_000_000                    // 1e9 scaling factor (like WAD but 1e18)
NAD_DECIMALS = 9                       // 9 decimal places
BPS_DENOMINATOR = 10_000              // Basis points denominator (100% = 10,000 bps)
```

### Liquidation Parameters
```rust
CLOSE_FACTOR_BPS = 5_000              // 50% - portion of debt repaid per liquidation
MAX_COLLATERAL_FACTOR_BPS = 8_500    // 85% - maximum LTV allowed
LTV_BUFFER_BPS = 500                  // 5% - buffer between borrow limit and liquidation
LIQUIDATION_INCENTIVE_BPS = 300       // 3% - bonus for liquidators
```

**Key Insight**: 
- Max borrow: 80% LTV (85% - 5% buffer)
- Liquidation threshold: 85% LTV
- Buffer creates safety zone: borrow at 80%, liquidate at 85%

### EMA Parameters
```rust
MIN_HALF_LIFE = 60                    // 1 minute minimum
MAX_HALF_LIFE = 43_200                // 12 hours maximum
NATURAL_LOG_OF_TWO_NAD = 693_147_180  // ln(2) * NAD for calculations
TAYLOR_TERMS = 5                      // Taylor series precision
```

### Interest Rate Model
```rust
INITIAL_RATE_BPS = 200                // 2% starting rate
MIN_RATE_BPS = 100                    // 1% minimum rate
TARGET_UTIL_START_BPS = 5_000         // 50% - optimal utilization start
TARGET_UTIL_END_BPS = 8_500           // 85% - optimal utilization end
SECONDS_PER_YEAR = 31_536_000         // For APR calculations
```

### Other
```rust
MIN_LIQUIDITY = 1_000                 // Minimum pool liquidity
FLASHLOAN_FEE_BPS = 5                 // 0.05% flash loan fee
PAIR_CREATION_FEE_LAMPORTS = 200_000_000  // 0.2 SOL to create pair
```

---

## 2. EMA Pricing Mechanism (from `math.rs` and `pair.rs`)

### Formula
```rust
// Exponential Moving Average with time-weighting
EMA_new = input + (last_ema - input) * α

where:
  α (alpha) = exp(-dt / τ)
  dt = time_elapsed (seconds since last update)
  τ (tau) = half_life / ln(2)
  
// Expanded:
exp_time = half_life / ln(2)
x = dt / exp_time
α = exp(-x)

// Final formula:
EMA_new = (input * (1 - α) + last_ema * α)
```

### Python Translation
```python
import math

def compute_ema(last_ema, last_update_time, current_spot_price, 
                current_time, half_life):
    """
    Compute exponential moving average with time-weighting.
    
    Args:
        last_ema: Previous EMA value (NAD-scaled, e.g., 1e9 = 1.0)
        last_update_time: Unix timestamp of last update
        current_spot_price: Current spot price (NAD-scaled)
        current_time: Current unix timestamp
        half_life: Half-life in seconds (e.g., 60 = 1 minute)
    
    Returns:
        Updated EMA value (NAD-scaled)
    """
    NAD = 1_000_000_000
    LN_2 = 0.693147180  # ln(2)
    
    dt = current_time - last_update_time
    
    if dt <= 0 or half_life <= 0:
        return last_ema
    
    # If first initialization
    if last_ema == 0:
        return current_spot_price
    
    # Calculate decay factor: α = exp(-dt * ln(2) / half_life)
    exp_time = half_life / LN_2
    x = dt / exp_time
    alpha = math.exp(-x)
    
    # EMA update
    new_ema = current_spot_price * (1 - alpha) + last_ema * alpha
    
    return int(new_ema)
```

### Key Properties
1. **Half-Life Behavior**: 
   - After 1 half-life: EMA moves 50% toward spot
   - After 2 half-lives: EMA moves 75% toward spot
   - After 3 half-lives: EMA moves 87.5% toward spot

2. **Smoothing Effect**:
   - Short half-life (60s): Responsive but less manipulation-resistant
   - Long half-life (300s): More resistant but slower to react to legitimate changes
   - Trade-off between responsiveness and security

3. **Attack Resistance**:
   - Single-block manipulation: Minimal impact (1-2% movement at 60s half-life)
   - Multi-block manipulation: Requires sustained price pressure
   - Cost: Attacker must maintain manipulation for multiple half-lives

---

## 3. Spot Price Calculation (from `pair.rs`)

### Formula
```rust
// Price of token0 in terms of token1
spot_price0 = (reserve1 * NAD) / reserve0

// Price of token1 in terms of token0
spot_price1 = (reserve0 * NAD) / reserve1
```

### Python Translation
```python
def calculate_spot_price(reserve_base, reserve_quote):
    """
    Calculate spot price from AMM reserves.
    
    Args:
        reserve_base: Reserve of base token (raw amount)
        reserve_quote: Reserve of quote token (raw amount)
    
    Returns:
        Spot price (NAD-scaled): quote per base
    """
    NAD = 1_000_000_000
    
    if reserve_base == 0:
        return 0
    
    return (reserve_quote * NAD) // reserve_base
```

---

## 4. Dynamic Collateral Factor (from `gamm_math.rs`)

### Full Formula (Already extracted in previous read)
```rust
// Step 1: Calculate collateral value at EMA price
V = collateral_amount * ema_price / NAD

// Step 2: Calculate base CF from AMM curve
if dynamic_cf_enabled:
    Y_curve = curve_y_from_v(V, debt_reserve)
    base_cf_bps = (Y_curve * BPS_DENOMINATOR) / V
else:
    base_cf_bps = fixed_cf_bps

// Step 3: Apply pessimistic divergence cap
liquidation_cf_bps = min(base_cf_bps, base_cf_bps * spot_price / ema_price)
liquidation_cf_bps = clamp(liquidation_cf_bps, 100, 8500)  // 1% min, 85% max

// Step 4: Apply LTV buffer
max_allowed_cf_bps = liquidation_cf_bps - LTV_BUFFER_BPS

// Step 5: Calculate max borrow
max_borrow = V * max_allowed_cf_bps / BPS_DENOMINATOR
```

### AMM Curve Solution (`curve_y_from_v`)
```rust
// Solve Y from constant product curve: Y = V * (1 - Y/R1)^2
// where V = collateral value, R1 = debt reserve
//
// Solution: Y = R1 * t
// where t = 2a / (2a + 1 + sqrt(4a + 1))
// and a = V / R1

a = V / R1
t = (2 * a) / (2 * a + 1 + sqrt(4 * a + 1))
Y = R1 * t
```

### Key Properties
1. **Slippage Awareness**: CF decreases as borrow size increases relative to pool depth
2. **Pessimistic Protection**: CF capped when spot < EMA (prevents front-running)
3. **Max CF Cap**: Never exceeds 85% even in deep liquidity
4. **LTV Buffer**: Creates 5% safety zone between max borrow and liquidation

---

## 5. Liquidation Logic (from `liquidate.rs`)

### Liquidation Conditions
```rust
// Position is liquidatable if:
debt_amount >= collateral_value * liquidation_cf_bps / BPS_DENOMINATOR

// Liquidation CF is the pessimistic CF (no buffer applied)
// Max allowed CF (for borrowing) has 5% buffer subtracted
```

### Liquidation Amounts
```rust
// Check if insolvent (debt > collateral value)
is_insolvent = debt_amount > collateral_value

if is_insolvent:
    // Full liquidation
    debt_to_repay = debt_amount
else:
    // Partial liquidation (50%)
    debt_to_repay = min(debt_amount, debt_amount * CLOSE_FACTOR_BPS / BPS_DENOMINATOR)

// Calculate collateral to seize
collateral_to_seize = debt_to_repay * NAD / collateral_ema_price
collateral_to_seize = min(collateral_to_seize, user_collateral)

// Liquidator bonus (3%)
liquidator_bonus = collateral_to_seize * LIQUIDATION_INCENTIVE_BPS / BPS_DENOMINATOR

// Remaining goes to reserves
collateral_to_reserves = collateral_to_seize - liquidator_bonus
```

### Key Properties
1. **Partial Liquidation**: Only 50% liquidated if collateral covers debt
2. **Full Liquidation**: 100% if insolvent (bad debt scenario)
3. **Liquidator Incentive**: 3% bonus to encourage timely liquidations
4. **Bad Debt Socialization**: Remaining losses distributed to LPs

---

## 6. Summary: Complete GAMM Mechanics

### Borrow Flow
```
1. User deposits collateral (e.g., 100 SOL)
2. System calculates:
   - Spot price (from AMM reserves)
   - EMA price (time-weighted average)
   - Dynamic CF (from curve_y_from_v)
   - Pessimistic CF (min of base CF and spot/EMA adjusted)
   - Max allowed CF (pessimistic - 5% buffer)
3. Max borrow = collateral_value * max_allowed_cf_bps / 10000
4. User borrows up to max (e.g., 80 USDC if SOL at $1)
```

### Liquidation Flow
```
1. Price drops (e.g., SOL falls to $0.90)
2. EMA lags behind spot (EMA might be $0.95)
3. System recalculates position health:
   - collateral_value = 100 SOL * $0.95 = $95
   - liquidation_threshold = $95 * 0.85 = $80.75
   - current_debt = $80
4. If debt >= liquidation_threshold: LIQUIDATABLE
5. Liquidator repays 50% of debt ($40)
6. Liquidator receives ~$41.2 collateral (40/0.95 + 3% bonus)
7. Position remains with 50% debt and reduced collateral
```

### Price Update Flow
```
Every transaction:
1. Update time-weighted EMA (spot → EMA smoothing)
2. Recalculate dynamic CF (based on pool depth)
3. Apply pessimistic cap (spot/EMA divergence protection)
4. Update all position health scores
5. Check for liquidatable positions
```

---

## 7. Simulation Implementation Priorities

### Phase 1: Core Mechanics ✅
- [x] EMA calculation
- [x] Spot price calculation
- [x] Dynamic CF calculation
- [x] Liquidation logic

### Phase 2: Configuration System (Next)
- [ ] Modular toggles (EMA on/off, Dynamic CF on/off, etc.)
- [ ] Parameter adjustment (half-life, max CF, etc.)
- [ ] Preset configurations (Traditional, Full GAMM, etc.)

### Phase 3: Pool State Management
- [ ] Reserve tracking
- [ ] Position management
- [ ] Time-series stepping
- [ ] Event logging

---

## 8. Key Questions Answered

**Q: What is the default half-life?**  
A: Not specified in constants, but range is 60s (1min) to 43,200s (12hr). Will test multiple values: 60s, 120s, 300s.

**Q: How quickly does EMA respond?**  
A: At 60s half-life, EMA moves ~50% toward spot in 1 minute. At 300s, takes 5 minutes for 50% movement.

**Q: What's the maximum leverage?**  
A: 80% LTV max (85% CF cap - 5% buffer), meaning ~5x leverage on most conservative calculation.

**Q: When does pessimistic cap trigger?**  
A: Whenever spot < EMA, CF is reduced proportionally to prevent borrowing against stale EMA.

---

**Status**: Contract analysis complete. Ready to build simulation engine.
**Next**: Set up Python project structure and implement core modules.

