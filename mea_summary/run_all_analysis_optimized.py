"""
Optimized unified script to run both daily and weekly analysis
- Data is loaded only once and shared between analyses
- Better error handling and progress reporting
- Professional output formatting
"""

import matplotlib.pyplot as plt
import time
from pathlib import Path

from visualize_metrics_optimized import MetricsVisualizer
from visualize_metrics_weekly_optimized import WeeklyMetricsVisualizer


def print_header(title: str, char: str = "=", width: int = 80):
    """Print a formatted header"""
    print(f"\n{char * width}")
    print(title.center(width))
    print(f"{char * width}")


def print_section(title: str, width: int = 80):
    """Print a formatted section header"""
    print(f"\n{'-' * width}")
    print(f"  {title}")
    print(f"{'-' * width}")


def main():
    """Main execution function with optimized workflow"""

    # Overall header
    print_header("MEA Spontaneous Activity Metrics - Complete Analysis (Optimized)")
    print("\nThis script will perform both daily and weekly analysis with shared data loading.")

    overall_start = time.time()

    try:
        # ==================== DAILY ANALYSIS ====================
        print_header("PART 1: DAILY ANALYSIS", char="=")

        daily_start = time.time()
        daily_viz = MetricsVisualizer(data_dir='.')

        # Load data for daily analysis
        print_section("[1/4] Loading data for daily analysis")
        daily_viz.load_data()
        data_load_time = time.time() - daily_start

        # Generate daily visualizations
        print_section("[2/4] Generating daily visualizations")
        daily_viz.plot_all_categories(output_dir='visualizations')

        # Create daily heatmap
        print_section("[3/4] Creating daily heatmap")
        daily_viz.create_summary_heatmap(save_path='visualizations/summary_heatmap.png')
        plt.close('all')

        # Generate daily statistics
        print_section("[4/4] Generating daily summary statistics")
        daily_viz.generate_summary_stats(save_path='visualizations/summary_statistics.csv')

        daily_total_time = time.time() - daily_start

        # ==================== WEEKLY ANALYSIS ====================
        print_header("PART 2: WEEKLY ANALYSIS", char="=")

        weekly_start = time.time()
        weekly_viz = WeeklyMetricsVisualizer(data_dir='.', week_size=7)

        # Reuse loaded data from daily analysis (optimization!)
        print_section("[1/5] Reusing data from daily analysis (optimized)")
        weekly_viz.df = daily_viz.df.copy()
        print(f"✓ Data reused successfully ({len(weekly_viz.df):,} rows)")

        # Create weekly groups
        print_section("[2/5] Creating weekly groups")
        weekly_viz.create_weekly_groups()

        # Generate weekly visualizations
        print_section("[3/5] Generating weekly visualizations")
        weekly_viz.plot_all_categories_weekly(output_dir='weekly_visualizations')

        # Create weekly heatmap
        print_section("[4/5] Creating weekly heatmap")
        weekly_viz.create_weekly_heatmap(save_path='weekly_visualizations/weekly_heatmap.png')
        plt.close('all')

        # Generate weekly statistics
        print_section("[5/5] Generating weekly summary statistics")
        weekly_viz.generate_weekly_summary_stats(save_path='weekly_visualizations/weekly_summary_statistics.csv')

        weekly_total_time = time.time() - weekly_start

        # ==================== SUMMARY ====================
        print_header("✓ ANALYSIS COMPLETE!", char="=")

        # Performance summary
        total_time = time.time() - overall_start
        print("\n⏱️  Performance Summary:")
        print(f"   • Data loading:      {data_load_time:.2f}s")
        print(f"   • Daily analysis:    {daily_total_time:.2f}s")
        print(f"   • Weekly analysis:   {weekly_total_time:.2f}s")
        print(f"   • Total time:        {total_time:.2f}s")

        # Output summary
        print("\n📁 Output Files:")
        print("   Daily Analysis:")
        print("     • visualizations/")
        for category in daily_viz.get_metric_categories().keys():
            filename = f"{category.replace(' ', '_').lower()}.png"
            print(f"       - {filename}")
        print("       - summary_heatmap.png")
        print("       - summary_statistics.csv")

        print("\n   Weekly Analysis:")
        print("     • weekly_visualizations/")
        for category in weekly_viz.get_metric_categories().keys():
            filename = f"{category.replace(' ', '_').lower()}_weekly.png"
            print(f"       - {filename}")
        print("       - weekly_heatmap.png")
        print("       - weekly_summary_statistics.csv")

        # Data summary
        print(f"\n📊 Data Summary:")
        print(f"   • Total samples:     {len(daily_viz.df):,}")
        print(f"   • Unique metrics:    {daily_viz.df['Metric'].nunique()}")
        print(f"   • Day range:         {daily_viz.df['DIFF_DAY'].min():.0f} - {daily_viz.df['DIFF_DAY'].max():.0f}")
        print(f"   • Week range:        {weekly_viz.weekly_df['Week'].min():.0f} - {weekly_viz.weekly_df['Week'].max():.0f}")
        print(f"   • Week size:         {weekly_viz.week_size} days")

        print("\n" + "=" * 80)
        print("Both daily and weekly analysis have been successfully completed!".center(80))
        print("=" * 80 + "\n")

        return 0  # Success

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("   Make sure CSV files matching '*spontaneous_activity.csv' exist in the current directory.")
        return 1

    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("   Check that your CSV files have the required columns: DIFF_DAY, Metric, Mean")
        return 1

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    exit(exit_code)
