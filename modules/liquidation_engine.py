"""
Liquidation Engine
Handles position liquidation logic with configurable parameters
"""

from typing import Dict, Optional
from config import NAD, BPS_DENOMINATOR, CLOSE_FACTOR_BPS, LIQUIDATION_INCENTIVE_BPS


def is_liquidatable(
    collateral_value: int,
    debt_amount: int,
    liquidation_cf_bps: int
) -> bool:
    """
    Check if position is undercollateralized and liquidatable.
    
    A position is liquidatable when:
        debt >= collateral_value * liquidation_cf
    
    Args:
        collateral_value: Value of collateral at current price (NAD-scaled)
        debt_amount: Current debt amount (NAD-scaled)
        liquidation_cf_bps: Liquidation threshold CF in basis points
    
    Returns:
        True if position can be liquidated
    """
    if collateral_value == 0:
        return debt_amount > 0
    
    borrow_limit = (collateral_value * liquidation_cf_bps) // BPS_DENOMINATOR
    
    return debt_amount >= borrow_limit


def calculate_liquidation(
    collateral_amount: int,
    collateral_price: int,
    debt_amount: int,
    liquidation_cf_bps: int,
    close_factor_bps: int = CLOSE_FACTOR_BPS,
    liquidation_incentive_bps: int = LIQUIDATION_INCENTIVE_BPS
) -> Dict:
    """
    Calculate liquidation amounts and outcomes.
    
    Args:
        collateral_amount: Amount of collateral (NAD-scaled)
        collateral_price: Price of collateral (use EMA if enabled) (NAD-scaled)
        debt_amount: Current debt amount (NAD-scaled)
        liquidation_cf_bps: Liquidation threshold CF
        close_factor_bps: Portion of debt to repay (5000 = 50%)
        liquidation_incentive_bps: Bonus for liquidator (300 = 3%)
    
    Returns:
        Dictionary with liquidation details
    """
    # Calculate collateral value
    collateral_value = (collateral_amount * collateral_price) // NAD
    
    # Calculate borrow limit at liquidation threshold
    borrow_limit = (collateral_value * liquidation_cf_bps) // BPS_DENOMINATOR
    
    # Check if liquidatable
    if debt_amount < borrow_limit:
        return {
            "liquidatable": False,
            "health_factor": (borrow_limit * 100) // debt_amount if debt_amount > 0 else 999,
            "collateral_value": collateral_value,
            "debt_amount": debt_amount,
            "borrow_limit": borrow_limit,
        }
    
    # Check if insolvent (debt > total collateral value)
    is_insolvent = debt_amount > collateral_value
    
    # Determine debt to repay
    if is_insolvent:
        # Full liquidation (bad debt scenario)
        debt_to_repay = debt_amount
    else:
        # Partial liquidation
        partial_debt = (debt_amount * close_factor_bps) // BPS_DENOMINATOR
        debt_to_repay = min(debt_amount, partial_debt)
    
    # Calculate collateral to seize
    # collateral_to_seize = debt_to_repay / price
    collateral_to_seize = (debt_to_repay * NAD) // collateral_price
    collateral_to_seize = min(collateral_to_seize, collateral_amount)
    
    # Liquidator bonus
    liquidator_bonus = (collateral_to_seize * liquidation_incentive_bps) // BPS_DENOMINATOR
    
    # Remaining collateral goes to reserves
    collateral_to_reserves = max(0, collateral_to_seize - liquidator_bonus)
    
    # Calculate bad debt (if any)
    bad_debt = 0
    if is_insolvent:
        # Bad debt = debt that can't be covered by collateral
        bad_debt = max(0, debt_amount - collateral_value)
    
    # Remaining position after liquidation
    remaining_collateral = collateral_amount - collateral_to_seize
    remaining_debt = debt_amount - debt_to_repay
    
    # Calculate profit for liquidator
    liquidator_profit_usd = (liquidator_bonus * collateral_price) // NAD - debt_to_repay
    
    return {
        "liquidatable": True,
        "is_insolvent": is_insolvent,
        "debt_to_repay": debt_to_repay,
        "collateral_seized": collateral_to_seize,
        "liquidator_bonus": liquidator_bonus,
        "collateral_to_reserves": collateral_to_reserves,
        "bad_debt": bad_debt,
        "remaining_collateral": remaining_collateral,
        "remaining_debt": remaining_debt,
        "liquidator_profit_usd": liquidator_profit_usd,
        "health_factor": 0,  # Underwater
        "collateral_value": collateral_value,
        "debt_amount": debt_amount,
        "borrow_limit": borrow_limit,
    }


