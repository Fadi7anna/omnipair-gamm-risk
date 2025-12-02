"""
Dynamic Collateral Factor Calculator
Implements slippage-aware and pessimistic CF logic from OmniPair
"""

import math
from typing import Optional, Tuple
from config import NAD, BPS_DENOMINATOR, MAX_COLLATERAL_FACTOR_BPS, LTV_BUFFER_BPS


def curve_y_from_v(v: int, r1: int) -> int:
    """
    Exact AMM curve solution: given collateral value V and debt reserve R1,
    calculate max borrowable Y that maintains constant product invariant.
    
    Formula:
        Y = R1 * t
        where t = 2a / (2a + 1 + sqrt(4a + 1))
        and a = V / R1
    
    This represents the maximum amount that can be borrowed from the pool
    without breaking the xy=k invariant.
    
    Args:
        v: Collateral value at EMA price (NAD-scaled)
        r1: Debt token reserve in pool (NAD-scaled)
    
    Returns:
        Maximum borrowable amount Y (NAD-scaled)
    """
    if v == 0 or r1 == 0:
        return 0
    
    # a_scaled = (V/R1) * NAD
    a_scaled = (v * NAD) // r1
    
    # sqrt_term = sqrt(4a + 1) * NAD
    four_a_plus_one = (4 * a_scaled) + NAD
    sqrt_term = int(math.sqrt(four_a_plus_one * NAD))
    
    # numerator = 2a * NAD
    numerator = 2 * a_scaled * NAD
    
    # denominator = (2a + 1 + sqrt(4a+1)) * NAD
    denominator = (2 * a_scaled) + NAD + sqrt_term
    
    if denominator == 0:
        return 0
    
    # t_scaled = numerator / denominator
    t_scaled = numerator // denominator
    
    # Y = R1 * t
    y = (r1 * t_scaled) // NAD
    
    return y


def get_pessimistic_cf_bps(
    base_cf_bps: int,
    spot_price: int,
    ema_price: int
) -> int:
    """
    Apply pessimistic divergence cap to prevent EMA front-running.
    
    Formula:
        CF_pessimistic = min(CF_base, CF_base * spot/ema)
    
    Clamped to [100, MAX_COLLATERAL_FACTOR_BPS] basis points.
    
    Args:
        base_cf_bps: Base collateral factor (from dynamic calc or fixed)
        spot_price: Current spot price (NAD-scaled)
        ema_price: EMA price (NAD-scaled)
    
    Returns:
        Pessimistic CF in basis points
    """
    if ema_price == 0:
        return 100  # Minimum 1%
    
    # Shrink CF proportionally if spot < ema
    shrunk_cf = (spot_price * base_cf_bps) // ema_price
    
    # Take minimum (pessimistic)
    cf_bps = min(base_cf_bps, shrunk_cf)
    
    # Clamp to valid range
    cf_bps = max(100, cf_bps)  # Floor at 1%
    cf_bps = min(MAX_COLLATERAL_FACTOR_BPS, cf_bps)  # Cap at 85%
    
    return cf_bps


def calculate_dynamic_cf(
    collateral_amount: int,
    collateral_ema_price: int,
    debt_reserve: int
) -> int:
    """
    Calculate dynamic collateral factor based on AMM curve impact.
    
    Args:
        collateral_amount: Amount of collateral (NAD-scaled)
        collateral_ema_price: EMA price of collateral (NAD-scaled)
        debt_reserve: Total debt token reserve in pool (NAD-scaled)
    
    Returns:
        Dynamic CF in basis points
    """
    if debt_reserve == 0:
        return 0
    
    # V = collateral value at EMA price
    v = (collateral_amount * collateral_ema_price) // NAD
    
    if v == 0:
        return 0
    
    # Calculate max borrowable from curve
    y_curve = curve_y_from_v(v, debt_reserve)
    
    # CF = Y / V (as basis points)
    cf_bps = (y_curve * BPS_DENOMINATOR) // v
    
    return cf_bps


