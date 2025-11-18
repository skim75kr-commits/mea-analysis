"""
Unified script to run both daily and weekly analysis
"""

from visualize_metrics import MetricsVisualizer
from visualize_metrics_weekly import WeeklyMetricsVisualizer
import matplotlib.pyplot as plt

print("=" * 80)
print("Spontaneous Activity Metrics - Complete Analysis (Daily + Weekly)".center(80))
print("=" * 80)

# ========== DAILY ANALYSIS ==========
print("\n" + "=" * 80)
print("PART 1: DAILY ANALYSIS".center(80))
print("=" * 80)

daily_viz = MetricsVisualizer(data_dir='.')

print("\n[Daily] Loading data...")
daily_viz.load_data()

print("\n[Daily] Generating visualizations...")
daily_viz.plot_all_categories(output_dir='visualizations')

print("\n[Daily] Creating heatmap...")
daily_viz.create_summary_heatmap(save_path='visualizations/summary_heatmap.png')
plt.close()

print("\n[Daily] Generating summary statistics...")
daily_viz.generate_summary_stats(save_path='visualizations/summary_statistics.csv')

# ========== WEEKLY ANALYSIS ==========
print("\n" + "=" * 80)
print("PART 2: WEEKLY ANALYSIS".center(80))
print("=" * 80)

weekly_viz = WeeklyMetricsVisualizer(data_dir='.', week_size=7)

print("\n[Weekly] Loading data...")
weekly_viz.load_data()

print("\n[Weekly] Creating weekly groups...")
weekly_viz.create_weekly_groups()

print("\n[Weekly] Generating visualizations...")
weekly_viz.plot_all_categories_weekly(output_dir='weekly_visualizations')

print("\n[Weekly] Creating heatmap...")
weekly_viz.create_weekly_heatmap(save_path='weekly_visualizations/weekly_heatmap.png')
plt.close()

print("\n[Weekly] Generating summary statistics...")
weekly_viz.generate_weekly_summary_stats(save_path='weekly_visualizations/weekly_summary_statistics.csv')

# ========== SUMMARY ==========
print("\n" + "=" * 80)
print("ANALYSIS COMPLETE!".center(80))
print("=" * 80)
print("\nResults saved in:")
print("  1. 'visualizations/' folder - Daily analysis")
print("  2. 'weekly_visualizations/' folder - Weekly analysis")
print("\nBoth daily and weekly analysis have been successfully completed.")
