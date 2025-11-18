"""
Weekly Light Response Metrics Visualization
Groups data by weeks for trend analysis with Baseline vs Stim comparison
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
from typing import Optional
import warnings
warnings.filterwarnings('ignore')

from visualize_light_response_base import BaseLightResponseVisualizer, ScientificPalette


class WeeklyLightResponseVisualizer(BaseLightResponseVisualizer):
    """
    Visualizer for weekly light response metrics analysis
    Inherits common functionality from BaseLightResponseVisualizer
    """

    def __init__(self, data_dir: str = 'Data_LightResponse', week_size: int = 7):
        """
        Initialize the weekly light response visualizer

        Parameters:
        -----------
        data_dir : str
            Directory containing Excel files
        week_size : int
            Number of days per week grouping
        """
        super().__init__(data_dir)
        self.week_size = week_size
        self.weekly_df: Optional[pd.DataFrame] = None

    def create_weekly_groups(self) -> pd.DataFrame:
        """
        Create weekly aggregated dataframe from daily data

        Returns:
        --------
        pd.DataFrame
            Weekly aggregated dataframe
        """
        if self.df is None:
            raise ValueError("Data not loaded. Call load_data() first.")

        # Create week column as a temporary calculation without modifying original df
        temp_df = self.df.copy()
        temp_df['Week'] = (temp_df['DIFF_DAY'] // self.week_size) + 1

        # Use efficient pandas groupby aggregation instead of nested loops
        agg_funcs = {
            'Baseline': ['mean', 'std', 'count'],
            'Stim': ['mean', 'std', 'count'],
            'Response': ['mean', 'std', 'count'],
            'Pct_Change': 'mean',
            'DIFF_DAY': ['min', 'max']
        }

        # Group by Week, Light_Code, and Metric
        grouped = temp_df.groupby(['Week', 'Light_Code', 'Metric']).agg(agg_funcs).reset_index()

        # Flatten column names
        grouped.columns = ['_'.join(col).strip('_') for col in grouped.columns.values]

        # Rename columns for clarity
        rename_dict = {
            'Baseline_mean': 'Baseline_Mean',
            'Baseline_std': 'Baseline_Std',
            'Baseline_count': 'Baseline_Count',
            'Stim_mean': 'Stim_Mean',
            'Stim_std': 'Stim_Std',
            'Stim_count': 'Stim_Count',
            'Response_mean': 'Response_Mean',
            'Response_std': 'Response_Std',
            'Response_count': 'Response_Count',
            'Pct_Change_mean': 'Pct_Change_Mean',
            'DIFF_DAY_min': 'Min_Day',
            'DIFF_DAY_max': 'Max_Day'
        }
        grouped.rename(columns=rename_dict, inplace=True)

        # Calculate standard errors (vectorized operation)
        grouped['Baseline_SE'] = grouped['Baseline_Std'] / np.sqrt(grouped['Baseline_Count'])
        grouped['Stim_SE'] = grouped['Stim_Std'] / np.sqrt(grouped['Stim_Count'])
        grouped['Response_SE'] = grouped['Response_Std'] / np.sqrt(grouped['Response_Count'])

        self.weekly_df = grouped

        print(f"\n[OK] Weekly groups created:")
        print(f"    - Week size: {self.week_size} days")
        print(f"    - Total weeks: {self.weekly_df['Week'].max():.0f}")
        print(f"    - Records: {len(self.weekly_df):,}")

        return self.weekly_df

    def plot_weekly_baseline_stim_comparison(
        self,
        metric_name: str,
        light_code: str,
        ax: Optional[plt.Axes] = None
    ) -> Optional[plt.Axes]:
        """
        Plot weekly baseline vs stim comparison for a single metric and light code

        Parameters:
        -----------
        metric_name : str
            Name of the metric to plot
        light_code : str
            Light code (e.g., 'BL', 'GR')
        ax : matplotlib.axes.Axes, optional
            Axis to plot on (if None, creates new figure)

        Returns:
        --------
        matplotlib.axes.Axes
            The axis object
        """
        if self.weekly_df is None:
            raise ValueError("Weekly data not created. Call create_weekly_groups() first.")

        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 5))

        # Filter data for this metric and light code
        mask = (self.weekly_df['Metric'] == metric_name) & (self.weekly_df['Light_Code'] == light_code)
        metric_data = self.weekly_df[mask].copy()

        if len(metric_data) == 0:
            ax.text(0.5, 0.5, f'No data available\n{metric_name}\n{self.get_light_code_label(light_code)}',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            return ax

        # Sort by Week
        metric_data = metric_data.sort_values('Week')

        # Colors for baseline and stim
        color_baseline = self.palette.QUALITATIVE['blue']
        color_stim = self.palette.QUALITATIVE['orange']

        # Setup error bar configurations with adjusted markersize for weekly view
        baseline_kwargs = self._setup_errorbar_kwargs(color_baseline, 'Baseline', marker='o')
        baseline_kwargs['markersize'] = 8
        baseline_kwargs['capsize'] = 5

        stim_kwargs = self._setup_errorbar_kwargs(color_stim, 'Stim', marker='s')
        stim_kwargs['markersize'] = 8
        stim_kwargs['capsize'] = 5

        # Plot baseline and stim mean lines with error bars
        ax.errorbar(metric_data['Week'], metric_data['Baseline_Mean'],
                   yerr=metric_data['Baseline_SE'], **baseline_kwargs)
        ax.errorbar(metric_data['Week'], metric_data['Stim_Mean'],
                   yerr=metric_data['Stim_SE'], **stim_kwargs)

        # Add trend lines with statistics
        baseline_stats = self.add_trend_line(
            ax, metric_data['Week'].values, metric_data['Baseline_Mean'].values,
            color=color_baseline, label='Baseline Trend'
        )
        stim_stats = self.add_trend_line(
            ax, metric_data['Week'].values, metric_data['Stim_Mean'].values,
            color=color_stim, label='Stim Trend'
        )

        # Optimize Y-axis limits after plotting
        all_y_data = np.concatenate([metric_data['Baseline_Mean'].values, metric_data['Stim_Mean'].values])
        self.optimize_y_limits(ax, all_y_data)

        # Add differentiation phases (after Y-axis is set)
        x_max = metric_data['Week'].max()
        self.add_differentiation_phases(ax, x_max, phase_type='week')

        # Add statistics annotations
        if baseline_stats:
            self.add_statistics_annotation(ax, baseline_stats, position='top_left')
        if stim_stats:
            self.add_statistics_annotation(ax, stim_stats, position='top_right')

        # Formatting
        ax.set_xlabel(f'Week (each = {self.week_size} days)', fontsize=10, fontweight='bold')
        ax.set_ylabel('Value', fontsize=10, fontweight='bold')

        title = f'{self.format_metric_name(metric_name)}\n{self.get_light_code_label(light_code)}'
        ax.set_title(title, fontsize=11, fontweight='bold', pad=10)

        # Legend
        legend_loc = 'lower right' if (baseline_stats or stim_stats) else 'best'
        ax.legend(loc=legend_loc, frameon=True, fancybox=False, shadow=False, framealpha=0.9, fontsize=8)

        # Grid
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)

        # Set integer ticks for weeks
        ax.set_xticks(metric_data['Week'].unique())

        return ax

    def plot_weekly_response(
        self,
        metric_name: str,
        light_code: str,
        ax: Optional[plt.Axes] = None
    ) -> Optional[plt.Axes]:
        """
        Plot weekly response (Stim - Baseline) over time

        Parameters:
        -----------
        metric_name : str
            Name of the metric to plot
        light_code : str
            Light code (e.g., 'BL', 'GR')
        ax : matplotlib.axes.Axes, optional
            Axis to plot on (if None, creates new figure)

        Returns:
        --------
        matplotlib.axes.Axes
            The axis object
        """
        if self.weekly_df is None:
            raise ValueError("Weekly data not created. Call create_weekly_groups() first.")

        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 5))

        # Filter data for this metric and light code
        mask = (self.weekly_df['Metric'] == metric_name) & (self.weekly_df['Light_Code'] == light_code)
        metric_data = self.weekly_df[mask].copy()

        if len(metric_data) == 0:
            ax.text(0.5, 0.5, f'No data available\n{metric_name}\n{self.get_light_code_label(light_code)}',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            return ax

        # Sort by Week
        metric_data = metric_data.sort_values('Week')

        # Add zero reference line using helper
        self.add_zero_line(ax)

        # Setup error bar configuration for response
        response_color = self.palette.QUALITATIVE['green']
        response_kwargs = self._setup_errorbar_kwargs(
            response_color,
            'Response (Stim - Baseline)',
            marker='o'
        )
        response_kwargs['markersize'] = 8
        response_kwargs['capsize'] = 5

        # Plot response mean line with error bars
        ax.errorbar(metric_data['Week'], metric_data['Response_Mean'],
                   yerr=metric_data['Response_SE'], **response_kwargs)

        # Add trend line with statistics
        response_stats = self.add_trend_line(
            ax, metric_data['Week'].values, metric_data['Response_Mean'].values,
            color='darkred', label='Response Trend'
        )

        # Optimize Y-axis limits after plotting
        self.optimize_y_limits(ax, metric_data['Response_Mean'].values)

        # Add differentiation phases (after Y-axis is set)
        x_max = metric_data['Week'].max()
        self.add_differentiation_phases(ax, x_max, phase_type='week')

        # Add statistics annotation
        if response_stats:
            # Position based on whether slope is positive or negative
            pos = 'top_right' if response_stats['slope'] > 0 else 'bottom_right'
            self.add_statistics_annotation(ax, response_stats, position=pos)

        # Formatting
        ax.set_xlabel(f'Week (each = {self.week_size} days)', fontsize=10, fontweight='bold')
        ax.set_ylabel('Response (Stim - Baseline)', fontsize=10, fontweight='bold')

        title = f'{self.format_metric_name(metric_name)} Response\n{self.get_light_code_label(light_code)}'
        ax.set_title(title, fontsize=11, fontweight='bold', pad=10)

        # Legend
        legend_loc = 'upper left' if response_stats and response_stats['slope'] > 0 else 'best'
        ax.legend(loc=legend_loc, frameon=True, fancybox=False, shadow=False, framealpha=0.9, fontsize=8)

        # Grid
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)

        # Set integer ticks for weeks
        ax.set_xticks(metric_data['Week'].unique())

        return ax

    def plot_category_weekly(
        self,
        category_name: str,
        metrics_list: list,
        light_code: str,
        save_path: Optional[Path] = None,
        comparison_type: str = 'baseline_stim'
    ) -> Optional[plt.Figure]:
        """
        Plot all metrics in a category for a specific light code (weekly)

        Parameters:
        -----------
        category_name : str
            Name of the category
        metrics_list : list
            List of metric names in this category
        light_code : str
            Light code to plot
        save_path : Path, optional
            Path to save the figure
        comparison_type : str
            Type of comparison: 'baseline_stim' or 'response'

        Returns:
        --------
        plt.Figure or None
            The figure object if metrics are available, None otherwise
        """
        if self.weekly_df is None:
            raise ValueError("Weekly data not created. Call create_weekly_groups() first.")

        # Filter metrics that exist in the data for this light code
        mask = self.weekly_df['Light_Code'] == light_code
        available_metrics = [m for m in metrics_list if m in self.weekly_df[mask]['Metric'].values]

        if not available_metrics:
            print(f"  WARNING: No data available for category: {category_name} ({self.get_light_code_label(light_code)})")
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
            if comparison_type == 'baseline_stim':
                self.plot_weekly_baseline_stim_comparison(metric, light_code, ax=axes[idx])
            elif comparison_type == 'response':
                self.plot_weekly_response(metric, light_code, ax=axes[idx])

        # Hide unused subplots
        for idx in range(n_metrics, len(axes)):
            axes[idx].set_visible(False)

        # Super title
        comparison_label = 'Baseline vs Stim' if comparison_type == 'baseline_stim' else 'Response'
        fig.suptitle(
            f'{category_name} - {self.get_light_code_label(light_code)}\nWeekly Analysis - {comparison_label}',
            fontsize=14,
            fontweight='bold',
            y=0.995
        )

        plt.tight_layout(rect=[0, 0, 1, 0.99])

        # Save if path provided
        if save_path:
            self.save_figure(fig, save_path, close=False)

        return fig

    def plot_all_categories_weekly(
        self,
        output_dir: str = 'light_response_weekly_visualizations'
    ) -> None:
        """
        Create weekly plots for all metric categories and light codes

        Parameters:
        -----------
        output_dir : str
            Directory to save visualization files
        """
        if self.weekly_df is None:
            raise ValueError("Weekly data not created. Call create_weekly_groups() first.")

        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)

        categories = self.get_metric_categories()
        light_codes = sorted(self.weekly_df['Light_Code'].unique())

        print(f"\n[INFO] Generating weekly light response visualizations...")
        print(f"       Output directory: {output_path.absolute()}\n")

        # Generate both baseline_stim and response plots for each category and light code
        for light_code in light_codes:
            print(f"\n  Light Code: {self.get_light_code_label(light_code)}")

            for category_name, metrics_list in categories.items():
                # Baseline vs Stim comparison
                print(f"    - {category_name} (Baseline vs Stim)...")
                save_file = output_path / f"{category_name.replace(' ', '_').lower()}_{light_code}_baseline_stim_weekly.png"
                fig = self.plot_category_weekly(
                    category_name, metrics_list, light_code,
                    save_path=save_file, comparison_type='baseline_stim'
                )
                if fig:
                    plt.close(fig)

                # Response over time
                print(f"    - {category_name} (Response)...")
                save_file = output_path / f"{category_name.replace(' ', '_').lower()}_{light_code}_response_weekly.png"
                fig = self.plot_category_weekly(
                    category_name, metrics_list, light_code,
                    save_path=save_file, comparison_type='response'
                )
                if fig:
                    plt.close(fig)

        print(f"\n[OK] All weekly visualizations saved")

    def create_weekly_heatmap(
        self,
        save_path: Optional[Path] = None,
        value_type: str = 'response'
    ) -> plt.Figure:
        """
        Create a heatmap showing all metrics over weeks

        Parameters:
        -----------
        save_path : Path, optional
            Path to save the figure
        value_type : str
            Type of value to plot: 'baseline', 'stim', 'response', or 'pct_change'

        Returns:
        --------
        plt.Figure
            The figure object
        """
        if self.weekly_df is None:
            raise ValueError("Weekly data not created. Call create_weekly_groups() first.")

        light_codes = sorted(self.weekly_df['Light_Code'].unique())
        n_lights = len(light_codes)

        # Create subplots for each light code
        fig, axes = plt.subplots(1, n_lights, figsize=(10 * n_lights, 10))

        if n_lights == 1:
            axes = [axes]

        value_col_map = {
            'baseline': 'Baseline_Mean',
            'stim': 'Stim_Mean',
            'response': 'Response_Mean',
            'pct_change': 'Pct_Change_Mean'
        }
        value_col = value_col_map[value_type]

        for idx, light_code in enumerate(light_codes):
            ax = axes[idx]

            # Filter data for this light code
            light_data = self.weekly_df[self.weekly_df['Light_Code'] == light_code].copy()

            # Create pivot table: Metric vs Week
            pivot_data = light_data.pivot_table(
                values=value_col,
                index='Metric',
                columns='Week',
                aggfunc='mean'
            )

            if value_type == 'response':
                # For response, use diverging colormap centered at 0
                vmax = max(abs(pivot_data.min().min()), abs(pivot_data.max().max()))
                vmin = -vmax
                cmap = 'RdBu_r'
            else:
                # Normalize each row (metric) to 0-1 scale for better visualization
                pivot_data = pivot_data.div(pivot_data.max(axis=1), axis=0)
                vmin, vmax = 0, 1
                cmap = self.palette.SEQUENTIAL

            # Create heatmap
            sns.heatmap(
                pivot_data,
                cmap=cmap,
                cbar_kws={
                    'label': f'{value_type.capitalize()} Value',
                    'shrink': 0.8,
                    'aspect': 30
                },
                ax=ax,
                linewidths=0.5,
                linecolor='white',
                square=False,
                vmin=vmin,
                vmax=vmax,
                center=0 if value_type == 'response' else None
            )

            # Format y-axis labels (metric names)
            y_labels = [self.format_metric_name(label.get_text()) for label in ax.get_yticklabels()]
            ax.set_yticklabels(y_labels, rotation=0, fontsize=8)

            # Format x-axis labels (weeks)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=0, fontsize=8)

            ax.set_xlabel(f'Week (each = {self.week_size} days)', fontsize=11, fontweight='bold')
            ax.set_ylabel('Metric', fontsize=11, fontweight='bold')
            ax.set_title(
                f'{self.get_light_code_label(light_code)}\n{value_type.capitalize()} - Weekly',
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
        save_path: str = 'light_response_weekly_summary_statistics.csv'
    ) -> pd.DataFrame:
        """
        Generate weekly summary statistics table

        Parameters:
        -----------
        save_path : str
            Path to save the summary CSV file

        Returns:
        --------
        pd.DataFrame
            Summary statistics dataframe
        """
        if self.weekly_df is None:
            raise ValueError("Weekly data not created. Call create_weekly_groups() first.")

        # Save to CSV
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        self.weekly_df.to_csv(save_path, index=False)

        print(f"\n[OK] Weekly summary statistics saved: {save_path}")
        print(f"    Total records: {len(self.weekly_df):,}")

        return self.weekly_df


def main():
    """Main execution function for weekly light response analysis"""
    print("=" * 80)
    print("MEA Light Response Metrics - Weekly Analysis".center(80))
    print("=" * 80)

    try:
        # Initialize visualizer
        visualizer = WeeklyLightResponseVisualizer(
            data_dir='Data_LightResponse',
            week_size=7
        )

        # Load data
        print("\n[Step 1/5] Loading data...")
        visualizer.load_data()

        # Create weekly groups
        print("\n[Step 2/5] Creating weekly groups...")
        visualizer.create_weekly_groups()

        # Generate all category plots
        print("\n[Step 3/5] Generating weekly category-wise visualizations...")
        visualizer.plot_all_categories_weekly(
            output_dir='light_response_weekly_visualizations'
        )

        # Create summary heatmaps
        print("\n[Step 4/5] Creating weekly summary heatmaps...")
        visualizer.create_weekly_heatmap(
            save_path='light_response_weekly_visualizations/weekly_heatmap_response.png',
            value_type='response'
        )
        visualizer.create_weekly_heatmap(
            save_path='light_response_weekly_visualizations/weekly_heatmap_baseline.png',
            value_type='baseline'
        )
        plt.close('all')

        # Generate summary statistics
        print("\n[Step 5/5] Generating weekly summary statistics...")
        visualizer.generate_weekly_summary_stats(
            save_path='light_response_weekly_visualizations/light_response_weekly_summary_statistics.csv'
        )

        print("\n" + "=" * 80)
        print("[OK] Weekly Light Response Analysis Complete!".center(80))
        print("=" * 80)
        print("\nCheck the 'light_response_weekly_visualizations/' folder for all generated files.")

    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