class LiquidationEngine:
    """
    Configurable liquidation engine for scenario testing.
    """
    
    def __init__(
        self,
        close_factor_bps: int = CLOSE_FACTOR_BPS,
        liquidation_incentive_bps: int = LIQUIDATION_INCENTIVE_BPS,
        enable_partial_liquidation: bool = True
    ):
        """
        Initialize liquidation engine.
        
        Args:
            close_factor_bps: Portion of debt repaid per liquidation
            liquidation_incentive_bps: Bonus for liquidators
            enable_partial_liquidation: If False, always full liquidation
        """
        self.close_factor_bps = close_factor_bps if enable_partial_liquidation else 10_000
        self.liquidation_incentive_bps = liquidation_incentive_bps
        self.enable_partial_liquidation = enable_partial_liquidation
        
        # Tracking
        self.total_liquidations = 0
        self.total_bad_debt = 0
        self.total_liquidated_debt = 0
        self.total_seized_collateral = 0
    
    def check_and_liquidate(
        self,
        collateral_amount: int,
        collateral_price: int,
        debt_amount: int,
        liquidation_cf_bps: int
    ) -> Dict:
        """
        Check position and execute liquidation if needed.
        
        Returns:
            Liquidation result dictionary
        """
        result = calculate_liquidation(
            collateral_amount,
            collateral_price,
            debt_amount,
            liquidation_cf_bps,
            self.close_factor_bps,
            self.liquidation_incentive_bps
        )
        
        # Update tracking
        if result["liquidatable"]:
            self.total_liquidations += 1
            self.total_bad_debt += result["bad_debt"]
            self.total_liquidated_debt += result["debt_to_repay"]
            self.total_seized_collateral += result["collateral_seized"]
        
        return result
    
    def get_statistics(self) -> Dict:
        """Get liquidation statistics"""
        return {
            "total_liquidations": self.total_liquidations,
            "total_bad_debt": self.total_bad_debt,
            "total_liquidated_debt": self.total_liquidated_debt,
            "total_seized_collateral": self.total_seized_collateral,
            "bad_debt_rate": (
                (self.total_bad_debt * 100) // self.total_liquidated_debt
                if self.total_liquidated_debt > 0 else 0
            )
        }
    
    def reset(self):
        """Reset statistics"""
        self.total_liquidations = 0
        self.total_bad_debt = 0
        self.total_liquidated_debt = 0
        self.total_seized_collateral = 0


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_health_factor(
    collateral_value: int,
    debt_amount: int,
    liquidation_cf_bps: int
) -> float:
    """
    Calculate position health factor.
    
    Health Factor = (collateral_value * liquidation_cf) / debt
    
    - HF > 1.0: Healthy
    - HF = 1.0: At liquidation threshold
    - HF < 1.0: Liquidatable
    
    Args:
        collateral_value: Value of collateral (NAD-scaled)
        debt_amount: Current debt (NAD-scaled)
        liquidation_cf_bps: Liquidation threshold CF
    
    Returns:
        Health factor (e.g., 1.5 = 150%)
    """
    if debt_amount == 0:
        return 999.0  # No debt = infinite health
    
    borrow_limit = (collateral_value * liquidation_cf_bps) // BPS_DENOMINATOR
    
    return borrow_limit / debt_amount


def estimate_liquidation_price(
    collateral_amount: int,
    initial_price: int,
    debt_amount: int,
    liquidation_cf_bps: int
) -> int:
    """
    Estimate price at which position becomes liquidatable.
    
    Liquidation when: debt >= collateral_value * liquidation_cf
    Therefore: price_liq = debt / (collateral_amount * liquidation_cf)
    
    Args:
        collateral_amount: Amount of collateral (NAD-scaled)
        initial_price: Entry price (NAD-scaled)
        debt_amount: Current debt (NAD-scaled)
        liquidation_cf_bps: Liquidation CF
    
    Returns:
        Liquidation price (NAD-scaled)
    """
    if collateral_amount == 0:
        return 0
    
    # price_liq = debt / (collateral * CF)
    price_liq = (debt_amount * BPS_DENOMINATOR) // (collateral_amount * liquidation_cf_bps // BPS_DENOMINATOR)
    
    return price_liq


