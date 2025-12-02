"""
OmniPair GAMM Simulation - Configuration
Extracted constants from Solana smart contracts
"""

# ============================================================================
# CORE CONSTANTS (from constants.rs)
# ============================================================================

# Precision & Scaling
NAD = 1_000_000_000  # 1e9 scaling factor
NAD_DECIMALS = 9
BPS_DENOMINATOR = 10_000  # 100% = 10,000 basis points

# Liquidation Parameters
CLOSE_FACTOR_BPS = 5_000  # 50% - partial liquidation amount
MAX_COLLATERAL_FACTOR_BPS = 8_500  # 85% - maximum LTV cap
LTV_BUFFER_BPS = 500  # 5% - safety buffer
LIQUIDATION_INCENTIVE_BPS = 300  # 3% - liquidator bonus

# EMA Parameters
MIN_HALF_LIFE = 60  # 1 minute
MAX_HALF_LIFE = 43_200  # 12 hours
DEFAULT_HALF_LIFE = 60  # Default to 1 minute
LN_2 = 0.693147180559945309417  # ln(2) for calculations

# Interest Rate Model
INITIAL_RATE_BPS = 200  # 2%
MIN_RATE_BPS = 100  # 1%
TARGET_UTIL_START_BPS = 5_000  # 50%
TARGET_UTIL_END_BPS = 8_500  # 85%
SECONDS_PER_YEAR = 31_536_000

# Pool Parameters
MIN_LIQUIDITY = 1_000  # Minimum pool liquidity
FLASHLOAN_FEE_BPS = 5  # 0.05%


# ============================================================================
# SIMULATION CONFIGURATION PRESETS
# ============================================================================

class SimulationConfig:
    """
    Configuration for modular GAMM simulation.
    Each component can be toggled on/off for comparative analysis.
    """
    
    def __init__(
        self,
        name: str = "Custom",
        # Component toggles
        ema_enabled: bool = True,
        dynamic_cf_enabled: bool = True,
        pessimistic_cap_enabled: bool = True,
        ltv_buffer_enabled: bool = True,
        partial_liquidation_enabled: bool = True,
        # Parameters (if components enabled)
        half_life: int = DEFAULT_HALF_LIFE,
        fixed_cf_bps: int = 7500,  # 75% if dynamic CF disabled
        max_cf_bps: int = MAX_COLLATERAL_FACTOR_BPS,
        ltv_buffer_bps: int = LTV_BUFFER_BPS,
        close_factor_bps: int = CLOSE_FACTOR_BPS,
        liquidation_incentive_bps: int = LIQUIDATION_INCENTIVE_BPS,
    ):
        self.name = name
        
        # Component flags
        self.ema_enabled = ema_enabled
        self.dynamic_cf_enabled = dynamic_cf_enabled
        self.pessimistic_cap_enabled = pessimistic_cap_enabled
        self.ltv_buffer_enabled = ltv_buffer_enabled
        self.partial_liquidation_enabled = partial_liquidation_enabled
        
        # Parameters
        self.half_life = half_life
        self.fixed_cf_bps = fixed_cf_bps
        self.max_cf_bps = max_cf_bps
        self.ltv_buffer_bps = ltv_buffer_bps if ltv_buffer_enabled else 0
        self.close_factor_bps = close_factor_bps if partial_liquidation_enabled else 10_000
        self.liquidation_incentive_bps = liquidation_incentive_bps
    
    def __repr__(self):
        components = []
        if self.ema_enabled:
            components.append(f"EMA({self.half_life}s)")
        if self.dynamic_cf_enabled:
            components.append("DynamicCF")
        if self.pessimistic_cap_enabled:
            components.append("PessimisticCap")
        if self.ltv_buffer_enabled:
            components.append(f"LTVBuffer({self.ltv_buffer_bps}bps)")
        if self.partial_liquidation_enabled:
            components.append(f"PartialLiq({self.close_factor_bps}bps)")
        
        return f"{self.name}: [{', '.join(components) if components else 'No protections'}]"


# ============================================================================
# PRESET CONFIGURATIONS
# ============================================================================

# Configuration 1: Traditional Oracle-Based Lending (Baseline)
TRADITIONAL_LENDING = SimulationConfig(
    name="Traditional Lending",
    ema_enabled=False,  # Uses instant spot price (like Chainlink)
    dynamic_cf_enabled=False,  # Fixed CF
    pessimistic_cap_enabled=False,
    ltv_buffer_enabled=False,
    partial_liquidation_enabled=True,  # 50% close factor
    fixed_cf_bps=7500,  # 75% typical for stablecoins/majors
)

