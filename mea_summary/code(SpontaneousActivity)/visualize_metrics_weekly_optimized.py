"""
Optimized Weekly Metrics Visualization
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


class WeeklyMetricsVisualizer(BaseMetricsVisualizer):
    """
    Optimized visualizer for weekly metrics analysis
    Inherits common functionality from BaseMetricsVisualizer
    """

    def __init__(self, data_dir: str = '.', week_size: int = 7):
        """
        Initialize the weekly metrics visualizer

        Parameters:
        -----------
        data_dir : str
            Directory containing CSV files
        week_size : int
            Number of days per week (default: 7)
        """
        super().__init__(data_dir)
        self.week_size = week_size
        self.weekly_df: Optional[pd.DataFrame] = None

    def create_weekly_groups(self) -> pd.DataFrame:
        """
        Group DIFF_DAY data into weeks with comprehensive statistics

        Returns:
        --------
        pd.DataFrame
            Weekly aggregated dataframe
        """
        if self.df is None:
            raise ValueError("Please load data first using load_data()")

        # Create week number based on DIFF_DAY
        self.df['Week'] = (self.df['DIFF_DAY'] // self.week_size) + 1
        self.df['Week_Label'] = 'Week ' + self.df['Week'].astype(str)

        # Create descriptive label showing day range
        self.df['Week_Range'] = self.df['Week'].apply(
            lambda w: f"W{w} (D{(w-1)*self.week_size + 1}-{w*self.week_size})"
        )

        # Group by Week and Metric, calculate comprehensive statistics
        self.weekly_df = self.df.groupby(['Week', 'Week_Label', 'Week_Range', 'Metric']).agg({
            'Mean': ['mean', 'std', 'count', 'min', 'max', 'median'],
            'DIFF_DAY': ['min', 'max']
        }).reset_index()

        # Flatten column names
        self.weekly_df.columns = [
            'Week', 'Week_Label', 'Week_Range', 'Metric',
            'Mean_Avg', 'Mean_Std', 'N_Samples', 'Mean_Min', 'Mean_Max', 'Mean_Median',
            'Day_Start', 'Day_End'
        ]

        # Calculate standard error
        self.weekly_df['SE'] = self.weekly_df['Mean_Std'] / np.sqrt(self.weekly_df['N_Samples'])

        # Calculate coefficient of variation
        self.weekly_df['CV'] = (self.weekly_df['Mean_Std'] / self.weekly_df['Mean_Avg'] * 100).round(2)

        print(f"\n✓ Weekly grouping created:")
        print(f"  Week size: {self.week_size} days")
        print(f"  Number of weeks: {self.weekly_df['Week'].nunique()}")
        print(f"  Week range: {self.weekly_df['Week'].min():.0f} - {self.weekly_df['Week'].max():.0f}")

        return self.weekly_df

    def plot_metric_weekly(
        self,
        metric_name: str,
        ax: Optional[plt.Axes] = None,
        show_individual_points: bool = True
    ) -> Optional[plt.Axes]:
        """
        Plot a single metric over weeks with professional styling

        Parameters:
        -----------
        metric_name : str
            Name of the metric to plot
        ax : matplotlib.axes.Axes, optional
            Axis to plot on (if None, creates new figure)
        show_individual_points : bool
            Whether to show individual daily data points within weeks

        Returns:
        --------
        matplotlib.axes.Axes
            The axis object
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 5))

        # Filter data for this metric
        metric_data = self.weekly_df[self.weekly_df['Metric'] == metric_name].copy()

        if len(metric_data) == 0:
            ax.text(0.5, 0.5, f'No data available\n{metric_name}',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            return ax

        # Sort by Week
        metric_data = metric_data.sort_values('Week')

        # Plot individual daily points within each week (if requested and not too many)
        if show_individual_points:
            daily_data = self.df[self.df['Metric'] == metric_name].copy()
            if len(daily_data) < 300:  # Avoid clutter
                # Add small jitter to week number for visibility
                jitter_strength = 0.08
                for _, row in metric_data.iterrows():
                    week_points = daily_data[daily_data['Week'] == row['Week']]['Mean'].values
                    if len(week_points) > 0:
                        x_jitter = np.random.normal(row['Week'], jitter_strength, len(week_points))
                        ax.scatter(
                            x_jitter,
                            week_points,
                            alpha=0.25,
                            s=30,
                            color=self.palette.SCATTER_POINTS,
                            zorder=1
                        )

        # Plot weekly mean line with error bars
        ax.errorbar(
            metric_data['Week'],
            metric_data['Mean_Avg'],
            yerr=metric_data['SE'],
            marker='o',
            linestyle='-',
            linewidth=2.5,
            markersize=9,
            color=self.palette.MEAN_LINE,
            ecolor=self.palette.ERROR_BAR,
            capsize=5,
            capthick=2,
            label='Weekly Mean ± SEM',
            alpha=0.9,
            zorder=2
        )

        # Optimize X and Y axis limits after plotting
        self.optimize_y_limits(ax, metric_data['Mean_Avg'].values)
        self.optimize_x_limits(ax, metric_data['Week'].values)

        # Add differentiation phases (after axis limits are set)
        x_min = metric_data['Week'].min()
        x_max = metric_data['Week'].max()
        self.add_differentiation_phases(ax, x_min, x_max, phase_type='week')

        # Customize x-axis to show week labels
        ax.set_xticks(metric_data['Week'].values)
        ax.set_xticklabels([f"W{int(w)}" for w in metric_data['Week'].values])

        # Formatting
        ax.set_xlabel(f'Week ({self.week_size}-day periods)', fontsize=10, fontweight='bold')
        ax.set_ylabel('Value', fontsize=10, fontweight='bold')
        ax.set_title(
            f"{self.format_metric_name(metric_name)}\n(Weekly Aggregation)",
            fontsize=11,
            fontweight='bold',
            pad=10
        )

        # Add sample size and error bar info
        n_samples = int(metric_data['N_Samples'].mean())
        ax.text(0.02, 0.02, f'n={n_samples} (avg)\nError bars: SEM',
               transform=ax.transAxes, fontsize=7,
               verticalalignment='bottom', horizontalalignment='left',
               bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                        edgecolor='gray', alpha=0.8, linewidth=0.5))

        # Legend
        ax.legend(loc='best', frameon=True, fancybox=False, shadow=False, framealpha=0.9, fontsize=8)

        # Grid
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)

        return ax

    def plot_category_weekly(
        self,
        category_name: str,
        metrics_list: list,
        save_path: Optional[Path] = None
    ) -> Optional[plt.Figure]:
        """
        Plot all metrics in a category (weekly) with optimized layout

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
        available_metrics = [m for m in metrics_list if m in self.weekly_df['Metric'].values]

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
            self.plot_metric_weekly(metric, ax=axes[idx], show_individual_points=True)

        # Hide unused subplots
        for idx in range(n_metrics, len(axes)):
            axes[idx].set_visible(False)

        # Super title
        fig.suptitle(
            f'{category_name}\nWeekly Analysis ({self.week_size}-day periods)',
            fontsize=14,
            fontweight='bold',
            y=0.995
        )

        plt.tight_layout(rect=[0, 0, 1, 0.99])

        # Save if path provided
        if save_path:
            self.save_figure(fig, save_path, close=False)

        return fig

    def plot_all_categories_weekly(self, output_dir: str = 'weekly_visualizations') -> None:
        """
        Create weekly plots for all metric categories

        Parameters:
        -----------
        output_dir : str
            Directory to save visualization files
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)

        categories = self.get_metric_categories()

        print(f"\n📊 Generating weekly category visualizations...")
        print(f"   Output directory: {output_path.absolute()}\n")

        for category_name, metrics_list in categories.items():
            print(f"  • {category_name}...")
            save_file = output_path / f"{category_name.replace(' ', '_').lower()}_weekly.png"
            fig = self.plot_category_weekly(category_name, metrics_list, save_path=save_file)
            if fig:
                plt.close(fig)

        print(f"\n✓ All weekly visualizations saved")

    def create_weekly_heatmap(self, save_path: Optional[Path] = None) -> plt.Figure:
        """
        Create a professional heatmap showing all metrics over weeks

        Parameters:
        -----------
        save_path : Path, optional
            Path to save the figure

        Returns:
        --------
        plt.Figure
            The figure object
        """
        # Create pivot table: Metric vs Week
        pivot_data = self.weekly_df.pivot_table(
            values='Mean_Avg',
            index='Metric',
            columns='Week',
            aggfunc='mean'
        )

        # Normalize each row (metric) to 0-1 scale for better visualization
        pivot_normalized = pivot_data.div(pivot_data.max(axis=1), axis=0)

        # Create figure with appropriate size
        fig_height = max(8, len(pivot_data) * 0.25 + 2)
        fig_width = max(10, len(pivot_data.columns) * 0.6 + 3)
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))

        # Create heatmap with colorblind-friendly palette
        sns.heatmap(
            pivot_normalized,
            cmap=self.palette.SEQUENTIAL,
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

        # Format x-axis labels (weeks)
        week_labels = [f'W{int(w)}' for w in pivot_data.columns]
        ax.set_xticklabels(week_labels, rotation=0, fontsize=9)

        ax.set_xlabel(f'Week ({self.week_size}-day periods)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Metric', fontsize=11, fontweight='bold')
        ax.set_title(
            f'Normalized Metrics Heatmap - Weekly Analysis\n(Week size: {self.week_size} days)',
            fontsize=13,
            fontweight='bold',
            pad=15
        )

        plt.tight_layout()

        if save_path:
            self.save_figure(fig, save_path, close=False)

        return fig

    def generate_weekly_summary_stats(
        self,
        save_path: str = 'weekly_summary_statistics.csv'
    ) -> pd.DataFrame:
        """
        Generate comprehensive weekly summary statistics table

        Parameters:
        -----------
        save_path : str
            Path to save the summary CSV file

        Returns:
        --------
        pd.DataFrame
            Weekly summary statistics dataframe
        """
        summary = self.weekly_df.copy()

        # Select and reorder columns
        summary = summary[[
            'Metric', 'Week', 'Week_Label', 'Week_Range',
            'Day_Start', 'Day_End',
            'Mean_Avg', 'Mean_Std', 'SE', 'CV',
            'N_Samples', 'Mean_Min', 'Mean_Max', 'Mean_Median'
        ]]

        # Rename for clarity
        summary.columns = [
            'Metric', 'Week_Number', 'Week_Label', 'Week_Range',
            'Day_Start', 'Day_End',
            'Weekly_Mean', 'Weekly_Std', 'Standard_Error', 'CV_Percent',
            'N_Daily_Samples', 'Min_Daily_Value', 'Max_Daily_Value', 'Median_Daily_Value'
        ]

        # Save to CSV
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(save_path, index=False)

        print(f"\n✓ Weekly summary statistics saved: {save_path}")
        print(f"  Total records: {len(summary):,}")

        return summary


def main():
    """Main execution function for weekly analysis"""
    print("=" * 80)
    print("MEA Spontaneous Activity Metrics - Weekly Analysis (Optimized)".center(80))
    print("=" * 80)

    try:
        # Initialize visualizer with 7-day weeks
        visualizer = WeeklyMetricsVisualizer(data_dir='.', week_size=7)

        # Load data
        print("\n[Step 1/5] Loading data...")
        visualizer.load_data()

        # Create weekly groups
        print("\n[Step 2/5] Creating weekly groups...")
        visualizer.create_weekly_groups()

        # Generate all category plots (weekly)
        print("\n[Step 3/5] Generating weekly visualizations...")
        visualizer.plot_all_categories_weekly(output_dir='weekly_visualizations')

        # Create weekly heatmap
        print("\n[Step 4/5] Creating weekly heatmap...")
        visualizer.create_weekly_heatmap(save_path='weekly_visualizations/weekly_heatmap.png')
        plt.close('all')

        # Generate weekly summary statistics
        print("\n[Step 5/5] Generating weekly summary statistics...")
        visualizer.generate_weekly_summary_stats(save_path='weekly_visualizations/weekly_summary_statistics.csv')

        print("\n" + "=" * 80)
        print("✓ Weekly Analysis Complete!".center(80))
        print("=" * 80)
        print("\n📁 Check the 'weekly_visualizations/' folder for all generated files.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
