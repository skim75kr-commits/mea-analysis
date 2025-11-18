"""
Daily Light Response Metrics Visualization
Professional scientific styling with Baseline vs Stim comparison
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


class LightResponseVisualizer(BaseLightResponseVisualizer):
    """
    Visualizer for daily light response metrics analysis
    Inherits common functionality from BaseLightResponseVisualizer
    """

    def __init__(self, data_dir: str = 'Data_LightResponse'):
        """
        Initialize the daily light response visualizer

        Parameters:
        -----------
        data_dir : str
            Directory containing Excel files
        """
        super().__init__(data_dir)

    def plot_baseline_stim_comparison(
        self,
        metric_name: str,
        light_code: str,
        ax: Optional[plt.Axes] = None,
        show_individual_points: bool = True
    ) -> Optional[plt.Axes]:
        """
        Plot baseline vs stim comparison for a single metric and light code

        Parameters:
        -----------
        metric_name : str
            Name of the metric to plot
        light_code : str
            Light code (e.g., 'BL', 'GR')
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

        # Filter data for this metric and light code
        mask = (self.df['Metric'] == metric_name) & (self.df['Light_Code'] == light_code)
        metric_data = self.df[mask].copy()

        if len(metric_data) == 0:
            ax.text(0.5, 0.5, f'No data available\n{metric_name}\n{self.get_light_code_label(light_code)}',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            return ax

        # Sort by DIFF_DAY
        metric_data = metric_data.sort_values('DIFF_DAY')

        # Group by DIFF_DAY and calculate statistics for baseline and stim
        grouped_baseline = metric_data.groupby('DIFF_DAY')['Baseline'].agg(['mean', 'std', 'count']).reset_index()
        grouped_stim = metric_data.groupby('DIFF_DAY')['Stim'].agg(['mean', 'std', 'count']).reset_index()

        # Calculate standard error
        grouped_baseline['se'] = grouped_baseline['std'] / np.sqrt(grouped_baseline['count'])
        grouped_stim['se'] = grouped_stim['std'] / np.sqrt(grouped_stim['count'])

        # Colors for baseline and stim
        color_baseline = self.palette.QUALITATIVE['blue']
        color_stim = self.palette.QUALITATIVE['orange']

        # Plot individual points first (if enabled)
        # More efficient for large datasets: adjust alpha instead of hiding points
        if show_individual_points:
            point_alpha = 0.25 if len(metric_data) < 500 else 0.15
            ax.scatter(
                metric_data['DIFF_DAY'] - 0.5,
                metric_data['Baseline'],
                alpha=point_alpha,
                s=20,
                color=color_baseline,
                zorder=1
            )
            ax.scatter(
                metric_data['DIFF_DAY'] + 0.5,
                metric_data['Stim'],
                alpha=point_alpha,
                s=20,
                color=color_stim,
                zorder=1
            )

        # Plot baseline and stim mean lines with error bars
        baseline_kwargs = self._setup_errorbar_kwargs(color_baseline, 'Baseline', marker='o')
        stim_kwargs = self._setup_errorbar_kwargs(color_stim, 'Stim', marker='s')

        ax.errorbar(grouped_baseline['DIFF_DAY'], grouped_baseline['mean'],
                   yerr=grouped_baseline['se'], **baseline_kwargs)
        ax.errorbar(grouped_stim['DIFF_DAY'], grouped_stim['mean'],
                   yerr=grouped_stim['se'], **stim_kwargs)

        # Formatting
        ax.set_xlabel('Differentiation Day (days)', fontsize=10, fontweight='bold')
        ax.set_ylabel('Value', fontsize=10, fontweight='bold')

        title = f'{self.format_metric_name(metric_name)}\n{self.get_light_code_label(light_code)}'
        ax.set_title(title, fontsize=11, fontweight='bold', pad=10)

        # Legend
        ax.legend(loc='best', frameon=True, fancybox=False, shadow=False, framealpha=0.9)

        # Grid
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)

        return ax

    def plot_response_over_time(
        self,
        metric_name: str,
        light_code: str,
        ax: Optional[plt.Axes] = None,
        show_individual_points: bool = True
    ) -> Optional[plt.Axes]:
        """
        Plot response (Stim - Baseline) over time

        Parameters:
        -----------
        metric_name : str
            Name of the metric to plot
        light_code : str
            Light code (e.g., 'BL', 'GR')
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

        # Filter data for this metric and light code
        mask = (self.df['Metric'] == metric_name) & (self.df['Light_Code'] == light_code)
        metric_data = self.df[mask].copy()

        if len(metric_data) == 0:
            ax.text(0.5, 0.5, f'No data available\n{metric_name}\n{self.get_light_code_label(light_code)}',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            return ax

        # Sort by DIFF_DAY
        metric_data = metric_data.sort_values('DIFF_DAY')

        # Group by DIFF_DAY and calculate statistics for response
        grouped = metric_data.groupby('DIFF_DAY')['Response'].agg(['mean', 'std', 'count']).reset_index()
        grouped['se'] = grouped['std'] / np.sqrt(grouped['count'])

        # Plot individual points first (if enabled)
        # More efficient for large datasets: adjust alpha instead of hiding points
        if show_individual_points:
            point_alpha = 0.25 if len(metric_data) < 500 else 0.12
            ax.scatter(
                metric_data['DIFF_DAY'],
                metric_data['Response'],
                alpha=point_alpha,
                s=20,
                color=self.palette.SCATTER_POINTS,
                label='Individual wells' if point_alpha > 0.2 else None,
                zorder=1
            )

        # Plot response mean line with error bars
        response_kwargs = self._setup_errorbar_kwargs(
            self.palette.QUALITATIVE['green'],
            'Response (Stim - Baseline)',
            marker='o'
        )
        ax.errorbar(grouped['DIFF_DAY'], grouped['mean'], yerr=grouped['se'], **response_kwargs)

        # Add zero reference line
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.5, zorder=0)

        # Formatting
        ax.set_xlabel('Differentiation Day (days)', fontsize=10, fontweight='bold')
        ax.set_ylabel('Response (Stim - Baseline)', fontsize=10, fontweight='bold')

        title = f'{self.format_metric_name(metric_name)} Response\n{self.get_light_code_label(light_code)}'
        ax.set_title(title, fontsize=11, fontweight='bold', pad=10)

        # Legend
        ax.legend(loc='best', frameon=True, fancybox=False, shadow=False, framealpha=0.9)

        # Grid
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)

        return ax

    def plot_category_by_light(
        self,
        category_name: str,
        metrics_list: list,
        light_code: str,
        save_path: Optional[Path] = None,
        comparison_type: str = 'baseline_stim'
    ) -> Optional[plt.Figure]:
        """
        Plot all metrics in a category for a specific light code

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
        # Filter metrics that exist in the data for this light code
        mask = self.df['Light_Code'] == light_code
        available_metrics = [m for m in metrics_list if m in self.df[mask]['Metric'].values]

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
                self.plot_baseline_stim_comparison(metric, light_code, ax=axes[idx], show_individual_points=True)
            elif comparison_type == 'response':
                self.plot_response_over_time(metric, light_code, ax=axes[idx], show_individual_points=True)

        # Hide unused subplots
        for idx in range(n_metrics, len(axes)):
            axes[idx].set_visible(False)

        # Super title
        comparison_label = 'Baseline vs Stim' if comparison_type == 'baseline_stim' else 'Response'
        fig.suptitle(
            f'{category_name} - {self.get_light_code_label(light_code)}\n{comparison_label}',
            fontsize=14,
            fontweight='bold',
            y=0.995
        )

        plt.tight_layout(rect=[0, 0, 1, 0.99])

        # Save if path provided
        if save_path:
            self.save_figure(fig, save_path, close=False)

        return fig

    def plot_all_categories(self, output_dir: str = 'light_response_visualizations') -> None:
        """
        Create plots for all metric categories and light codes

        Parameters:
        -----------
        output_dir : str
            Directory to save visualization files
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)

        categories = self.get_metric_categories()
        light_codes = sorted(self.df['Light_Code'].unique())

        print(f"\n[INFO] Generating light response visualizations...")
        print(f"       Output directory: {output_path.absolute()}\n")

        # Generate both baseline_stim and response plots for each category and light code
        for light_code in light_codes:
            print(f"\n  Light Code: {self.get_light_code_label(light_code)}")

            for category_name, metrics_list in categories.items():
                # Baseline vs Stim comparison
                print(f"    - {category_name} (Baseline vs Stim)...")
                save_file = output_path / f"{category_name.replace(' ', '_').lower()}_{light_code}_baseline_stim.png"
                fig = self.plot_category_by_light(
                    category_name, metrics_list, light_code,
                    save_path=save_file, comparison_type='baseline_stim'
                )
                if fig:
                    plt.close(fig)

                # Response over time
                print(f"    - {category_name} (Response)...")
                save_file = output_path / f"{category_name.replace(' ', '_').lower()}_{light_code}_response.png"
                fig = self.plot_category_by_light(
                    category_name, metrics_list, light_code,
                    save_path=save_file, comparison_type='response'
                )
                if fig:
                    plt.close(fig)

        print(f"\n[OK] All visualizations saved")

    def create_summary_heatmap(
        self,
        save_path: Optional[Path] = None,
        value_type: str = 'response'
    ) -> plt.Figure:
        """
        Create a heatmap showing all metrics over time

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
        light_codes = sorted(self.df['Light_Code'].unique())
        n_lights = len(light_codes)

        # Create subplots for each light code
        fig, axes = plt.subplots(1, n_lights, figsize=(10 * n_lights, 10))

        if n_lights == 1:
            axes = [axes]

        for idx, light_code in enumerate(light_codes):
            ax = axes[idx]

            # Filter data for this light code
            light_data = self.df[self.df['Light_Code'] == light_code].copy()

            # Select value column
            value_col = {'baseline': 'Baseline', 'stim': 'Stim',
                        'response': 'Response', 'pct_change': 'Pct_Change'}[value_type]

            # Create pivot table: Metric vs DIFF_DAY
            pivot_data = light_data.pivot_table(
                values=value_col,
                index='Metric',
                columns='DIFF_DAY',
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

            # Format x-axis labels (days)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right', fontsize=8)

            ax.set_xlabel('Differentiation Day', fontsize=11, fontweight='bold')
            ax.set_ylabel('Metric', fontsize=11, fontweight='bold')
            ax.set_title(
                f'{self.get_light_code_label(light_code)}\n{value_type.capitalize()}',
                fontsize=13,
                fontweight='bold',
                pad=15
            )

        plt.tight_layout()

        if save_path:
            self.save_figure(fig, save_path, close=False)

        return fig

    def generate_summary_stats(
        self,
        save_path: str = 'light_response_summary_statistics.csv'
    ) -> pd.DataFrame:
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
        summary_list = []

        for light_code in sorted(self.df['Light_Code'].unique()):
            light_data = self.df[self.df['Light_Code'] == light_code].copy()

            for metric in light_data['Metric'].unique():
                metric_data = light_data[light_data['Metric'] == metric].copy()

                for diff_day in sorted(metric_data['DIFF_DAY'].unique()):
                    day_data = metric_data[metric_data['DIFF_DAY'] == diff_day].copy()

                    summary_list.append({
                        'Light_Code': light_code,
                        'Metric': metric,
                        'DIFF_DAY': diff_day,
                        'Baseline_Mean': day_data['Baseline'].mean(),
                        'Baseline_Std': day_data['Baseline'].std(),
                        'Stim_Mean': day_data['Stim'].mean(),
                        'Stim_Std': day_data['Stim'].std(),
                        'Response_Mean': day_data['Response'].mean(),
                        'Response_Std': day_data['Response'].std(),
                        'Pct_Change_Mean': day_data['Pct_Change'].mean(),
                        'N_Samples': len(day_data)
                    })

        summary = pd.DataFrame(summary_list)

        # Calculate standard error
        summary['Baseline_SE'] = summary['Baseline_Std'] / np.sqrt(summary['N_Samples'])
        summary['Stim_SE'] = summary['Stim_Std'] / np.sqrt(summary['N_Samples'])
        summary['Response_SE'] = summary['Response_Std'] / np.sqrt(summary['N_Samples'])

        # Save to CSV
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(save_path, index=False)

        print(f"\n[OK] Summary statistics saved: {save_path}")
        print(f"    Total records: {len(summary):,}")

        return summary


def main():
    """Main execution function for daily light response analysis"""
    print("=" * 80)
    print("MEA Light Response Metrics - Daily Analysis".center(80))
    print("=" * 80)

    try:
        # Initialize visualizer
        visualizer = LightResponseVisualizer(data_dir='Data_LightResponse')

        # Load data
        print("\n[Step 1/4] Loading data...")
        visualizer.load_data()

        # Generate all category plots
        print("\n[Step 2/4] Generating category-wise visualizations...")
        visualizer.plot_all_categories(output_dir='light_response_visualizations')

        # Create summary heatmaps
        print("\n[Step 3/4] Creating summary heatmaps...")
        visualizer.create_summary_heatmap(
            save_path='light_response_visualizations/summary_heatmap_response.png',
            value_type='response'
        )
        visualizer.create_summary_heatmap(
            save_path='light_response_visualizations/summary_heatmap_baseline.png',
            value_type='baseline'
        )
        plt.close('all')

        # Generate summary statistics
        print("\n[Step 4/4] Generating summary statistics...")
        visualizer.generate_summary_stats(
            save_path='light_response_visualizations/light_response_summary_statistics.csv'
        )

        print("\n" + "=" * 80)
        print("[OK] Daily Light Response Analysis Complete!".center(80))
        print("=" * 80)
        print("\nCheck the 'light_response_visualizations/' folder for all generated files.")

    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
