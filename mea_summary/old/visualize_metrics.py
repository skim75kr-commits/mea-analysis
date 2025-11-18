"""
Spontaneous Activity Metrics Visualization
Visualizes the change of metrics according to differentiation day (DIFF_DAY)
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (15, 10)
plt.rcParams['font.size'] = 10

class MetricsVisualizer:
    def __init__(self, data_dir='.'):
        """
        Initialize the visualizer

        Parameters:
        -----------
        data_dir : str
            Directory containing CSV files
        """
        self.data_dir = Path(data_dir)
        self.df = None

    def load_data(self):
        """Load all CSV files and combine them"""
        csv_files = list(self.data_dir.glob('*spontaneous_activity.csv'))

        if not csv_files:
            raise FileNotFoundError("No CSV files found in the directory")

        print(f"Found {len(csv_files)} CSV files:")
        for f in csv_files:
            print(f"  - {f.name}")

        # Read and combine all CSV files
        dfs = []
        for file in csv_files:
            df_temp = pd.read_csv(file)
            dfs.append(df_temp)

        self.df = pd.concat(dfs, ignore_index=True)
        print(f"\nTotal rows loaded: {len(self.df)}")
        print(f"Unique metrics: {self.df['Metric'].nunique()}")
        print(f"DIFF_DAY range: {self.df['DIFF_DAY'].min()} - {self.df['DIFF_DAY'].max()}")

        return self.df

    def get_metric_categories(self):
        """Categorize metrics into groups"""
        categories = {
            'Firing Rate': [
                'mean_firing_rate_hz',
                'weighted_mean_firing_rate_hz'
            ],
            'Burst Characteristics': [
                'burst_duration__avg_s',
                'burst_duration__std_s',
                'burst_frequency__avg_hz',
                'burst_frequency__std_hz',
                'burst_percentage__avg',
                'burst_percentage__std'
            ],
            'Inter-Burst Interval': [
                'inter_burst_interval__avg_s',
                'inter_burst_interval__std_s',
                'ibi_coefficient_of_variation__avg',
                'ibi_coefficient_of_variation__std'
            ],
            'ISI (Inter-Spike Interval)': [
                'mean_isi_within_burst__avg',
                'mean_isi_within_burst__std',
                'median_isi_within_burst__avg',
                'median_isi_within_burst__std',
                'isi_coefficient_of_variation__avg'
            ],
            'Network Activity': [
                'number_of_active_electrodes',
                'number_of_bursting_electrodes',
                'number_of_bursts',
                'number_of_network_bursts',
                'number_of_spikes'
            ],
            'Synchrony & Correlation': [
                'area_under_cross_correlation',
                'area_under_normalized_cross_correlation',
                'synchrony_index',
                'width_at_half_height_of_cross_correlation',
                'width_at_half_height_of_normalized_cross_correlation',
                'network_isi_coefficient_of_variation'
            ],
            'Network Burst': [
                'network_burst_duration__avg_sec',
                'network_burst_frequency__avg_hz',
                'network_burst_percentage__avg'
            ]
        }
        return categories

    def plot_metric_over_time(self, metric_name, ax=None, show_individual_points=True):
        """
        Plot a single metric over differentiation days

        Parameters:
        -----------
        metric_name : str
            Name of the metric to plot
        ax : matplotlib axis
            Axis to plot on (if None, creates new figure)
        show_individual_points : bool
            Whether to show individual data points
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        # Filter data for this metric
        metric_data = self.df[self.df['Metric'] == metric_name].copy()

        if len(metric_data) == 0:
            ax.text(0.5, 0.5, f'No data for {metric_name}',
                   ha='center', va='center', transform=ax.transAxes)
            return

        # Sort by DIFF_DAY
        metric_data = metric_data.sort_values('DIFF_DAY')

        # Group by DIFF_DAY and calculate statistics
        grouped = metric_data.groupby('DIFF_DAY')['Mean'].agg(['mean', 'std', 'count']).reset_index()

        # Calculate standard error
        grouped['se'] = grouped['std'] / np.sqrt(grouped['count'])

        # Plot line with error bars
        ax.errorbar(grouped['DIFF_DAY'], grouped['mean'],
                   yerr=grouped['se'],
                   marker='o', linestyle='-', linewidth=2,
                   markersize=8, capsize=5, capthick=2,
                   label='Mean ± SE', alpha=0.8)

        # Add individual points if requested
        if show_individual_points:
            ax.scatter(metric_data['DIFF_DAY'], metric_data['Mean'],
                      alpha=0.3, s=30, color='gray', label='Individual wells')

        ax.set_xlabel('Differentiation Day', fontsize=12, fontweight='bold')
        ax.set_ylabel('Value', fontsize=12, fontweight='bold')
        ax.set_title(metric_name.replace('_', ' ').title(), fontsize=13, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def plot_category(self, category_name, metrics_list, save_path=None):
        """
        Plot all metrics in a category

        Parameters:
        -----------
        category_name : str
            Name of the category
        metrics_list : list
            List of metric names in this category
        save_path : str
            Path to save the figure (optional)
        """
        # Filter metrics that exist in the data
        available_metrics = [m for m in metrics_list if m in self.df['Metric'].values]

        if not available_metrics:
            print(f"No data available for category: {category_name}")
            return

        n_metrics = len(available_metrics)
        n_cols = min(3, n_metrics)
        n_rows = (n_metrics + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(6*n_cols, 5*n_rows))
        if n_metrics == 1:
            axes = [axes]
        else:
            axes = axes.flatten() if n_rows > 1 else axes

        for idx, metric in enumerate(available_metrics):
            self.plot_metric_over_time(metric, ax=axes[idx])

        # Hide unused subplots
        for idx in range(n_metrics, len(axes)):
            axes[idx].set_visible(False)

        plt.suptitle(f'{category_name} - Over Differentiation Days',
                    fontsize=16, fontweight='bold', y=1.00)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Saved: {save_path}")

        return fig

    def plot_all_categories(self, output_dir='visualizations'):
        """
        Create plots for all metric categories

        Parameters:
        -----------
        output_dir : str
            Directory to save visualization files
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        categories = self.get_metric_categories()

        print("\nGenerating visualizations...")
        for category_name, metrics_list in categories.items():
            print(f"\nProcessing: {category_name}")
            save_file = output_path / f"{category_name.replace(' ', '_').lower()}.png"
            self.plot_category(category_name, metrics_list, save_path=save_file)
            plt.close()

        print(f"\nAll visualizations saved to: {output_path.absolute()}")

    def create_summary_heatmap(self, save_path=None):
        """
        Create a heatmap showing all metrics over time

        Parameters:
        -----------
        save_path : str
            Path to save the figure (optional)
        """
        # Create pivot table: DIFF_DAY vs Metric
        pivot_data = self.df.pivot_table(
            values='Mean',
            index='Metric',
            columns='DIFF_DAY',
            aggfunc='mean'
        )

        # Normalize each row (metric) to 0-1 scale for better visualization
        pivot_normalized = pivot_data.div(pivot_data.max(axis=1), axis=0)

        fig, ax = plt.subplots(figsize=(12, len(pivot_data)*0.3 + 2))
        sns.heatmap(pivot_normalized, cmap='YlOrRd', cbar_kws={'label': 'Normalized Value'},
                   ax=ax, linewidths=0.5, linecolor='white')

        ax.set_xlabel('Differentiation Day', fontsize=12, fontweight='bold')
        ax.set_ylabel('Metric', fontsize=12, fontweight='bold')
        ax.set_title('All Metrics Heatmap (Normalized) Over Differentiation Days',
                    fontsize=14, fontweight='bold')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Saved heatmap: {save_path}")

        return fig

    def generate_summary_stats(self, save_path='summary_statistics.csv'):
        """
        Generate summary statistics table

        Parameters:
        -----------
        save_path : str
            Path to save the summary CSV file
        """
        summary = self.df.groupby(['Metric', 'DIFF_DAY']).agg({
            'Mean': ['mean', 'std', 'count', 'min', 'max']
        }).reset_index()

        summary.columns = ['Metric', 'DIFF_DAY', 'Mean_Value', 'Std_Value',
                          'N_Samples', 'Min_Value', 'Max_Value']

        summary.to_csv(save_path, index=False)
        print(f"\nSummary statistics saved to: {save_path}")

        return summary


def main():
    """Main execution function"""
    print("=" * 70)
    print("Spontaneous Activity Metrics Visualization".center(70))
    print("=" * 70)

    # Initialize visualizer
    visualizer = MetricsVisualizer(data_dir='.')

    # Load data
    print("\n[Step 1] Loading data...")
    visualizer.load_data()

    # Generate all category plots
    print("\n[Step 2] Generating category-wise visualizations...")
    visualizer.plot_all_categories(output_dir='visualizations')

    # Create summary heatmap
    print("\n[Step 3] Creating summary heatmap...")
    visualizer.create_summary_heatmap(save_path='visualizations/summary_heatmap.png')
    plt.close()

    # Generate summary statistics
    print("\n[Step 4] Generating summary statistics...")
    visualizer.generate_summary_stats(save_path='visualizations/summary_statistics.csv')

    print("\n" + "=" * 70)
    print("Analysis Complete!".center(70))
    print("=" * 70)
    print("\nCheck the 'visualizations' folder for all generated plots and statistics.")


if __name__ == '__main__':
    main()