# Configuration 2: Only EMA Pricing
ONLY_EMA = SimulationConfig(
    name="Only EMA",
    ema_enabled=True,
    half_life=60,
    dynamic_cf_enabled=False,
    pessimistic_cap_enabled=False,
    ltv_buffer_enabled=False,
    partial_liquidation_enabled=True,
    fixed_cf_bps=7500,
)

# Configuration 3: Only Dynamic CF
ONLY_DYNAMIC_CF = SimulationConfig(
    name="Only Dynamic CF",
    ema_enabled=False,
    dynamic_cf_enabled=True,
    pessimistic_cap_enabled=False,
    ltv_buffer_enabled=False,
    partial_liquidation_enabled=True,
)

# Configuration 4: EMA + Dynamic CF (No Pessimistic Cap)
EMA_PLUS_DYNAMIC_CF = SimulationConfig(
    name="EMA + Dynamic CF",
    ema_enabled=True,
    half_life=60,
    dynamic_cf_enabled=True,
    pessimistic_cap_enabled=False,  # Missing protection
    ltv_buffer_enabled=False,
    partial_liquidation_enabled=True,
)

# Configuration 5: Full OmniPair GAMM (All Protections)
FULL_OMNIPAIR_GAMM = SimulationConfig(
    name="Full OmniPair GAMM",
    ema_enabled=True,
    half_life=60,
    dynamic_cf_enabled=True,
    pessimistic_cap_enabled=True,
    ltv_buffer_enabled=True,
    partial_liquidation_enabled=True,
    ltv_buffer_bps=500,
    max_cf_bps=8500,
)

# Configuration 6: Conservative GAMM (Longer half-life)
CONSERVATIVE_GAMM = SimulationConfig(
    name="Conservative GAMM",
    ema_enabled=True,
    half_life=300,  # 5 minutes
    dynamic_cf_enabled=True,
    pessimistic_cap_enabled=True,
    ltv_buffer_enabled=True,
    partial_liquidation_enabled=True,
    ltv_buffer_bps=1000,  # 10% buffer
    max_cf_bps=7500,  # 75% max CF
)

# Configuration 7: Aggressive GAMM (Shorter half-life, higher leverage)
AGGRESSIVE_GAMM = SimulationConfig(
    name="Aggressive GAMM",
    ema_enabled=True,
    half_life=30,  # 30 seconds
    dynamic_cf_enabled=True,
    pessimistic_cap_enabled=True,
    ltv_buffer_enabled=True,
    partial_liquidation_enabled=True,
    ltv_buffer_bps=300,  # 3% buffer
    max_cf_bps=8500,  # 85% max CF
)


# All presets for easy iteration
ALL_PRESETS = [
    TRADITIONAL_LENDING,
    ONLY_EMA,
    ONLY_DYNAMIC_CF,
    EMA_PLUS_DYNAMIC_CF,
    FULL_OMNIPAIR_GAMM,
    CONSERVATIVE_GAMM,
    AGGRESSIVE_GAMM,
]

PRESET_NAMES = {preset.name: preset for preset in ALL_PRESETS}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def bps_to_decimal(bps: int) -> float:
    """Convert basis points to decimal (e.g., 7500 bps = 0.75)"""
    return bps / BPS_DENOMINATOR


def decimal_to_bps(decimal: float) -> int:
    """Convert decimal to basis points (e.g., 0.75 = 7500 bps)"""
    return int(decimal * BPS_DENOMINATOR)


def nad_to_float(nad_value: int) -> float:
    """Convert NAD-scaled value to float (e.g., 1_000_000_000 = 1.0)"""
    return nad_value / NAD


def float_to_nad(float_value: float) -> int:
    """Convert float to NAD-scaled value (e.g., 1.0 = 1_000_000_000)"""
    return int(float_value * NAD)


if __name__ == "__main__":
    # Test configurations
    print("📋 Available Simulation Configurations:\n")
    for i, preset in enumerate(ALL_PRESETS, 1):
        print(f"{i}. {preset}")
    
    print("\n" + "="*70)
    print("\n🔧 Configuration Details:\n")
    
    config = FULL_OMNIPAIR_GAMM
    print(f"Config: {config.name}")
    print(f"  EMA Enabled: {config.ema_enabled} (half-life: {config.half_life}s)")
    print(f"  Dynamic CF: {config.dynamic_cf_enabled}")
    print(f"  Pessimistic Cap: {config.pessimistic_cap_enabled}")
    print(f"  LTV Buffer: {config.ltv_buffer_enabled} ({config.ltv_buffer_bps} bps = {bps_to_decimal(config.ltv_buffer_bps)*100}%)")
    print(f"  Partial Liquidation: {config.partial_liquidation_enabled} ({config.close_factor_bps} bps = {bps_to_decimal(config.close_factor_bps)*100}%)")