def calculate_liquidation_cascade(
    positions: list,
    price_path: list,
    liquidation_cf_bps: int,
    close_factor_bps: int = CLOSE_FACTOR_BPS
) -> Dict:
    """
    Simulate liquidation cascade as price moves.
    
    Args:
        positions: List of position dicts with collateral_amount and debt_amount
        price_path: List of prices over time
        liquidation_cf_bps: Liquidation threshold
        close_factor_bps: Close factor
    
    Returns:
        Dict with cascade statistics
    """
    liquidations = []
    total_bad_debt = 0
    
    for i, price in enumerate(price_path):
        for j, position in enumerate(positions):
            if position.get("liquidated"):
                continue
            
            result = calculate_liquidation(
                position["collateral_amount"],
                price,
                position["debt_amount"],
                liquidation_cf_bps,
                close_factor_bps
            )
            
            if result["liquidatable"]:
                position["liquidated"] = True
                position["liquidation_step"] = i
                position["liquidation_price"] = price
                total_bad_debt += result["bad_debt"]
                
                liquidations.append({
                    "position_id": j,
                    "step": i,
                    "price": price,
                    **result
                })
    
    return {
        "total_liquidations": len(liquidations),
        "total_bad_debt": total_bad_debt,
        "liquidation_events": liquidations,
        "positions_final": positions
    }


# ============================================================================
# UNIT TESTS
# ============================================================================

def test_health_factor():
    """Test health factor calculation"""
    collateral_value = 1000 * NAD  # $1000
    debt = 800 * NAD  # $800
    liq_cf = 8500  # 85%
    
    hf = calculate_health_factor(collateral_value, debt, liq_cf)
    
    # HF = (1000 * 0.85) / 800 = 1.0625
    assert 1.05 < hf < 1.07, f"Expected HF ~1.06, got {hf}"
    print(f"✅ Health factor test: {hf:.2f} (healthy)")
    
    # At liquidation threshold
    debt_at_liq = 850 * NAD
    hf_liq = calculate_health_factor(collateral_value, debt_at_liq, liq_cf)
    assert 0.99 < hf_liq < 1.01, f"At threshold HF should be ~1.0, got {hf_liq}"
    print(f"✅ Health factor at threshold: {hf_liq:.2f}")


def test_partial_liquidation():
    """Test partial liquidation (50%)"""
    collateral = 1000 * NAD  # 1000 tokens
    price = 1 * NAD  # $1/token
    debt = 900 * NAD  # $900 debt
    liq_cf = 8500  # 85% liquidation threshold
    
    result = calculate_liquidation(collateral, price, debt, liq_cf)
    
    assert result["liquidatable"], "Position should be liquidatable"
    assert not result["is_insolvent"], "Position should not be insolvent"
    
    # Should repay 50% of debt
    expected_repay = 450 * NAD
    assert abs(result["debt_to_repay"] - expected_repay) < NAD, f"Should repay ~450, got {result['debt_to_repay']/NAD}"
    
    # Remaining position should have 50% debt
    assert result["remaining_debt"] == debt - expected_repay
    
    print(f"✅ Partial liquidation test:")
    print(f"   Debt repaid: ${result['debt_to_repay']/NAD:.0f} (50%)")
    print(f"   Remaining debt: ${result['remaining_debt']/NAD:.0f}")
    print(f"   Bad debt: ${result['bad_debt']/NAD:.0f}")


def test_full_liquidation_insolvent():
    """Test full liquidation when insolvent"""
    collateral = 1000 * NAD
    price = 1 * NAD
    debt = 1100 * NAD  # Debt > collateral value = insolvent
    liq_cf = 8500
    
    result = calculate_liquidation(collateral, price, debt, liq_cf)
    
    assert result["liquidatable"], "Position should be liquidatable"
    assert result["is_insolvent"], "Position should be insolvent"
    
    # Should try to repay full debt
    assert result["debt_to_repay"] == debt
    
    # Bad debt = debt - collateral_value
    expected_bad_debt = 100 * NAD
    assert abs(result["bad_debt"] - expected_bad_debt) < NAD
    
    print(f"✅ Insolvent liquidation test:")
    print(f"   Debt: ${debt/NAD:.0f}")
    print(f"   Collateral value: ${(collateral*price)//NAD:.0f}")
    print(f"   Bad debt: ${result['bad_debt']/NAD:.0f}")


