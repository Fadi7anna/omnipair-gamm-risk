"""
GAMM Pool State Manager
Orchestrates all components (EMA, CF, Liquidation) into complete pool simulation
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from config import (
    NAD, BPS_DENOMINATOR, SimulationConfig, 
    FULL_OMNIPAIR_GAMM, nad_to_float, float_to_nad
)
from ema_engine import PriceOracle
from collateral_factor import CollateralFactorCalculator, pessimistic_max_debt
from liquidation_engine import LiquidationEngine, calculate_health_factor


@dataclass
class BorrowerPosition:
    """Represents a single borrower's position"""
    id: int
    collateral_amount: int  # NAD-scaled
    debt_amount: int  # NAD-scaled
    entry_price: int  # NAD-scaled
    entry_time: int  # Unix timestamp
    liquidated: bool = False
    liquidation_time: Optional[int] = None
    liquidation_price: Optional[int] = None
    bad_debt_accrued: int = 0
    
    def get_health_factor(self, collateral_price: int, liquidation_cf_bps: int) -> float:
        """Calculate current health factor"""
        collateral_value = (self.collateral_amount * collateral_price) // NAD
        return calculate_health_factor(collateral_value, self.debt_amount, liquidation_cf_bps)


@dataclass
class PoolState:
    """Snapshot of pool state at a point in time"""
    timestamp: int
    reserve_base: int
    reserve_quote: int
    total_debt: int
    total_collateral: int
    spot_price: int
    ema_price: int
    average_cf_bps: int
    active_positions: int
    total_bad_debt: int
    protocol_health_pct: float


