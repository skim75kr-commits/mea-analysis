"""
Spontaneous Activity Metrics Visualization - Weekly Analysis
Visualizes the change of metrics according to differentiation day grouped by weeks
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

class WeeklyMetricsVisualizer:
    def __init__(self, data_dir='.', week_size=7):
        """
        Initialize the weekly visualizer

        Parameters:
        -----------
        data_dir : str
            Directory containing CSV files
        week_size : int
            Number of days per week (default: 7)
        """
        self.data_dir = Path(data_dir)
        self.week_size = week_size
        self.df = None
        self.weekly_df = None

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

    def create_weekly_groups(self):
        """Group DIFF_DAY into weeks"""
        if self.df is None:
            raise ValueError("Please load data first using load_data()")

        # Create week number based on DIFF_DAY
        self.df['Week'] = (self.df['DIFF_DAY'] // self.week_size) + 1
        self.df['Week_Label'] = 'Week ' + self.df['Week'].astype(str)

        # Create a more descriptive label showing day range
        self.df['Week_Range'] = self.df['Week'].apply(
            lambda w: f"Week {w}\n(Day {(w-1)*self.week_size + 1}-{w*self.week_size})"
        )

        # Group by Week and Metric, calculate statistics
        self.weekly_df = self.df.groupby(['Week', 'Week_Label', 'Week_Range', 'Metric']).agg({
            'Mean': ['mean', 'std', 'count', 'min', 'max'],
            'DIFF_DAY': ['min', 'max']  # Track the actual day range
        }).reset_index()

        # Flatten column names
        self.weekly_df.columns = [
            'Week', 'Week_Label', 'Week_Range', 'Metric',
            'Mean_Avg', 'Mean_Std', 'N_Samples', 'Mean_Min', 'Mean_Max',
            'Day_Start', 'Day_End'
        ]

        # Calculate standard error
        self.weekly_df['SE'] = self.weekly_df['Mean_Std'] / np.sqrt(self.weekly_df['N_Samples'])

        print(f"\nWeekly grouping created:")
        print(f"Number of weeks: {self.weekly_df['Week'].nunique()}")
        print(f"Week range: {self.weekly_df['Week'].min()} - {self.weekly_df['Week'].max()}")

        return self.weekly_df

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

    def plot_metric_weekly(self, metric_name, ax=None, show_individual_weeks=True):
        """
        Plot a single metric over weeks

        Parameters:
        -----------
        metric_name : str
            Name of the metric to plot
        ax : matplotlib axis
            Axis to plot on (if None, creates new figure)
        show_individual_weeks : bool
            Whether to show individual week data points
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        # Filter data for this metric
        metric_data = self.weekly_df[self.weekly_df['Metric'] == metric_name].copy()

        if len(metric_data) == 0:
            ax.text(0.5, 0.5, f'No data for {metric_name}',
                   ha='center', va='center', transform=ax.transAxes)
            return

        # Sort by Week
        metric_data = metric_data.sort_values('Week')

        # Plot line with error bars
        ax.errorbar(metric_data['Week'], metric_data['Mean_Avg'],
                   yerr=metric_data['SE'],
                   marker='o', linestyle='-', linewidth=2.5,
                   markersize=10, capsize=6, capthick=2,
                   label='Weekly Mean ± SE', alpha=0.8, color='#2E86AB')

        # Add individual week points if requested
        if show_individual_weeks:
            for _, row in metric_data.iterrows():
                # Get individual data points for this week
                week_points = self.df[
                    (self.df['Metric'] == metric_name) &
                    (self.df['Week'] == row['Week'])
                ]['Mean']

                if len(week_points) > 0:
                    # Add jitter to x-axis for visibility
                    x_jitter = np.random.normal(row['Week'], 0.05, len(week_points))
                    ax.scatter(x_jitter, week_points,
                             alpha=0.3, s=40, color='gray')

        # Customize x-axis to show week labels
        ax.set_xticks(metric_data['Week'].values)
        ax.set_xticklabels([f"W{int(w)}" for w in metric_data['Week'].values])

        ax.set_xlabel('Week', fontsize=12, fontweight='bold')
        ax.set_ylabel('Value', fontsize=12, fontweight='bold')
        ax.set_title(f"{metric_name.replace('_', ' ').title()}\n(Weekly Aggregation)",
                    fontsize=13, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        # Add week range info in the corner
        week_info = f"Week size: {self.week_size} days"
        ax.text(0.02, 0.98, week_info, transform=ax.transAxes,
               fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    def plot_category_weekly(self, category_name, metrics_list, save_path=None):
        """
        Plot all metrics in a category (weekly)

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
        available_metrics = [m for m in metrics_list if m in self.weekly_df['Metric'].values]

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
            self.plot_metric_weekly(metric, ax=axes[idx])

        # Hide unused subplots
        for idx in range(n_metrics, len(axes)):
            axes[idx].set_visible(False)

        plt.suptitle(f'{category_name} - Weekly Analysis',
                    fontsize=16, fontweight='bold', y=1.00)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Saved: {save_path}")

        return fig

    def plot_all_categories_weekly(self, output_dir='weekly_visualizations'):
        """
        Create weekly plots for all metric categories

        Parameters:
        -----------
        output_dir : str
            Directory to save visualization files
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        categories = self.get_metric_categories()

        print("\nGenerating weekly visualizations...")
        for category_name, metrics_list in categories.items():
            print(f"\nProcessing: {category_name}")
            save_file = output_path / f"{category_name.replace(' ', '_').lower()}_weekly.png"
            self.plot_category_weekly(category_name, metrics_list, save_path=save_file)
            plt.close()

        print(f"\nAll weekly visualizations saved to: {output_path.absolute()}")

    def create_weekly_heatmap(self, save_path=None):
        """
        Create a heatmap showing all metrics over weeks

        Parameters:
        -----------
        save_path : str
            Path to save the figure (optional)
        """
        # Create pivot table: Week vs Metric
        pivot_data = self.weekly_df.pivot_table(
            values='Mean_Avg',
            index='Metric',
            columns='Week',
            aggfunc='mean'
        )

        # Normalize each row (metric) to 0-1 scale for better visualization
        pivot_normalized = pivot_data.div(pivot_data.max(axis=1), axis=0)

        fig, ax = plt.subplots(figsize=(max(12, len(pivot_data.columns)*0.8),
                                        len(pivot_data)*0.3 + 2))
        sns.heatmap(pivot_normalized, cmap='YlOrRd', cbar_kws={'label': 'Normalized Value'},
                   ax=ax, linewidths=0.5, linecolor='white', annot=False)

        # Customize x-axis labels to show weeks
        week_labels = [f'Week {int(w)}' for w in pivot_data.columns]
        ax.set_xticklabels(week_labels, rotation=0)

        ax.set_xlabel('Week', fontsize=12, fontweight='bold')
        ax.set_ylabel('Metric', fontsize=12, fontweight='bold')
        ax.set_title(f'All Metrics Heatmap (Normalized) - Weekly Analysis\n(Week size: {self.week_size} days)',
                    fontsize=14, fontweight='bold')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Saved heatmap: {save_path}")

        return fig

    def generate_weekly_summary_stats(self, save_path='weekly_summary_statistics.csv'):
        """
        Generate weekly summary statistics table

        Parameters:
        -----------
        save_path : str
            Path to save the summary CSV file
        """
        summary = self.weekly_df.copy()
        summary = summary[['Metric', 'Week', 'Week_Label', 'Day_Start', 'Day_End',
                          'Mean_Avg', 'Mean_Std', 'SE', 'N_Samples', 'Mean_Min', 'Mean_Max']]

        summary.to_csv(save_path, index=False)
        print(f"\nWeekly summary statistics saved to: {save_path}")

        return summary

    def create_comparison_plot(self, metric_name, save_path=None):
        """
        Create a comparison plot showing both daily and weekly trends

        Parameters:
        -----------
        metric_name : str
            Name of the metric to plot
        save_path : str
            Path to save the figure (optional)
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

        # Daily plot
        daily_data = self.df[self.df['Metric'] == metric_name].copy()
        daily_data = daily_data.sort_values('DIFF_DAY')
        grouped_daily = daily_data.groupby('DIFF_DAY')['Mean'].agg(['mean', 'std', 'count']).reset_index()
        grouped_daily['se'] = grouped_daily['std'] / np.sqrt(grouped_daily['count'])

        ax1.errorbar(grouped_daily['DIFF_DAY'], grouped_daily['mean'],
                    yerr=grouped_daily['se'],
                    marker='o', linestyle='-', linewidth=2,
                    markersize=6, capsize=4, capthick=1.5,
                    label='Daily Mean ± SE', alpha=0.8, color='#A23B72')
        ax1.scatter(daily_data['DIFF_DAY'], daily_data['Mean'],
                   alpha=0.2, s=20, color='gray')
        ax1.set_xlabel('Differentiation Day', fontsize=11, fontweight='bold')
        ax1.set_ylabel('Value', fontsize=11, fontweight='bold')
        ax1.set_title('Daily Analysis', fontsize=12, fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Weekly plot
        self.plot_metric_weekly(metric_name, ax=ax2, show_individual_weeks=True)

        plt.suptitle(f'{metric_name.replace("_", " ").title()}\nDaily vs Weekly Comparison',
                    fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Saved comparison plot: {save_path}")

        return fig


def main():
    """Main execution function for weekly analysis"""
    print("=" * 70)
    print("Spontaneous Activity Metrics - Weekly Analysis".center(70))
    print("=" * 70)

    # Initialize visualizer with 7-day weeks
    visualizer = WeeklyMetricsVisualizer(data_dir='.', week_size=7)

    # Load data
    print("\n[Step 1] Loading data...")
    visualizer.load_data()

    # Create weekly groups
    print("\n[Step 2] Creating weekly groups...")
    visualizer.create_weekly_groups()

    # Generate all category plots (weekly)
    print("\n[Step 3] Generating weekly visualizations...")
    visualizer.plot_all_categories_weekly(output_dir='weekly_visualizations')

    # Create weekly heatmap
    print("\n[Step 4] Creating weekly heatmap...")
    visualizer.create_weekly_heatmap(save_path='weekly_visualizations/weekly_heatmap.png')
    plt.close()

    # Generate weekly summary statistics
    print("\n[Step 5] Generating weekly summary statistics...")
    visualizer.generate_weekly_summary_stats(save_path='weekly_visualizations/weekly_summary_statistics.csv')

    print("\n" + "=" * 70)
    print("Weekly Analysis Complete!".center(70))
    print("=" * 70)
    print("\nCheck the 'weekly_visualizations' folder for all generated plots and statistics.")


if __name__ == '__main__':
    main()
