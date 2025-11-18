"""
Optimized Daily Metrics Visualization
Professional scientific styling with improved performance
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
from typing import Optional
import warnings
warnings.filterwarnings('ignore')

from visualize_metrics_base import BaseMetricsVisualizer, ScientificPalette


class MetricsVisualizer(BaseMetricsVisualizer):
    """
    Optimized visualizer for daily metrics analysis
    Inherits common functionality from BaseMetricsVisualizer
    """

    def __init__(self, data_dir: str = '.'):
        """
        Initialize the daily metrics visualizer

        Parameters:
        -----------
        data_dir : str
            Directory containing CSV files
        """
        super().__init__(data_dir)

    def plot_metric_over_time(
        self,
        metric_name: str,
        ax: Optional[plt.Axes] = None,
        show_individual_points: bool = True
    ) -> Optional[plt.Axes]:
        """
        Plot a single metric over differentiation days with professional styling

        Parameters:
        -----------
        metric_name : str
            Name of the metric to plot
        ax : matplotlib.axes.Axes, optional
            Axis to plot on (if None, creates new figure)
        show_individual_points : bool
            Whether to show individual well data points

        Returns:
        --------
        matplotlib.axes.Axes
            The axis object
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 5))

        # Filter data for this metric
        metric_data = self.df[self.df['Metric'] == metric_name].copy()

        if len(metric_data) == 0:
            ax.text(0.5, 0.5, f'No data available\n{metric_name}',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            return ax

        # Sort by DIFF_DAY for proper line plotting
        metric_data = metric_data.sort_values('DIFF_DAY')

        # Group by DIFF_DAY and calculate statistics
        grouped = metric_data.groupby('DIFF_DAY')['Mean'].agg(['mean', 'std', 'count']).reset_index()

        # Calculate standard error
        grouped['se'] = grouped['std'] / np.sqrt(grouped['count'])

        # Plot individual points first (so they appear behind the line)
        if show_individual_points and len(metric_data) < 500:  # Avoid clutter with too many points
            ax.scatter(
                metric_data['DIFF_DAY'],
                metric_data['Mean'],
                alpha=0.25,
                s=25,
                color=self.palette.SCATTER_POINTS,
                label='Individual wells',
                zorder=1
            )

        # Plot mean line with error bars
        ax.errorbar(
            grouped['DIFF_DAY'],
            grouped['mean'],
            yerr=grouped['se'],
            marker='o',
            linestyle='-',
            linewidth=2,
            markersize=7,
            color=self.palette.MEAN_LINE,
            ecolor=self.palette.ERROR_BAR,
            capsize=4,
            capthick=1.5,
            label='Mean ± SE',
            alpha=0.9,
            zorder=2
        )

        # Formatting
        ax.set_xlabel('Differentiation Day (days)', fontsize=10, fontweight='bold')
        ax.set_ylabel('Value', fontsize=10, fontweight='bold')
        ax.set_title(self.format_metric_name(metric_name), fontsize=11, fontweight='bold', pad=10)

        # Legend
        if show_individual_points and len(metric_data) < 500:
            ax.legend(loc='best', frameon=True, fancybox=False, shadow=False, framealpha=0.9)

        # Grid
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)

        return ax

    def plot_category(
        self,
        category_name: str,
        metrics_list: list,
        save_path: Optional[Path] = None
    ) -> Optional[plt.Figure]:
        """
        Plot all metrics in a category with optimized layout

        Parameters:
        -----------
        category_name : str
            Name of the category
        metrics_list : list
            List of metric names in this category
        save_path : Path, optional
            Path to save the figure

        Returns:
        --------
        plt.Figure or None
            The figure object if metrics are available, None otherwise
        """
        # Filter metrics that exist in the data
        available_metrics = [m for m in metrics_list if m in self.df['Metric'].values]

        if not available_metrics:
            print(f"  ⚠ No data available for category: {category_name}")
            return None

        # Calculate layout
        n_metrics = len(available_metrics)
        n_rows, n_cols = self.calculate_subplot_layout(n_metrics, max_cols=3)

        # Create figure with optimized size
        fig_width = 6 * n_cols
        fig_height = 4.5 * n_rows
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_width, fig_height))

        # Handle single subplot case
        if n_metrics == 1:
            axes = np.array([axes])
        axes = axes.flatten()

        # Plot each metric
        for idx, metric in enumerate(available_metrics):
            self.plot_metric_over_time(metric, ax=axes[idx], show_individual_points=True)

        # Hide unused subplots
        for idx in range(n_metrics, len(axes)):
            axes[idx].set_visible(False)

        # Super title
        fig.suptitle(
            f'{category_name}\nDifferentiation Day Analysis',
            fontsize=14,
            fontweight='bold',
            y=0.995
        )

        plt.tight_layout(rect=[0, 0, 1, 0.99])

        # Save if path provided
        if save_path:
            self.save_figure(fig, save_path, close=False)

        return fig

    def plot_all_categories(self, output_dir: str = 'visualizations') -> None:
        """
        Create plots for all metric categories

        Parameters:
        -----------
        output_dir : str
            Directory to save visualization files
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)

        categories = self.get_metric_categories()

        print(f"\n📊 Generating category visualizations...")
        print(f"   Output directory: {output_path.absolute()}\n")

        for category_name, metrics_list in categories.items():
            print(f"  • {category_name}...")
            save_file = output_path / f"{category_name.replace(' ', '_').lower()}.png"
            fig = self.plot_category(category_name, metrics_list, save_path=save_file)
            if fig:
                plt.close(fig)

        print(f"\n✓ All visualizations saved")

    def create_summary_heatmap(self, save_path: Optional[Path] = None) -> plt.Figure:
        """
        Create a professional heatmap showing all metrics over time

        Parameters:
        -----------
        save_path : Path, optional
            Path to save the figure

        Returns:
        --------
        plt.Figure
            The figure object
        """
        # Create pivot table: Metric vs DIFF_DAY
        pivot_data = self.df.pivot_table(
            values='Mean',
            index='Metric',
            columns='DIFF_DAY',
            aggfunc='mean'
        )

        # Normalize each row (metric) to 0-1 scale for better visualization
        pivot_normalized = pivot_data.div(pivot_data.max(axis=1), axis=0)

        # Create figure with appropriate size
        fig_height = max(8, len(pivot_data) * 0.25 + 2)
        fig_width = max(10, len(pivot_data.columns) * 0.4 + 3)
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))

        # Create heatmap with colorblind-friendly palette
        sns.heatmap(
            pivot_normalized,
            cmap=self.palette.SEQUENTIAL,  # viridis is colorblind-friendly
            cbar_kws={
                'label': 'Normalized Value (0-1)',
                'shrink': 0.8,
                'aspect': 30
            },
            ax=ax,
            linewidths=0.5,
            linecolor='white',
            square=False,
            vmin=0,
            vmax=1
        )

        # Format y-axis labels (metric names)
        y_labels = [self.format_metric_name(label.get_text()) for label in ax.get_yticklabels()]
        ax.set_yticklabels(y_labels, rotation=0, fontsize=8)

        # Format x-axis labels (days)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right', fontsize=8)

        ax.set_xlabel('Differentiation Day', fontsize=11, fontweight='bold')
        ax.set_ylabel('Metric', fontsize=11, fontweight='bold')
        ax.set_title(
            'Normalized Metrics Heatmap Across Differentiation Days',
            fontsize=13,
            fontweight='bold',
            pad=15
        )

        plt.tight_layout()

        if save_path:
            self.save_figure(fig, save_path, close=False)

        return fig

    def generate_summary_stats(self, save_path: str = 'summary_statistics.csv') -> pd.DataFrame:
        """
        Generate comprehensive summary statistics table

        Parameters:
        -----------
        save_path : str
            Path to save the summary CSV file

        Returns:
        --------
        pd.DataFrame
            Summary statistics dataframe
        """
        summary = self.df.groupby(['Metric', 'DIFF_DAY']).agg({
            'Mean': ['mean', 'std', 'count', 'min', 'max', 'median']
        }).reset_index()

        # Flatten column names
        summary.columns = [
            'Metric', 'DIFF_DAY', 'Mean_Value', 'Std_Value',
            'N_Samples', 'Min_Value', 'Max_Value', 'Median_Value'
        ]

        # Calculate coefficient of variation
        summary['CV'] = (summary['Std_Value'] / summary['Mean_Value'] * 100).round(2)

        # Calculate standard error
        summary['SE'] = (summary['Std_Value'] / np.sqrt(summary['N_Samples'])).round(4)

        # Save to CSV
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(save_path, index=False)

        print(f"\n✓ Summary statistics saved: {save_path}")
        print(f"  Total records: {len(summary):,}")

        return summary


def main():
    """Main execution function for daily analysis"""
    print("=" * 80)
    print("MEA Spontaneous Activity Metrics - Daily Analysis (Optimized)".center(80))
    print("=" * 80)

    try:
        # Initialize visualizer
        visualizer = MetricsVisualizer(data_dir='.')

        # Load data
        print("\n[Step 1/4] Loading data...")
        visualizer.load_data()

        # Generate all category plots
        print("\n[Step 2/4] Generating category-wise visualizations...")
        visualizer.plot_all_categories(output_dir='visualizations')

        # Create summary heatmap
        print("\n[Step 3/4] Creating summary heatmap...")
        visualizer.create_summary_heatmap(save_path='visualizations/summary_heatmap.png')
        plt.close('all')

        # Generate summary statistics
        print("\n[Step 4/4] Generating summary statistics...")
        visualizer.generate_summary_stats(save_path='visualizations/summary_statistics.csv')

        print("\n" + "=" * 80)
        print("✓ Daily Analysis Complete!".center(80))
        print("=" * 80)
        print("\n📁 Check the 'visualizations/' folder for all generated files.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
