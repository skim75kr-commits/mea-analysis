"""
Simple execution script for spontaneous activity metrics visualization
"""

from visualize_metrics import MetricsVisualizer

# Create visualizer instance
visualizer = MetricsVisualizer(data_dir='.')

# Load data
print("Loading data...")
visualizer.load_data()

# Generate all visualizations
print("\nGenerating visualizations...")
visualizer.plot_all_categories(output_dir='visualizations')

# Create heatmap
print("\nCreating heatmap...")
visualizer.create_summary_heatmap(save_path='visualizations/summary_heatmap.png')

# Generate statistics
print("\nGenerating summary statistics...")
visualizer.generate_summary_stats(save_path='visualizations/summary_statistics.csv')

print("\nDone! Check the 'visualizations' folder.")