def pessimistic_max_debt(
    collateral_amount: int,
    collateral_ema_price: int,
    collateral_spot_price: int,
    debt_reserve: int,
    fixed_cf_bps: Optional[int] = None,
    use_dynamic_cf: bool = True,
    use_pessimistic_cap: bool = True,
    use_ltv_buffer: bool = True
) -> Tuple[int, int, int]:
    """
    Calculate maximum debt and collateral factors (MODULAR VERSION).
    
    This is the core function that can be configured to enable/disable
    different OmniPair protections for comparative analysis.
    
    Args:
        collateral_amount: Amount of collateral (NAD-scaled)
        collateral_ema_price: EMA price of collateral (NAD-scaled)
        collateral_spot_price: Spot price of collateral (NAD-scaled)
        debt_reserve: Debt token reserve in pool (NAD-scaled)
        fixed_cf_bps: If provided, use this instead of dynamic CF
        use_dynamic_cf: If True and no fixed_cf, calculate dynamic CF
        use_pessimistic_cap: If True, apply spot/EMA divergence cap
        use_ltv_buffer: If True, apply LTV buffer (5%)
    
    Returns:
        Tuple of (max_borrow_limit, max_allowed_cf_bps, liquidation_cf_bps)
    """
    # Sanity checks
    if collateral_amount == 0 or collateral_ema_price == 0 or collateral_spot_price == 0:
        return (0, 0, 0)
    
    # V = collateral value at EMA price
    v = (collateral_amount * collateral_ema_price) // NAD
    
    # ===== Step 1: Determine Base CF =====
    if fixed_cf_bps is not None:
        # Fixed CF mode (traditional lending)
        base_cf_bps = fixed_cf_bps
    elif use_dynamic_cf:
        # Dynamic CF mode (OmniPair innovation)
        if debt_reserve == 0:
            return (0, 0, 0)
        base_cf_bps = calculate_dynamic_cf(collateral_amount, collateral_ema_price, debt_reserve)
    else:
        # Default fallback (shouldn't happen)
        base_cf_bps = 7500  # 75%
    
    # ===== Step 2: Apply Pessimistic Cap (if enabled) =====
    if use_pessimistic_cap:
        liquidation_cf_bps = get_pessimistic_cf_bps(
            base_cf_bps,
            collateral_spot_price,
            collateral_ema_price
        )
    else:
        # No pessimistic cap: use base CF directly
        liquidation_cf_bps = min(base_cf_bps, MAX_COLLATERAL_FACTOR_BPS)
    
    # ===== Step 3: Apply LTV Buffer (if enabled) =====
    if use_ltv_buffer:
        buffer = LTV_BUFFER_BPS
    else:
        buffer = 0
    
    max_allowed_cf_bps = max(0, liquidation_cf_bps - buffer)
    
    # ===== Step 4: Calculate Max Borrow Limit =====
    max_borrow = (v * max_allowed_cf_bps) // BPS_DENOMINATOR
    
    return (max_borrow, max_allowed_cf_bps, liquidation_cf_bps)


class CollateralFactorCalculator:
    """
    Configurable collateral factor calculator that can operate in
    different modes for comparative analysis.
    """
    
    def __init__(
        self,
        use_dynamic_cf: bool = True,
        use_pessimistic_cap: bool = True,
        use_ltv_buffer: bool = True,
        fixed_cf_bps: Optional[int] = None,
        max_cf_bps: int = MAX_COLLATERAL_FACTOR_BPS
    ):
        """
        Initialize CF calculator with configuration.
        
        Args:
            use_dynamic_cf: Enable AMM curve-based dynamic CF
            use_pessimistic_cap: Enable spot/EMA divergence protection
            use_ltv_buffer: Enable LTV safety buffer
            fixed_cf_bps: If set, use this fixed CF instead of dynamic
            max_cf_bps: Maximum allowed CF cap
        """
        self.use_dynamic_cf = use_dynamic_cf
        self.use_pessimistic_cap = use_pessimistic_cap
        self.use_ltv_buffer = use_ltv_buffer
        self.fixed_cf_bps = fixed_cf_bps
        self.max_cf_bps = max_cf_bps
    
    def calculate(
        self,
        collateral_amount: int,
        collateral_ema_price: int,
        collateral_spot_price: int,
        debt_reserve: int
    ) -> Tuple[int, int, int]:
        """
        Calculate max debt and CF using configured settings.
        
        Returns:
            (max_borrow, max_allowed_cf_bps, liquidation_cf_bps)
        """
        return pessimistic_max_debt(
            collateral_amount,
            collateral_ema_price,
            collateral_spot_price,
            debt_reserve,
            fixed_cf_bps=self.fixed_cf_bps,
            use_dynamic_cf=self.use_dynamic_cf,
            use_pessimistic_cap=self.use_pessimistic_cap,
            use_ltv_buffer=self.use_ltv_buffer
        )


# ============================================================================
# UNIT TESTS
# ============================================================================

def test_curve_y_from_v():
    """Test AMM curve solution"""
    # Small borrow from large pool: CF should be high
    v = 100 * NAD  # $100 collateral value
    r1 = 1_000_000 * NAD  # $1M pool
    
    y = curve_y_from_v(v, r1)
    cf = (y * BPS_DENOMINATOR) // v
    
    # Should allow high CF due to deep liquidity
    assert cf > 8000, f"Deep pool should allow >80% CF, got {cf/100}%"
    print(f"✅ Curve test (deep pool): CF = {cf/100}%")
    
    # Large borrow from small pool: CF should be lower
    v2 = 100 * NAD
    r1_2 = 200 * NAD  # Only $200 pool
    
    y2 = curve_y_from_v(v2, r1_2)
    cf2 = (y2 * BPS_DENOMINATOR) // v2
    
    assert cf2 < cf, "Shallow pool should have lower CF"
    print(f"✅ Curve test (shallow pool): CF = {cf2/100}%")


