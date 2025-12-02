"""
EMA (Exponential Moving Average) Pricing Engine
Implements time-weighted price smoothing to prevent manipulation
"""

import math
from typing import Optional
from config import NAD, LN_2, MIN_HALF_LIFE, MAX_HALF_LIFE


class EMAEngine:
    """
    Exponential Moving Average calculator for price smoothing.
    
    Prevents flash loan and short-term price manipulation by
    time-weighting prices with exponential decay.
    """
    
    def __init__(self, half_life: int = 60):
        """
        Initialize EMA engine.
        
        Args:
            half_life: Half-life in seconds (time for 50% convergence)
        """
        assert MIN_HALF_LIFE <= half_life <= MAX_HALF_LIFE, \
            f"Half-life must be between {MIN_HALF_LIFE} and {MAX_HALF_LIFE} seconds"
        
        self.half_life = half_life
        self.last_ema = 0  # NAD-scaled
        self.last_update = 0  # Unix timestamp
    
    def initialize(self, initial_price: int, timestamp: int):
        """
        Initialize EMA with first price observation.
        
        Args:
            initial_price: Initial spot price (NAD-scaled)
            timestamp: Unix timestamp
        """
        self.last_ema = initial_price
        self.last_update = timestamp
    
    def update(self, current_spot_price: int, current_time: int) -> int:
        """
        Update EMA with new spot price observation.
        
        Formula:
            α (alpha) = exp(-dt * ln(2) / half_life)
            EMA_new = spot * (1 - α) + EMA_old * α
        
        Args:
            current_spot_price: Current spot price from AMM (NAD-scaled)
            current_time: Current unix timestamp
        
        Returns:
            Updated EMA price (NAD-scaled)
        """
        # Initialize if first update
        if self.last_ema == 0:
            self.initialize(current_spot_price, current_time)
            return self.last_ema
        
        # Calculate time elapsed
        dt = current_time - self.last_update
        
        # If no time passed, return last EMA
        if dt <= 0:
            return self.last_ema
        
        # Calculate decay factor: α = exp(-dt * ln(2) / half_life)
        exp_time = self.half_life / LN_2
        x = dt / exp_time
        alpha = math.exp(-x)
        
        # EMA update: weighted average of spot and last EMA
        new_ema = current_spot_price * (1 - alpha) + self.last_ema * alpha
        
        # Update state
        self.last_ema = int(new_ema)
        self.last_update = current_time
        
        return self.last_ema
    
    def get_current_ema(self, current_spot_price: int, current_time: int) -> int:
        """
        Get current EMA without updating internal state.
        Useful for read-only queries.
        
        Args:
            current_spot_price: Current spot price (NAD-scaled)
            current_time: Current timestamp
        
        Returns:
            Calculated EMA (NAD-scaled)
        """
        if self.last_ema == 0:
            return current_spot_price
        
        dt = current_time - self.last_update
        
        if dt <= 0:
            return self.last_ema
        
        exp_time = self.half_life / LN_2
        x = dt / exp_time
        alpha = math.exp(-x)
        
        ema = current_spot_price * (1 - alpha) + self.last_ema * alpha
        
        return int(ema)
    
    def reset(self):
        """Reset EMA state"""
        self.last_ema = 0
        self.last_update = 0


class PriceOracle:
    """
    Price oracle that can use either EMA or spot pricing.
    """
    
    def __init__(self, use_ema: bool = True, half_life: int = 60):
        """
        Initialize price oracle.
        
        Args:
            use_ema: If True, use EMA smoothing. If False, use spot price (traditional)
            half_life: Half-life for EMA (if enabled)
        """
        self.use_ema = use_ema
        self.ema_engine = EMAEngine(half_life) if use_ema else None
    
    def get_price(self, spot_price: int, timestamp: int) -> int:
        """
        Get price for lending calculations.
        
        Args:
            spot_price: Current spot price from AMM (NAD-scaled)
            timestamp: Current unix timestamp
        
        Returns:
            Price for lending (EMA if enabled, spot otherwise)
        """
        if self.use_ema and self.ema_engine:
            return self.ema_engine.update(spot_price, timestamp)
        else:
            # Traditional: use spot price directly (like Chainlink oracle)
            return spot_price
    
    def get_spot_and_ema(self, spot_price: int, timestamp: int) -> tuple[int, int]:
        """
        Get both spot and EMA prices.
        
        Returns:
            (spot_price, ema_price) tuple
        """
        if self.use_ema and self.ema_engine:
            ema = self.ema_engine.update(spot_price, timestamp)
            return (spot_price, ema)
        else:
            return (spot_price, spot_price)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_ema_lag(spot_price: float, ema_price: float) -> float:
    """
    Calculate percentage lag between spot and EMA.
    
    Returns:
        Percentage difference (e.g., 0.05 = 5% lag)
    """
    if ema_price == 0:
        return 0.0
    return abs(spot_price - ema_price) / ema_price


def estimate_convergence_time(current_lag_pct: float, half_life: int, target_lag_pct: float = 0.01) -> int:
    """
    Estimate time for EMA to converge to spot within target lag.
    
    Args:
        current_lag_pct: Current lag as percentage (e.g., 0.10 = 10%)
        half_life: EMA half-life in seconds
        target_lag_pct: Target lag percentage (default 1%)
    
    Returns:
        Estimated seconds to convergence
    """
    if current_lag_pct <= target_lag_pct:
        return 0
    
    # Number of half-lives needed: n = log(current/target) / log(2)
    n_half_lives = math.log(current_lag_pct / target_lag_pct) / math.log(2)
    
    return int(n_half_lives * half_life)