def test_liquidation_incentive():
    """Test liquidator receives bonus"""
    collateral = 1000 * NAD
    price = 1 * NAD
    debt = 900 * NAD
    liq_cf = 8500
    
    result = calculate_liquidation(collateral, price, debt, liq_cf, liquidation_incentive_bps=300)
    
    # Liquidator should get 3% bonus
    expected_bonus = (result["collateral_seized"] * 300) // BPS_DENOMINATOR
    assert abs(result["liquidator_bonus"] - expected_bonus) < 1000
    
    # Liquidator profit = bonus_value - debt_repaid
    assert result["liquidator_profit_usd"] > 0, "Liquidator should profit"
    
    print(f"✅ Liquidation incentive test:")
    print(f"   Collateral seized: {result['collateral_seized']/NAD:.0f} tokens")
    print(f"   Liquidator bonus: {result['liquidator_bonus']/NAD:.0f} tokens (3%)")
    print(f"   Liquidator profit: ${result['liquidator_profit_usd']/NAD:.2f}")


def test_liquidation_price_estimate():
    """Test liquidation price estimation"""
    collateral = 1000 * NAD
    initial_price = 2 * NAD  # $2/token
    debt = 1500 * NAD  # Borrowed $1500 at $2 price (75% LTV)
    liq_cf = 8500  # 85% liquidation threshold
    
    liq_price = estimate_liquidation_price(collateral, initial_price, debt, liq_cf)
    
    # Liquidation when: 1500 >= 1000 * price * 0.85
    # Therefore: price <= 1500 / (1000 * 0.85) = $1.765
    expected_liq_price = (debt * BPS_DENOMINATOR) // (collateral * liq_cf // BPS_DENOMINATOR)
    
    from config import nad_to_float
    print(f"✅ Liquidation price estimate:")
    print(f"   Entry price: ${nad_to_float(initial_price):.2f}")
    print(f"   Liquidation price: ${nad_to_float(liq_price):.3f}")
    print(f"   Price drop to liquidation: {((initial_price - liq_price) * 100 / initial_price):.1f}%")


def run_all_tests():
    """Run all liquidation tests"""
    print("\n🧪 Running Liquidation Engine Tests...\n")
    test_health_factor()
    test_partial_liquidation()
    test_full_liquidation_insolvent()
    test_liquidation_incentive()
    test_liquidation_price_estimate()
    print("\n✅ All liquidation tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
    
    print("="*70)
    print("\n📊 Liquidation Scenario Example:\n")
    
    # Example: Position through price crash
    collateral = 1000 * NAD
    initial_price = 100 * NAD  # $100/token
    debt = 75_000 * NAD  # Borrowed $75K (75% LTV)
    liq_cf = 8500  # 85%
    
    from config import nad_to_float
    
    # Price drops from $100 to $88 (liquidation threshold)
    liq_price = estimate_liquidation_price(collateral, initial_price, debt, liq_cf)
    print(f"Entry: 1000 tokens @ ${nad_to_float(initial_price)}, borrowed ${nad_to_float(debt)}")
    print(f"Liquidation price: ${nad_to_float(liq_price):.2f}\n")
    
    # Simulate price drops
    prices = [100, 95, 90, 88, 85, 80]
    for price_float in prices:
        price = price_float * NAD
        hf = calculate_health_factor((collateral * price) // NAD, debt, liq_cf)
        result = calculate_liquidation(collateral, price, debt, liq_cf)
        
        status = "🔴 LIQUIDATABLE" if result["liquidatable"] else "🟢 Healthy"
        print(f"Price ${price_float}: HF={hf:.2f} {status}")
        
        if result["liquidatable"] and not result.get("printed"):
            print(f"  → Repay ${nad_to_float(result['debt_to_repay']):.0f} (50%)")
            print(f"  → Seize {nad_to_float(result['collateral_seized']):.0f} tokens")
            print(f"  → Bad debt: ${nad_to_float(result['bad_debt']):.0f}")
            result["printed"] = True