class GAMMPool:
    """
    Complete GAMM pool simulation with modular configuration.
    
    Orchestrates EMA pricing, dynamic CF, liquidations, and position management.
    """
    
    def __init__(
        self,
        config: SimulationConfig,
        initial_reserve_base: int,
        initial_reserve_quote: int,
        initial_timestamp: int = 0
    ):
        """
        Initialize GAMM pool.
        
        Args:
            config: Simulation configuration (determines which components are enabled)
            initial_reserve_base: Initial base token reserve (e.g., SOL)
            initial_reserve_quote: Initial quote token reserve (e.g., USDC)
            initial_timestamp: Starting timestamp
        """
        self.config = config
        
        # Pool reserves
        self.reserve_base = initial_reserve_base
        self.reserve_quote = initial_reserve_quote
        
        # Debt and collateral tracking
        self.total_debt = 0
        self.total_collateral_base = 0
        self.total_collateral_quote = 0
        
        # Time tracking
        self.current_time = initial_timestamp
        self.last_update = initial_timestamp
        
        # Component initialization
        self.price_oracle = PriceOracle(
            use_ema=config.ema_enabled,
            half_life=config.half_life if config.ema_enabled else 60
        )
        
        self.cf_calculator = CollateralFactorCalculator(
            use_dynamic_cf=config.dynamic_cf_enabled,
            use_pessimistic_cap=config.pessimistic_cap_enabled,
            use_ltv_buffer=config.ltv_buffer_enabled,
            fixed_cf_bps=config.fixed_cf_bps,
            max_cf_bps=config.max_cf_bps
        )
        
        self.liquidation_engine = LiquidationEngine(
            close_factor_bps=config.close_factor_bps,
            liquidation_incentive_bps=config.liquidation_incentive_bps,
            enable_partial_liquidation=config.partial_liquidation_enabled
        )
        
        # Position management
        self.positions: List[BorrowerPosition] = []
        self.next_position_id = 1
        
        # Event history
        self.state_history: List[PoolState] = []
        self.liquidation_events: List[Dict] = []
        
        # Initialize price oracle with initial spot price
        initial_spot = self.get_spot_price()
        self.price_oracle.get_price(initial_spot, initial_timestamp)
    
    def get_spot_price(self) -> int:
        """
        Calculate spot price from reserves: quote/base
        
        Returns:
            Spot price (NAD-scaled)
        """
        if self.reserve_base == 0:
            return 0
        return (self.reserve_quote * NAD) // self.reserve_base
    
    def get_lending_price(self, timestamp: int) -> int:
        """
        Get price used for lending calculations (EMA or spot based on config).
        
        Args:
            timestamp: Current timestamp
        
        Returns:
            Lending price (NAD-scaled)
        """
        spot = self.get_spot_price()
        return self.price_oracle.get_price(spot, timestamp)
    
    def update_reserves_from_price(self, new_price: int):
        """
        Update reserves to reflect new price (simulates AMM trades).
        
        In real AMM, trades change reserves. For simulation, we can
        adjust reserves to match target price.
        
        Args:
            new_price: Target price (NAD-scaled)
        """
        # Keep base reserve constant, adjust quote reserve
        self.reserve_quote = (self.reserve_base * new_price) // NAD
    
    def create_position(
        self,
        collateral_amount: int,
        target_ltv: float,
        timestamp: int
    ) -> BorrowerPosition:
        """
        Create new borrower position.
        
        Args:
            collateral_amount: Amount of base token collateral (NAD-scaled)
            target_ltv: Target loan-to-value ratio (e.g., 0.75 = 75%)
            timestamp: Position creation time
        
        Returns:
            New BorrowerPosition
        """
        # Get current price
        lending_price = self.get_lending_price(timestamp)
        spot_price = self.get_spot_price()
        
        # Calculate maximum borrow amount
        max_borrow, max_cf_bps, liq_cf_bps = self.cf_calculator.calculate(
            collateral_amount,
            lending_price,
            spot_price,
            self.reserve_quote
        )
        
        # Borrow at target LTV (percentage of max allowed)
        actual_borrow = int(max_borrow * target_ltv)
        
        # Create position
        position = BorrowerPosition(
            id=self.next_position_id,
            collateral_amount=collateral_amount,
            debt_amount=actual_borrow,
            entry_price=lending_price,
            entry_time=timestamp
        )
        
        self.next_position_id += 1
        self.positions.append(position)
        
        # Update pool state
        self.total_debt += actual_borrow
        self.total_collateral_base += collateral_amount
        
        # Reduce available reserves (debt is borrowed out)
        self.reserve_quote = max(0, self.reserve_quote - actual_borrow)
        
        return position
    
    def check_liquidations(self, timestamp: int) -> List[Dict]:
        """
        Check all positions for liquidation and execute if needed.
        
        Args:
            timestamp: Current timestamp
        
        Returns:
            List of liquidation event dictionaries
        """
        liquidations = []
        lending_price = self.get_lending_price(timestamp)
        spot_price = self.get_spot_price()
        
        for position in self.positions:
            if position.liquidated:
                continue
            
            # Get liquidation CF for this position
            _, _, liq_cf_bps = self.cf_calculator.calculate(
                position.collateral_amount,
                lending_price,
                spot_price,
                self.reserve_quote
            )
            
            # Check liquidation
            result = self.liquidation_engine.check_and_liquidate(
                position.collateral_amount,
                lending_price,
                position.debt_amount,
                liq_cf_bps
            )
            
            if result["liquidatable"]:
                # Execute liquidation
                position.liquidated = True
                position.liquidation_time = timestamp
                position.liquidation_price = lending_price
                position.bad_debt_accrued = result["bad_debt"]
                
                # Update position state
                position.collateral_amount = result["remaining_collateral"]
                position.debt_amount = result["remaining_debt"]
                
                # Update pool state
                self.total_debt -= result["debt_to_repay"]
                self.total_collateral_base -= result["collateral_seized"]
                
                # Collateral seized goes back to reserves
                # (minus liquidator bonus which leaves the system)
                self.reserve_base += result["collateral_to_reserves"]
                
                # Debt repaid goes back to reserves
                self.reserve_quote += result["debt_to_repay"]
                
                # Record event
                event = {
                    "timestamp": timestamp,
                    "position_id": position.id,
                    "price": lending_price,
                    "spot_price": spot_price,
                    "ema_price": lending_price if self.config.ema_enabled else spot_price,
                    **result
                }
                
                liquidations.append(event)
                self.liquidation_events.append(event)
        
        return liquidations
    
    def step(self, new_price: int, timestamp: int) -> PoolState:
        """
        Advance simulation by one time step.
        
        Args:
            new_price: New market price (NAD-scaled)
            timestamp: Current timestamp
        
        Returns:
            Current pool state
        """
        # Update time
        self.current_time = timestamp
        
        # Update reserves to reflect new price
        self.update_reserves_from_price(new_price)
        
        # Update lending price (triggers EMA update if enabled)
        lending_price = self.get_lending_price(timestamp)
        spot_price = self.get_spot_price()
        
        # Check and execute liquidations
        self.check_liquidations(timestamp)
        
        # Calculate average CF across active positions
        active_positions = [p for p in self.positions if not p.liquidated]
        if active_positions:
            total_cf = 0
            for pos in active_positions:
                _, _, liq_cf = self.cf_calculator.calculate(
                    pos.collateral_amount,
                    lending_price,
                    spot_price,
                    self.reserve_quote
                )
                total_cf += liq_cf
            avg_cf = total_cf // len(active_positions)
        else:
            avg_cf = 0
        
        # Calculate protocol health
        total_collateral_value = (self.total_collateral_base * lending_price) // NAD
        if self.total_debt > 0:
            protocol_health = ((total_collateral_value - self.total_debt) * 100) // self.total_debt
        else:
            protocol_health = 999
        
        # Create state snapshot
        state = PoolState(
            timestamp=timestamp,
            reserve_base=self.reserve_base,
            reserve_quote=self.reserve_quote,
            total_debt=self.total_debt,
            total_collateral=self.total_collateral_base,
            spot_price=spot_price,
            ema_price=lending_price,
            average_cf_bps=avg_cf,
            active_positions=len(active_positions),
            total_bad_debt=self.liquidation_engine.total_bad_debt,
            protocol_health_pct=protocol_health
        )
        
        self.state_history.append(state)
        self.last_update = timestamp
        
        return state
    
    def get_statistics(self) -> Dict:
        """Get comprehensive pool statistics"""
        active_positions = [p for p in self.positions if not p.liquidated]
        liquidated_positions = [p for p in self.positions if p.liquidated]
        
        total_borrowed = sum(p.debt_amount for p in self.positions)
        total_collateral_value = sum(
            (p.collateral_amount * p.entry_price) // NAD 
            for p in self.positions
        )
        
        return {
            "config_name": self.config.name,
            "total_positions": len(self.positions),
            "active_positions": len(active_positions),
            "liquidated_positions": len(liquidated_positions),
            "total_borrowed": total_borrowed,
            "total_bad_debt": self.liquidation_engine.total_bad_debt,
            "bad_debt_rate_bps": (
                (self.liquidation_engine.total_bad_debt * BPS_DENOMINATOR) // total_borrowed
                if total_borrowed > 0 else 0
            ),
            "total_liquidations": self.liquidation_engine.total_liquidations,
            "protocol_health_final": self.state_history[-1].protocol_health_pct if self.state_history else 0,
            "liquidation_events": len(self.liquidation_events),
        }
    
    def get_final_lp_return(self, initial_lp_value: int) -> float:
        """
        Calculate LP return (percentage change in pool value).
        
        Args:
            initial_lp_value: Initial pool value
        
        Returns:
            Return percentage (e.g., 0.05 = 5% gain, -0.10 = 10% loss)
        """
        if not self.state_history:
            return 0.0
        
        final_state = self.state_history[-1]
        
        # Pool value = reserves + collateral - debt - bad_debt
        final_pool_value = (
            final_state.reserve_base * final_state.ema_price // NAD +
            final_state.reserve_quote +
            final_state.total_collateral * final_state.ema_price // NAD -
            final_state.total_debt -
            final_state.total_bad_debt
        )
        
        if initial_lp_value == 0:
            return 0.0
        
        return (final_pool_value - initial_lp_value) / initial_lp_value


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def simulate_scenario(
    config: SimulationConfig,
    price_data: List[Tuple[int, int]],  # List of (timestamp, price)
    initial_pool_tvl: int,
    borrower_positions: List[Dict],  # List of {ltv: float, collateral: int}
) -> Dict:
    """
    Run complete scenario simulation.
    
    Args:
        config: Simulation configuration
        price_data: List of (timestamp, price_nad) tuples
        initial_pool_tvl: Initial pool TVL in quote token
        borrower_positions: List of borrower configs
    
    Returns:
        Complete results dictionary
    """
    if not price_data:
        return {"error": "No price data provided"}
    
    # Initialize pool
    initial_timestamp, initial_price = price_data[0]
    initial_base = initial_pool_tvl  # In quote units
    initial_quote = initial_pool_tvl
    
    pool = GAMMPool(
        config=config,
        initial_reserve_base=initial_base,
        initial_reserve_quote=initial_quote,
        initial_timestamp=initial_timestamp
    )
    
    # Create borrower positions
    for i, borrower in enumerate(borrower_positions):
        pool.create_position(
            collateral_amount=borrower.get("collateral", initial_base // 10),
            target_ltv=borrower.get("ltv", 0.75),
            timestamp=initial_timestamp
        )
    
    # Step through price data
    for timestamp, price in price_data[1:]:
        pool.step(price, timestamp)
    
    # Gather results
    stats = pool.get_statistics()
    initial_lp_value = initial_pool_tvl * 2  # Base + quote
    lp_return = pool.get_final_lp_return(initial_lp_value)
    
    return {
        **stats,
        "lp_return_pct": lp_return * 100,
        "state_history": pool.state_history,
        "liquidation_events": pool.liquidation_events,
        "pool": pool  # Return pool object for further analysis
    }


def compare_configurations(
    configs: List[SimulationConfig],
    price_data: List[Tuple[int, int]],
    initial_pool_tvl: int,
    borrower_positions: List[Dict]
) -> Dict[str, Dict]:
    """
    Run same scenario with multiple configurations and compare.
    
    Args:
        configs: List of configurations to test
        price_data: Price time series
        initial_pool_tvl: Initial pool size
        borrower_positions: Borrower setup
    
    Returns:
        Dictionary mapping config name to results
    """
    results = {}
    
    for config in configs:
        print(f"Running simulation: {config.name}...")
        result = simulate_scenario(
            config=config,
            price_data=price_data,
            initial_pool_tvl=initial_pool_tvl,
            borrower_positions=borrower_positions
        )
        results[config.name] = result
    
    return results


# ============================================================================
# UNIT TESTS
# ============================================================================

def test_pool_initialization():
    """Test pool initializes correctly"""
    from config import FULL_OMNIPAIR_GAMM
    
    pool = GAMMPool(
        config=FULL_OMNIPAIR_GAMM,
        initial_reserve_base=1_000_000 * NAD,
        initial_reserve_quote=1_000_000 * NAD,
        initial_timestamp=0
    )
    
    assert pool.reserve_base == 1_000_000 * NAD
    assert pool.reserve_quote == 1_000_000 * NAD
    assert pool.total_debt == 0
    assert len(pool.positions) == 0
    
    print("✅ Pool initialization test passed")


def test_position_creation():
    """Test creating borrower positions"""
    from config import FULL_OMNIPAIR_GAMM
    
    pool = GAMMPool(
        config=FULL_OMNIPAIR_GAMM,
        initial_reserve_base=1_000_000 * NAD,
        initial_reserve_quote=1_000_000 * NAD,
        initial_timestamp=0
    )
    
    # Create position with 75% LTV
    position = pool.create_position(
        collateral_amount=100 * NAD,
        target_ltv=0.75,
        timestamp=0
    )
    
    assert position.collateral_amount == 100 * NAD
    assert position.debt_amount > 0
    assert position.liquidated == False
    assert pool.total_debt > 0
    
    print(f"✅ Position creation test passed")
    print(f"   Collateral: {nad_to_float(position.collateral_amount):.0f} tokens")
    print(f"   Debt: ${nad_to_float(position.debt_amount):.0f}")


def test_price_movement():
    """Test pool behavior during price movement"""
    from config import FULL_OMNIPAIR_GAMM
    
    pool = GAMMPool(
        config=FULL_OMNIPAIR_GAMM,
        initial_reserve_base=1_000 * NAD,
        initial_reserve_quote=1_000 * NAD,
        initial_timestamp=0
    )
    
    # Create position at $1
    initial_price = 1 * NAD
    pool.update_reserves_from_price(initial_price)
    position = pool.create_position(
        collateral_amount=100 * NAD,
        target_ltv=0.75,
        timestamp=0
    )
    
    # Price drops to $0.50
    new_price = int(0.5 * NAD)
    state = pool.step(new_price, 60)
    
    assert state.spot_price == new_price
    # EMA should lag behind
    if pool.config.ema_enabled:
        assert state.ema_price > new_price
    
    print("✅ Price movement test passed")
    print(f"   Spot: ${nad_to_float(state.spot_price):.2f}")
    print(f"   EMA: ${nad_to_float(state.ema_price):.2f}")


def test_liquidation_scenario():
    """Test liquidation triggers correctly"""
    from config import FULL_OMNIPAIR_GAMM
    
    pool = GAMMPool(
        config=FULL_OMNIPAIR_GAMM,
        initial_reserve_base=1_000 * NAD,
        initial_reserve_quote=1_000 * NAD,
        initial_timestamp=0
    )
    
    # Create aggressive position at $1
    initial_price = 1 * NAD
    pool.update_reserves_from_price(initial_price)
    position = pool.create_position(
        collateral_amount=100 * NAD,
        target_ltv=0.95,  # Very aggressive
        timestamp=0
    )
    
    # Price crashes to $0.60
    crash_price = int(0.60 * NAD)
    
    # Step through gradual crash
    for i in range(1, 11):
        price = initial_price - (initial_price - crash_price) * i // 10
        pool.step(price, i * 60)
    
    # Check if position was liquidated
    assert position.liquidated, "Position should be liquidated after crash"
    assert len(pool.liquidation_events) > 0
    
    print("✅ Liquidation scenario test passed")
    print(f"   Liquidation price: ${nad_to_float(position.liquidation_price):.2f}")
    print(f"   Bad debt: ${nad_to_float(position.bad_debt_accrued):.2f}")


def test_configuration_comparison():
    """Test comparing multiple configurations"""
    from config import TRADITIONAL_LENDING, FULL_OMNIPAIR_GAMM
    
    # Simple price crash scenario
    price_data = [
        (0, 1 * NAD),      # $1
        (60, int(0.9 * NAD)),   # $0.90
        (120, int(0.8 * NAD)),  # $0.80
        (180, int(0.7 * NAD)),  # $0.70
    ]
    
    borrowers = [
        {"ltv": 0.80, "collateral": 100 * NAD}
    ]
    
    results = compare_configurations(
        configs=[TRADITIONAL_LENDING, FULL_OMNIPAIR_GAMM],
        price_data=price_data,
        initial_pool_tvl=1_000 * NAD,
        borrower_positions=borrowers
    )
    
    assert "Traditional Lending" in results
    assert "Full OmniPair GAMM" in results
    
    trad_bad_debt = results["Traditional Lending"]["total_bad_debt"]
    gamm_bad_debt = results["Full OmniPair GAMM"]["total_bad_debt"]
    
    print("✅ Configuration comparison test passed")
    print(f"   Traditional: ${nad_to_float(trad_bad_debt):.0f} bad debt")
    print(f"   Full GAMM: ${nad_to_float(gamm_bad_debt):.0f} bad debt")


def run_all_tests():
    """Run all pool tests"""
    print("\n🧪 Running GAMM Pool Tests...\n")
    test_pool_initialization()
    test_position_creation()
    test_price_movement()
    test_liquidation_scenario()
    test_configuration_comparison()
    print("\n✅ All pool tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
    
    print("="*70)
    print("\n📊 Example: Complete Scenario Simulation\n")
    
    from config import TRADITIONAL_LENDING, ONLY_EMA, FULL_OMNIPAIR_GAMM
    
    # Simulate flash crash
    price_data = [
        (0, 100 * NAD),
        (60, 95 * NAD),
        (120, 85 * NAD),
        (180, 75 * NAD),  # Flash crash
        (240, 80 * NAD),  # Recovery
        (300, 85 * NAD),
    ]
    
    borrowers = [
        {"ltv": 0.70, "collateral": 1000 * NAD},
        {"ltv": 0.80, "collateral": 500 * NAD},
    ]
    
    results = compare_configurations(
        configs=[TRADITIONAL_LENDING, ONLY_EMA, FULL_OMNIPAIR_GAMM],
        price_data=price_data,
        initial_pool_tvl=100_000 * NAD,
        borrower_positions=borrowers
    )
    
    print("\n📈 Flash Crash Simulation Results:\n")
    for config_name, result in results.items():
        print(f"{config_name}:")
        print(f"  Bad Debt: ${nad_to_float(result['total_bad_debt']):,.0f}")
        print(f"  Bad Debt Rate: {result['bad_debt_rate_bps']/100:.1f}%")
        print(f"  Liquidations: {result['total_liquidations']}")
        print(f"  Protocol Health: {result['protocol_health_final']}%")
        print(f"  LP Return: {result['lp_return_pct']:+.2f}%")
        print()