def test_pessimistic_cap():
    """Test pessimistic divergence cap"""
    base_cf = 8000  # 80%
    
    # Case 1: Spot = EMA (no divergence)
    price = 1_000_000_000
    cf1 = get_pessimistic_cf_bps(base_cf, price, price)
    assert cf1 == base_cf, "No divergence should keep CF unchanged"
    print(f"✅ Pessimistic cap (spot=ema): {cf1/100}%")
    
    # Case 2: Spot < EMA (price falling)
    spot_falling = 900_000_000  # -10%
    ema_stale = 1_000_000_000
    cf2 = get_pessimistic_cf_bps(base_cf, spot_falling, ema_stale)
    
    # CF should shrink proportionally
    expected_shrink = (8000 * 900) // 1000  # 7200 bps = 72%
    assert abs(cf2 - expected_shrink) < 10, f"CF should shrink to ~{expected_shrink}, got {cf2}"
    print(f"✅ Pessimistic cap (spot<ema): {cf2/100}% (shrunk from {base_cf/100}%)")
    
    # Case 3: Spot > EMA (price rising)
    spot_rising = 1_100_000_000  # +10%
    cf3 = get_pessimistic_cf_bps(base_cf, spot_rising, ema_stale)
    
    # CF should NOT increase (pessimistic)
    assert cf3 == base_cf, "Rising price should not increase CF (pessimistic)"
    print(f"✅ Pessimistic cap (spot>ema): {cf3/100}% (not increased)")


def test_dynamic_vs_fixed_cf():
    """Test dynamic CF vs fixed CF"""
    collateral = 100 * NAD
    ema_price = 1_000_000_000
    spot_price = 1_000_000_000
    
    # Deep pool: dynamic CF should be high
    deep_reserve = 1_000_000 * NAD
    max_debt_dynamic, cf_dynamic, _ = pessimistic_max_debt(
        collateral, ema_price, spot_price, deep_reserve,
        fixed_cf_bps=None, use_dynamic_cf=True
    )
    
    # Fixed CF: always 75%
    max_debt_fixed, cf_fixed, _ = pessimistic_max_debt(
        collateral, ema_price, spot_price, deep_reserve,
        fixed_cf_bps=7500, use_dynamic_cf=False
    )
    
    print(f"✅ Dynamic CF (deep pool): {cf_dynamic/100}%, max borrow: ${max_debt_dynamic/NAD:.0f}")
    print(f"✅ Fixed CF: {cf_fixed/100}%, max borrow: ${max_debt_fixed/NAD:.0f}")
    
    assert cf_dynamic > cf_fixed, "Dynamic CF should be higher in deep pool"


def test_ltv_buffer():
    """Test LTV buffer creates safety zone"""
    collateral = 100 * NAD
    price = 1_000_000_000
    reserve = 1_000_000 * NAD
    
    # With buffer
    _, cf_with_buffer, liq_cf_with = pessimistic_max_debt(
        collateral, price, price, reserve,
        use_ltv_buffer=True
    )
    
    # Without buffer
    _, cf_no_buffer, liq_cf_no = pessimistic_max_debt(
        collateral, price, price, reserve,
        use_ltv_buffer=False
    )
    
    # Buffer should create 5% gap
    gap = liq_cf_with - cf_with_buffer
    assert gap == LTV_BUFFER_BPS, f"Buffer should be {LTV_BUFFER_BPS}bps, got {gap}bps"
    
    print(f"✅ LTV buffer test:")
    print(f"   Max borrow CF: {cf_with_buffer/100}%")
    print(f"   Liquidation CF: {liq_cf_with/100}%")
    print(f"   Buffer: {gap/100}%")


def run_all_tests():
    """Run all CF calculator tests"""
    print("\n🧪 Running Collateral Factor Tests...\n")
    test_curve_y_from_v()
    test_pessimistic_cap()
    test_dynamic_vs_fixed_cf()
    test_ltv_buffer()
    print("\n✅ All CF tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
    
    # Example: Compare configurations
    print("="*70)
    print("\n📊 Configuration Comparison Example:\n")
    
    collateral = 1000 * NAD  # 1000 tokens
    price = 1_500_000_000  # $1.50 per token
    reserve = 500_000 * NAD  # $500K pool
    
    configs = [
        ("Traditional (Fixed 75%)", {"fixed_cf_bps": 7500, "use_dynamic_cf": False, "use_pessimistic_cap": False, "use_ltv_buffer": False}),
        ("Only Dynamic CF", {"use_dynamic_cf": True, "use_pessimistic_cap": False, "use_ltv_buffer": False}),
        ("Dynamic + Pessimistic", {"use_dynamic_cf": True, "use_pessimistic_cap": True, "use_ltv_buffer": False}),
        ("Full GAMM", {"use_dynamic_cf": True, "use_pessimistic_cap": True, "use_ltv_buffer": True}),
    ]
    
    for name, kwargs in configs:
        max_borrow, max_cf, liq_cf = pessimistic_max_debt(
            collateral, price, price, reserve, **kwargs
        )
        print(f"{name}:")
        print(f"  Max CF: {max_cf/100}%, Liq CF: {liq_cf/100}%, Max Borrow: ${max_borrow/NAD:,.0f}\n")

