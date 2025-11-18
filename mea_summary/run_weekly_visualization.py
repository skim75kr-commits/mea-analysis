"""
Simple execution script for weekly spontaneous activity metrics visualization
"""

from visualize_metrics_weekly import WeeklyMetricsVisualizer

# Create visualizer instance (7 days per week)
visualizer = WeeklyMetricsVisualizer(data_dir='.', week_size=7)

# Load data
print("Loading data...")
visualizer.load_data()

# Create weekly groups
print("\nCreating weekly groups...")
visualizer.create_weekly_groups()

# Generate all visualizations
print("\nGenerating weekly visualizations...")
visualizer.plot_all_categories_weekly(output_dir='weekly_visualizations')

# Create heatmap
print("\nCreating weekly heatmap...")
visualizer.create_weekly_heatmap(save_path='weekly_visualizations/weekly_heatmap.png')

# Generate statistics
print("\nGenerating weekly summary statistics...")
visualizer.generate_weekly_summary_stats(save_path='weekly_visualizations/weekly_summary_statistics.csv')

print("\nDone! Check the 'weekly_visualizations' folder.")
