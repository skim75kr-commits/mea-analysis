"""
Optimized execution script for daily spontaneous activity metrics visualization
"""

from visualize_metrics_optimized import MetricsVisualizer
import matplotlib.pyplot as plt


def main():
    """Execute daily analysis with optimized code"""
    print("=" * 80)
    print("MEA Spontaneous Activity - Daily Analysis (Optimized)".center(80))
    print("=" * 80)

    try:
        # Create visualizer instance
        visualizer = MetricsVisualizer(data_dir='.')

        # Load data
        print("\n[1/4] Loading data...")
        visualizer.load_data()

        # Generate all visualizations
        print("\n[2/4] Generating visualizations...")
        visualizer.plot_all_categories(output_dir='visualizations')

        # Create heatmap
        print("\n[3/4] Creating heatmap...")
        visualizer.create_summary_heatmap(save_path='visualizations/summary_heatmap.png')
        plt.close('all')

        # Generate statistics
        print("\n[4/4] Generating summary statistics...")
        visualizer.generate_summary_stats(save_path='visualizations/summary_statistics.csv')

        print("\n" + "=" * 80)
        print("✓ Done! Check the 'visualizations/' folder.".center(80))
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
