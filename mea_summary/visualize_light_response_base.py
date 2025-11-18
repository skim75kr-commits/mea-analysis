"""
Base classes for MEA Light Response Metrics Visualization
Provides common functionality and professional scientific styling
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

# Import from existing base module for consistency
try:
    from visualize_metrics_base import ScientificPalette, setup_scientific_style
except ImportError:
    # Fallback for when visualize_metrics_base is not available
    from code_SpontaneousActivity.visualize_metrics_base import ScientificPalette, setup_scientific_style


class BaseLightResponseVisualizer:
    """
    Base class for light response visualization with common functionality
    """

    def __init__(self, data_dir: str = 'Data_LightResponse'):
        """
        Initialize the base visualizer

        Parameters:
        -----------
        data_dir : str
            Directory containing Excel files
        """
        self.data_dir = Path(data_dir)
        self.df: Optional[pd.DataFrame] = None
        self.palette = ScientificPalette()

        # Setup professional styling
        setup_scientific_style()

    def load_data(self, file_pattern: str = '*light_response_report.xlsx') -> pd.DataFrame:
        """
        Load all Excel files matching the pattern

        Parameters:
        -----------
        file_pattern : str
            Glob pattern for Excel files

        Returns:
        --------
        pd.DataFrame
            Combined dataframe
        """
        excel_files = list(self.data_dir.glob(file_pattern))

        # Filter out temporary files
        excel_files = [f for f in excel_files if not f.name.startswith('~$')]

        if not excel_files:
            raise FileNotFoundError(f"No Excel files found matching '{file_pattern}' in {self.data_dir}")

        print(f"Found {len(excel_files)} Excel file(s):")
        for f in excel_files:
            print(f"  - {f.name}")

        # Read and combine with error handling
        dfs = []
        for file in excel_files:
            try:
                df_temp = pd.read_excel(file, sheet_name='Overall')
                dfs.append(df_temp)
            except Exception as e:
                print(f"  WARNING: Failed to load {file.name}: {e}")

        if not dfs:
            raise ValueError("No valid Excel files could be loaded")

        self.df = pd.concat(dfs, ignore_index=True)

        # Validate required columns
        required_cols = ['DIFF_DAY', 'Metric', 'Baseline', 'Stim', 'Response', 'Light_Code']
        missing_cols = [col for col in required_cols if col not in self.df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        print(f"\n[OK] Total rows loaded: {len(self.df):,}")
        print(f"[OK] Unique metrics: {self.df['Metric'].nunique()}")
        print(f"[OK] Light codes: {sorted(self.df['Light_Code'].unique())}")
        print(f"[OK] DIFF_DAY range: {self.df['DIFF_DAY'].min():.0f} - {self.df['DIFF_DAY'].max():.0f}")

        return self.df

    @staticmethod
    def get_metric_categories() -> Dict[str, List[str]]:
        """
        Categorize metrics into groups

        Returns:
        --------
        Dict[str, List[str]]
            Dictionary mapping category names to lists of metric names
        """
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
            ]
        }
        return categories

    @staticmethod
    def get_light_code_label(code: str) -> str:
        """
        Get full label for light code

        Parameters:
        -----------
        code : str
            Light code (e.g., 'BL', 'GR')

        Returns:
        --------
        str
            Full label
        """
        labels = {
            'BL': 'Blue Light',
            'GR': 'Green Light',
            'RD': 'Red Light',
            'WH': 'White Light'
        }
        return labels.get(code, code)

    @staticmethod
    def calculate_subplot_layout(n_items: int, max_cols: int = 3) -> Tuple[int, int]:
        """
        Calculate optimal subplot layout

        Parameters:
        -----------
        n_items : int
            Number of subplots needed
        max_cols : int
            Maximum number of columns

        Returns:
        --------
        Tuple[int, int]
            (n_rows, n_cols)
        """
        n_cols = min(max_cols, n_items)
        n_rows = (n_items + n_cols - 1) // n_cols
        return n_rows, n_cols

    def format_metric_name(self, metric_name: str) -> str:
        """
        Format metric name for display

        Parameters:
        -----------
        metric_name : str
            Raw metric name

        Returns:
        --------
        str
            Formatted metric name
        """
        # Replace underscores with spaces and capitalize
        formatted = metric_name.replace('_', ' ').title()

        # Handle special cases
        replacements = {
            'Hz': 'Hz',
            'Avg': 'Average',
            'Std': 'Std Dev',
            'Isi': 'ISI',
            'Ibi': 'IBI',
            'Sec': 'sec',
            'S ': 's '
        }

        for old, new in replacements.items():
            formatted = formatted.replace(old, new)

        return formatted

    def save_figure(self, fig: plt.Figure, save_path: Path, close: bool = True):
        """
        Save figure with proper settings

        Parameters:
        -----------
        fig : plt.Figure
            Figure to save
        save_path : Path
            Path to save the figure
        close : bool
            Whether to close the figure after saving
        """
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        fig.savefig(save_path, dpi=300, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        print(f"  [OK] Saved: {save_path.name}")

        if close:
            plt.close(fig)

    @staticmethod
    def _setup_errorbar_kwargs(color: str, label: str, marker: str = 'o',
                               is_line: bool = True) -> Dict:
        """
        Setup consistent errorbar styling configuration

        Parameters:
        -----------
        color : str
            Color for the line and error bars
        label : str
            Label for the line
        marker : str
            Marker style ('o' for circle, 's' for square)
        is_line : bool
            Whether to draw connecting lines

        Returns:
        --------
        Dict
            Configuration dictionary for errorbar plotting
        """
        return {
            'marker': marker,
            'linestyle': '-' if is_line else 'none',
            'linewidth': 2,
            'markersize': 7,
            'color': color,
            'ecolor': color,
            'capsize': 4,
            'capthick': 1.5,
            'label': label,
            'alpha': 0.9,
            'zorder': 2
        }

    @staticmethod
    def _setup_scatter_kwargs(color: str, label: str = None) -> Dict:
        """
        Setup consistent scatter point styling

        Parameters:
        -----------
        color : str
            Color for scatter points
        label : str
            Label for the points

        Returns:
        --------
        Dict
            Configuration dictionary for scatter plotting
        """
        return {
            'alpha': 0.25,
            's': 25,
            'color': color,
            'label': label,
            'zorder': 1
        }

    @staticmethod
    def add_differentiation_phases(ax: plt.Axes, x_max: float, phase_type: str = 'day'):
        """
        Add visual background shading for differentiation phases

        Parameters:
        -----------
        ax : plt.Axes
            Axis to add phases to
        x_max : float
            Maximum x value (day or week number)
        phase_type : str
            Type of x-axis ('day' or 'week')
        """
        if phase_type == 'day':
            # Define phases based on differentiation days
            if x_max <= 20:
                phases = [
                    (0, 7, 'Early\nDifferentiation', '#E8F4F8'),
                    (7, x_max, 'Mid-Late\nDifferentiation', '#FFF4E6')
                ]
            else:
                phases = [
                    (0, 7, 'Early', '#E8F4F8'),
                    (7, 14, 'Mid', '#FFF4E6'),
                    (14, x_max, 'Late', '#F0F8E8')
                ]
        else:  # week
            # Simpler phases for weekly view
            mid_point = x_max / 2
            phases = [
                (0, mid_point, 'Early Phase', '#E8F4F8'),
                (mid_point, x_max, 'Late Phase', '#FFF4E6')
            ]

        # Add shaded regions
        for start, end, label, color in phases:
            ax.axvspan(start, end, alpha=0.15, color=color, zorder=0)
            # Add phase label at the top
            mid_x = (start + end) / 2
            y_pos = ax.get_ylim()[1]
            ax.text(mid_x, y_pos, label, ha='center', va='bottom',
                   fontsize=8, style='italic', color='gray', alpha=0.7)

    @staticmethod
    def add_trend_line(ax: plt.Axes, x_data: np.ndarray, y_data: np.ndarray,
                      color: str = 'red', label: str = 'Trend', degree: int = 1):
        """
        Add polynomial trend line with statistics

        Parameters:
        -----------
        ax : plt.Axes
            Axis to add trend line to
        x_data : np.ndarray
            X coordinates
        y_data : np.ndarray
            Y coordinates
        color : str
            Color for the trend line
        label : str
            Label for the trend line
        degree : int
            Degree of polynomial (1=linear, 2=quadratic)

        Returns:
        --------
        Dict
            Dictionary containing slope, r_squared, and p_value
        """
        from scipy import stats

        # Remove NaN values
        mask = ~(np.isnan(x_data) | np.isnan(y_data))
        x_clean = x_data[mask]
        y_clean = y_data[mask]

        if len(x_clean) < 2:
            return None

        # Fit polynomial
        coeffs = np.polyfit(x_clean, y_clean, degree)
        poly = np.poly1d(coeffs)

        # Generate smooth curve
        x_smooth = np.linspace(x_clean.min(), x_clean.max(), 100)
        y_smooth = poly(x_smooth)

        # Plot trend line
        ax.plot(x_smooth, y_smooth, '--', color=color, linewidth=2,
               alpha=0.7, label=label, zorder=3)

        # Calculate statistics for linear fit
        if degree == 1:
            slope, intercept, r_value, p_value, std_err = stats.linregress(x_clean, y_clean)
            return {
                'slope': slope,
                'r_squared': r_value**2,
                'p_value': p_value
            }
        return None

    @staticmethod
    def add_statistics_annotation(ax: plt.Axes, stats_dict: Dict, position: str = 'top_right'):
        """
        Add statistics annotation to plot

        Parameters:
        -----------
        ax : plt.Axes
            Axis to add annotation to
        stats_dict : Dict
            Dictionary with 'slope', 'r_squared', 'p_value'
        position : str
            Position for annotation ('top_right', 'top_left', 'bottom_right', 'bottom_left')
        """
        if stats_dict is None:
            return

        # Format statistics text
        slope = stats_dict.get('slope', 0)
        r_sq = stats_dict.get('r_squared', 0)
        p_val = stats_dict.get('p_value', 1)

        # Determine significance
        if p_val < 0.001:
            sig = '***'
        elif p_val < 0.01:
            sig = '**'
        elif p_val < 0.05:
            sig = '*'
        else:
            sig = 'ns'

        text = f'Slope: {slope:.3e}\n$R^2$: {r_sq:.3f}\np: {p_val:.3e} {sig}'

        # Position mapping
        pos_map = {
            'top_right': (0.95, 0.95, 'top', 'right'),
            'top_left': (0.05, 0.95, 'top', 'left'),
            'bottom_right': (0.95, 0.05, 'bottom', 'right'),
            'bottom_left': (0.05, 0.05, 'bottom', 'left')
        }

        x, y, va, ha = pos_map.get(position, pos_map['top_right'])

        # Add text box
        ax.text(x, y, text, transform=ax.transAxes,
               fontsize=8, verticalalignment=va, horizontalalignment=ha,
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
               zorder=10)

    @staticmethod
    def optimize_y_limits(ax: plt.Axes, y_data: np.ndarray, margin: float = 0.1):
        """
        Optimize Y-axis limits based on data range

        Parameters:
        -----------
        ax : plt.Axes
            Axis to optimize
        y_data : np.ndarray
            Y data values
        margin : float
            Margin as fraction of data range (0.1 = 10%)
        """
        # Remove NaN values
        y_clean = y_data[~np.isnan(y_data)]

        if len(y_clean) == 0:
            return

        y_min, y_max = y_clean.min(), y_clean.max()
        y_range = y_max - y_min

        # Add margin
        if y_range > 0:
            ax.set_ylim(y_min - margin * y_range, y_max + margin * y_range)
        else:
            # If all values are the same
            ax.set_ylim(y_min - 1, y_max + 1)
