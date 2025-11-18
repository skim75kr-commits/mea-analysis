"""
Optimized unified script to run both daily and weekly light response analysis
- Data is loaded only once and shared between analyses
- Better error handling and progress reporting
- Professional output formatting
"""

import matplotlib.pyplot as plt
import time
from pathlib import Path

from visualize_light_response_daily import LightResponseVisualizer
from visualize_light_response_weekly import WeeklyLightResponseVisualizer


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
    print_header("MEA Light Response Metrics - Complete Analysis (Optimized)")
    print("\nThis script will perform both daily and weekly light response analysis with shared data loading.")

    overall_start = time.time()

    try:
        # ==================== DAILY ANALYSIS ====================
        print_header("PART 1: DAILY ANALYSIS", char="=")

        daily_start = time.time()
        daily_viz = LightResponseVisualizer(data_dir='Data_LightResponse')

        # Load data for daily analysis
        print_section("[1/4] Loading data for daily analysis")
        daily_viz.load_data()
        data_load_time = time.time() - daily_start

        # Generate daily visualizations
        print_section("[2/4] Generating daily visualizations")
        daily_viz.plot_all_categories(output_dir='light_response_visualizations')

        # Create daily heatmaps
        print_section("[3/4] Creating daily heatmaps")
        daily_viz.create_summary_heatmap(
            save_path='light_response_visualizations/summary_heatmap_response.png',
            value_type='response'
        )
        daily_viz.create_summary_heatmap(
            save_path='light_response_visualizations/summary_heatmap_baseline.png',
            value_type='baseline'
        )
        plt.close('all')

        # Generate daily statistics
        print_section("[4/4] Generating daily summary statistics")
        daily_viz.generate_summary_stats(
            save_path='light_response_visualizations/light_response_summary_statistics.csv'
        )

        daily_total_time = time.time() - daily_start

        # ==================== WEEKLY ANALYSIS ====================
        print_header("PART 2: WEEKLY ANALYSIS", char="=")

        weekly_start = time.time()
        weekly_viz = WeeklyLightResponseVisualizer(data_dir='Data_LightResponse', week_size=7)

        # Reuse loaded data from daily analysis (optimization!)
        print_section("[1/5] Reusing data from daily analysis (optimized)")
        weekly_viz.df = daily_viz.df.copy()
        print(f"[OK] Data reused successfully ({len(weekly_viz.df):,} rows)")

        # Create weekly groups
        print_section("[2/5] Creating weekly groups")
        weekly_viz.create_weekly_groups()

        # Generate weekly visualizations
        print_section("[3/5] Generating weekly visualizations")
        weekly_viz.plot_all_categories_weekly(
            output_dir='light_response_weekly_visualizations'
        )

        # Create weekly heatmaps
        print_section("[4/5] Creating weekly heatmaps")
        weekly_viz.create_weekly_heatmap(
            save_path='light_response_weekly_visualizations/weekly_heatmap_response.png',
            value_type='response'
        )
        weekly_viz.create_weekly_heatmap(
            save_path='light_response_weekly_visualizations/weekly_heatmap_baseline.png',
            value_type='baseline'
        )
        plt.close('all')

        # Generate weekly statistics
        print_section("[5/5] Generating weekly summary statistics")
        weekly_viz.generate_weekly_summary_stats(
            save_path='light_response_weekly_visualizations/light_response_weekly_summary_statistics.csv'
        )

        weekly_total_time = time.time() - weekly_start

        # ==================== SUMMARY ====================
        print_header("[OK] ANALYSIS COMPLETE!", char="=")

        # Performance summary
        total_time = time.time() - overall_start
        print("\n[PERF] Performance Summary:")
        print(f"       - Data loading:      {data_load_time:.2f}s")
        print(f"       - Daily analysis:    {daily_total_time:.2f}s")
        print(f"       - Weekly analysis:   {weekly_total_time:.2f}s")
        print(f"       - Total time:        {total_time:.2f}s")

        # Output summary
        print("\n[FILES] Output Files:")
        print("   Daily Analysis:")
        print("     - light_response_visualizations/")

        categories = daily_viz.get_metric_categories()
        light_codes = sorted(daily_viz.df['Light_Code'].unique())

        for light_code in light_codes:
            print(f"\n       [{daily_viz.get_light_code_label(light_code)}]")
            for category in categories.keys():
                category_slug = category.replace(' ', '_').lower()
                print(f"         - {category_slug}_{light_code}_baseline_stim.png")
                print(f"         - {category_slug}_{light_code}_response.png")

        print("\n       [Heatmaps]")
        print("         - summary_heatmap_response.png")
        print("         - summary_heatmap_baseline.png")
        print("\n       [Statistics]")
        print("         - light_response_summary_statistics.csv")

        print("\n   Weekly Analysis:")
        print("     - light_response_weekly_visualizations/")

        for light_code in light_codes:
            print(f"\n       [{daily_viz.get_light_code_label(light_code)}]")
            for category in categories.keys():
                category_slug = category.replace(' ', '_').lower()
                print(f"         - {category_slug}_{light_code}_baseline_stim_weekly.png")
                print(f"         - {category_slug}_{light_code}_response_weekly.png")

        print("\n       [Heatmaps]")
        print("         - weekly_heatmap_response.png")
        print("         - weekly_heatmap_baseline.png")
        print("\n       [Statistics]")
        print("         - light_response_weekly_summary_statistics.csv")

        # Data summary
        print(f"\n[DATA] Data Summary:")
        print(f"       - Total samples:     {len(daily_viz.df):,}")
        print(f"       - Unique metrics:    {daily_viz.df['Metric'].nunique()}")
        print(f"       - Light codes:       {', '.join([daily_viz.get_light_code_label(lc) for lc in light_codes])}")
        print(f"       - Day range:         {daily_viz.df['DIFF_DAY'].min():.0f} - {daily_viz.df['DIFF_DAY'].max():.0f}")
        print(f"       - Week range:        {weekly_viz.weekly_df['Week'].min():.0f} - {weekly_viz.weekly_df['Week'].max():.0f}")
        print(f"       - Week size:         {weekly_viz.week_size} days")

        print("\n" + "=" * 80)
        print("Both daily and weekly light response analysis have been successfully completed!".center(80))
        print("=" * 80 + "\n")

        return 0  # Success

    except FileNotFoundError as e:
        print(f"\n[ERROR]: {e}")
        print("   Make sure Excel files matching '*light_response_report.xlsx' exist in 'Data_LightResponse/' directory.")
        return 1

    except ValueError as e:
        print(f"\n[ERROR]: {e}")
        print("   Check that your Excel files have the required columns: DIFF_DAY, Metric, Baseline, Stim, Response, Light_Code")
        return 1

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    exit(exit_code)