def simulate_ema_attack(
    initial_price: float,
    manipulated_price: float,
    attack_duration: int,
    half_life: int
) -> dict:
    """
    Simulate an EMA manipulation attack.
    
    Args:
        initial_price: Price before attack (e.g., 1.0)
        manipulated_price: Target manipulated price (e.g., 2.0)
        attack_duration: How long attacker maintains price (seconds)
        half_life: EMA half-life
    
    Returns:
        Dictionary with attack results
    """
    from config import float_to_nad, nad_to_float
    
    ema_engine = EMAEngine(half_life)
    
    # Initialize at equilibrium
    initial_nad = float_to_nad(initial_price)
    ema_engine.initialize(initial_nad, 0)
    
    # Attacker manipulates price
    manipulated_nad = float_to_nad(manipulated_price)
    final_ema_nad = ema_engine.update(manipulated_nad, attack_duration)
    
    final_ema = nad_to_float(final_ema_nad)
    
    # Calculate attack effectiveness
    price_change_pct = (manipulated_price / initial_price - 1) * 100
    ema_change_pct = (final_ema / initial_price - 1) * 100
    attack_effectiveness = ema_change_pct / price_change_pct if price_change_pct != 0 else 0
    
    return {
        'initial_price': initial_price,
        'manipulated_price': manipulated_price,
        'attack_duration': attack_duration,
        'half_life': half_life,
        'final_ema': final_ema,
        'ema_moved_pct': ema_change_pct,
        'price_moved_pct': price_change_pct,
        'attack_effectiveness': attack_effectiveness,
        'interpretation': (
            f"Attacker moved price {price_change_pct:.1f}% but EMA only moved "
            f"{ema_change_pct:.1f}% ({attack_effectiveness*100:.1f}% effective)"
        )
    }


# ============================================================================
# UNIT TESTS
# ============================================================================

def test_ema_initialization():
    """Test EMA initializes correctly"""
    ema = EMAEngine(half_life=60)
    price = 1_000_000_000  # 1.0 in NAD
    
    result = ema.update(price, 0)
    assert result == price, "EMA should equal first price"
    assert ema.last_ema == price
    print("✅ EMA initialization test passed")


def test_ema_no_movement():
    """Test EMA with stable price"""
    ema = EMAEngine(half_life=60)
    price = 1_000_000_000
    
    ema.update(price, 0)
    result = ema.update(price, 60)  # 1 minute later
    
    assert result == price, "EMA should stay at price if no change"
    print("✅ EMA stable price test passed")


def test_ema_convergence():
    """Test EMA converges toward new price"""
    ema = EMAEngine(half_life=60)
    
    # Start at 1.0
    ema.update(1_000_000_000, 0)
    
    # Price jumps to 2.0
    new_price = 2_000_000_000
    
    # After 1 half-life, EMA should be ~halfway
    result_60s = ema.get_current_ema(new_price, 60)
    from config import nad_to_float
    
    ema_value = nad_to_float(result_60s)
    assert 1.4 < ema_value < 1.6, f"After 1 half-life, EMA should be ~1.5, got {ema_value}"
    print(f"✅ EMA convergence test passed (1 half-life: {ema_value:.3f})")


def test_ema_manipulation_resistance():
    """Test EMA resistance to short attacks"""
    result = simulate_ema_attack(
        initial_price=1.0,
        manipulated_price=2.0,  # 100% pump
        attack_duration=10,  # Only 10 seconds
        half_life=60
    )
    
    # EMA should move much less than 100%
    assert result['ema_moved_pct'] < 20, "EMA should resist short manipulation"
    print(f"✅ Manipulation resistance test passed:")
    print(f"   {result['interpretation']}")


def test_price_oracle_modes():
    """Test PriceOracle with EMA on/off"""
    spot_price = 2_000_000_000
    
    # Traditional oracle (no EMA)
    oracle_spot = PriceOracle(use_ema=False)
    price_spot = oracle_spot.get_price(spot_price, 0)
    assert price_spot == spot_price, "Spot oracle should return spot"
    
    # EMA oracle
    oracle_ema = PriceOracle(use_ema=True, half_life=60)
    oracle_ema.get_price(1_000_000_000, 0)  # Initialize at 1.0
    price_ema = oracle_ema.get_price(spot_price, 60)  # After 1 minute
    assert price_ema != spot_price, "EMA oracle should smooth"
    assert 1_000_000_000 < price_ema < spot_price, "EMA should be between old and new"
    
    print("✅ Price oracle modes test passed")


def run_all_tests():
    """Run all EMA engine tests"""
    print("\n🧪 Running EMA Engine Tests...\n")
    test_ema_initialization()
    test_ema_no_movement()
    test_ema_convergence()
    test_ema_manipulation_resistance()
    test_price_oracle_modes()
    print("\n✅ All EMA tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
    
    # Example: Simulate various attack scenarios
    print("="*70)
    print("\n📊 EMA Attack Simulation Examples:\n")
    
    scenarios = [
        {"duration": 10, "half_life": 60, "pump": 2.0},
        {"duration": 60, "half_life": 60, "pump": 2.0},
        {"duration": 180, "half_life": 60, "pump": 2.0},
        {"duration": 60, "half_life": 300, "pump": 2.0},
    ]
    
    for scenario in scenarios:
        result = simulate_ema_attack(
            initial_price=1.0,
            manipulated_price=scenario["pump"],
            attack_duration=scenario["duration"],
            half_life=scenario["half_life"]
        )
        print(f"Duration: {result['attack_duration']}s, Half-life: {result['half_life']}s")
        print(f"  → {result['interpretation']}\n")

