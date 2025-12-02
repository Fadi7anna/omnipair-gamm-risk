"""
Run Complete Scenario Analysis
Tests all configurations against all three crisis scenarios
"""

from config import (
    TRADITIONAL_LENDING, ONLY_EMA, ONLY_DYNAMIC_CF, 
    EMA_PLUS_DYNAMIC_CF, FULL_OMNIPAIR_GAMM, 
    CONSERVATIVE_GAMM, AGGRESSIVE_GAMM,
    nad_to_float, float_to_nad
)
from gamm_pool import compare_configurations, simulate_scenario
from data_collector import load_price_data_csv
from pathlib import Path
import json


def run_complete_analysis():
    """
    Run full analysis across all scenarios and configurations.
    """
    
    print("\n" + "="*80)
    print("🔬 OMNIPAIR GAMM RISK ANALYSIS - COMPLETE SCENARIO TESTING")
    print("="*80 + "\n")
    
    # Define scenarios
    scenarios = [
        {
            "name": "Mango Markets Exploit",
            "file": "data/mango_exploit/mngo_usdc_prices.csv",
            "description": "Oracle manipulation attack, rapid price pump & dump",
            "initial_tvl": 1_000_000 * float_to_nad(1),  # $1M pool
            "borrowers": [
                {"ltv": 0.75, "collateral": 100_000 * float_to_nad(1)},  # $100K conservative
                {"ltv": 0.82, "collateral": 50_000 * float_to_nad(1)},   # $50K aggressive
            ]
        },
        {
            "name": "LUNA Collapse",
            "file": "data/luna_collapse/luna_usdc_prices.csv",
            "description": "Death spiral, 99.99% price drop over 6 days",
            "initial_tvl": 1_000_000 * float_to_nad(1),
            "borrowers": [
                {"ltv": 0.70, "collateral": 150_000 * float_to_nad(1)},  # $150K conservative
                {"ltv": 0.80, "collateral": 100_000 * float_to_nad(1)},  # $100K moderate
            ]
        },
        {
            "name": "FTT Collapse",
            "file": "data/ftt_collapse/ftt_usdc_prices.csv",
            "description": "Gradual then rapid 90% crash over 10 days",
            "initial_tvl": 1_000_000 * float_to_nad(1),
            "borrowers": [
                {"ltv": 0.75, "collateral": 200_000 * float_to_nad(1)},  # $200K position
                {"ltv": 0.78, "collateral": 80_000 * float_to_nad(1)},   # $80K position
            ]
        }
    ]
    
    # Configurations to test
    configs = [
        TRADITIONAL_LENDING,
        ONLY_EMA,
        ONLY_DYNAMIC_CF,
        EMA_PLUS_DYNAMIC_CF,
        FULL_OMNIPAIR_GAMM,
    ]
    
    all_results = {}
    
    # Run each scenario
    for scenario in scenarios:
        print(f"\n{'='*80}")
        print(f"📊 SCENARIO: {scenario['name']}")
        print(f"   {scenario['description']}")
        print(f"{'='*80}\n")
        
        # Check if data file exists
        filepath = Path(scenario['file'])
        if not filepath.exists():
            print(f"❌ Data file not found: {filepath}")
            print(f"   Run: python create_synthetic_data.py")
            continue
        
        # Load price data
        try:
            price_data = load_price_data_csv(str(filepath))
            print(f"✅ Loaded {len(price_data)} price points")
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            continue
        
        # Run simulations
        print(f"\n🔄 Running simulations with {len(configs)} configurations...\n")
        
        results = compare_configurations(
            configs=configs,
            price_data=price_data,
            initial_pool_tvl=scenario['initial_tvl'],
            borrower_positions=scenario['borrowers']
        )
        
        all_results[scenario['name']] = results
        
        # Print results
        print(f"\n{'─'*80}")
        print(f"📈 RESULTS: {scenario['name']}")
        print(f"{'─'*80}\n")
        
        # Sort by bad debt (worst to best)
        sorted_configs = sorted(
            results.items(),
            key=lambda x: x[1]['total_bad_debt'],
            reverse=True
        )
        
        for config_name, result in sorted_configs:
            bad_debt = nad_to_float(result['total_bad_debt'])
            bad_debt_rate = result['bad_debt_rate_bps'] / 100
            health = result['protocol_health_final']
            lp_return = result['lp_return_pct']
            liquidations = result['total_liquidations']
            
            # Status indicator
            if bad_debt_rate < 1.0:
                status = "✅"
            elif bad_debt_rate < 5.0:
                status = "⚠️ "
            else:
                status = "❌"
            
            print(f"{status} {config_name:25s}")
            print(f"     Bad Debt: ${bad_debt:10,.0f} ({bad_debt_rate:5.2f}%)")
            print(f"     Protocol Health: {health:4.0f}%  |  LP Return: {lp_return:+6.2f}%  |  Liquidations: {liquidations}")
            print()
    
    # Generate comparison summary
    print("\n" + "="*80)
    print("🎯 CROSS-SCENARIO SUMMARY")
    print("="*80 + "\n")
    
    # For each config, show performance across all scenarios
    for config in configs:
        config_name = config.name
        print(f"\n📊 {config_name}")
        print("─" * 80)
        
        total_bad_debt = 0
        scenario_count = 0
        
        for scenario_name, results in all_results.items():
            if config_name in results:
                result = results[config_name]
                bad_debt = nad_to_float(result['total_bad_debt'])
                rate = result['bad_debt_rate_bps'] / 100
                total_bad_debt += bad_debt
                scenario_count += 1
                
                print(f"  {scenario_name:25s}: ${bad_debt:10,.0f} ({rate:5.2f}%)")
        
        if scenario_count > 0:
            avg_bad_debt = total_bad_debt / scenario_count
            print(f"  {'─'*50}")
            print(f"  {'Average Bad Debt':25s}: ${avg_bad_debt:10,.0f}")
    
    # Component attribution analysis
    print("\n" + "="*80)
    print("💡 COMPONENT CONTRIBUTION ANALYSIS")
    print("="*80 + "\n")
    
    # Pick one scenario for detailed analysis (Mango)
    if "Mango Markets Exploit" in all_results:
        mango_results = all_results["Mango Markets Exploit"]
        
        trad_bd = nad_to_float(mango_results.get("Traditional Lending", {}).get("total_bad_debt", 0))
        ema_bd = nad_to_float(mango_results.get("Only EMA", {}).get("total_bad_debt", 0))
        gamm_bd = nad_to_float(mango_results.get("Full OmniPair GAMM", {}).get("total_bad_debt", 0))
        
        if trad_bd > 0:
            ema_improvement = ((trad_bd - ema_bd) / trad_bd) * 100
            full_improvement = ((trad_bd - gamm_bd) / trad_bd) * 100
            
            print(f"Using Mango Markets Exploit as reference:\n")
            print(f"  Traditional Lending (Baseline):  ${trad_bd:10,.0f}")
            print(f"  Only EMA:                         ${ema_bd:10,.0f}  ({ema_improvement:+.1f}% vs baseline)")
            print(f"  Full OmniPair GAMM:               ${gamm_bd:10,.0f}  ({full_improvement:+.1f}% vs baseline)")
            print(f"\n  🎯 Key Insight: EMA alone prevents {ema_improvement:.0f}% of bad debt")
            print(f"  🎯 Key Insight: Full GAMM prevents {full_improvement:.0f}% of bad debt")
            
            if ema_bd > 0:
                additional_improvement = ((ema_bd - gamm_bd) / ema_bd) * 100
                print(f"  🎯 Key Insight: Additional protections (Dynamic CF + Pessimistic Cap + LTV Buffer)")
                print(f"                  provide {additional_improvement:.0f}% further improvement beyond EMA")
    
    # Save results to file
    output_file = "analysis_results.json"
    results_for_save = {}
    for scenario_name, results in all_results.items():
        results_for_save[scenario_name] = {
            config_name: {
                "bad_debt_usd": nad_to_float(result['total_bad_debt']),
                "bad_debt_rate_pct": result['bad_debt_rate_bps'] / 100,
                "protocol_health_pct": result['protocol_health_final'],
                "lp_return_pct": result['lp_return_pct'],
                "total_liquidations": result['total_liquidations'],
            }
            for config_name, result in results.items()
        }
    
    with open(output_file, 'w') as f:
        json.dump(results_for_save, f, indent=2)
    
    print(f"\n\n💾 Results saved to: {output_file}")
    
    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE!")
    print("="*80)
    print("\nNext steps:")
    print("  1. Review results above")
    print("  2. Run: python visualize_results.py (to generate charts)")
    print("  3. Run: streamlit run dashboard_app.py (for interactive exploration)")
    print("\n")


if __name__ == "__main__":
    run_complete_analysis()

