"""
Optimized execution script for weekly spontaneous activity metrics visualization
"""

from visualize_metrics_weekly_optimized import WeeklyMetricsVisualizer
import matplotlib.pyplot as plt


def main():
    """Execute weekly analysis with optimized code"""
    print("=" * 80)
    print("MEA Spontaneous Activity - Weekly Analysis (Optimized)".center(80))
    print("=" * 80)

    try:
        # Create visualizer instance (7 days per week)
        visualizer = WeeklyMetricsVisualizer(data_dir='.', week_size=7)

        # Load data
        print("\n[1/5] Loading data...")
        visualizer.load_data()

        # Create weekly groups
        print("\n[2/5] Creating weekly groups...")
        visualizer.create_weekly_groups()

        # Generate all visualizations
        print("\n[3/5] Generating weekly visualizations...")
        visualizer.plot_all_categories_weekly(output_dir='weekly_visualizations')

        # Create heatmap
        print("\n[4/5] Creating weekly heatmap...")
        visualizer.create_weekly_heatmap(save_path='weekly_visualizations/weekly_heatmap.png')
        plt.close('all')

        # Generate statistics
        print("\n[5/5] Generating weekly summary statistics...")
        visualizer.generate_weekly_summary_stats(save_path='weekly_visualizations/weekly_summary_statistics.csv')

        print("\n" + "=" * 80)
        print("✓ Done! Check the 'weekly_visualizations/' folder.".center(80))
        print("=" * 80 + "\n")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    exit(exit_code)
