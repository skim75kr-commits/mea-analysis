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


class ScientificPalette:
    """
    Professional color palette for scientific publications
    Colorblind-friendly and journal-ready (Nature, Cell, Science style)
    """

    # Paul Tol's colorblind-friendly palette
    QUALITATIVE = {
        'blue': '#0173B2',
        'orange': '#DE8F05',
        'green': '#029E73',
        'red': '#CC78BC',
        'cyan': '#56B4E9',
        'magenta': '#CA9161',
        'purple': '#949494',
        'yellow': '#ECE133'
    }

    # Sequential colors for heatmaps (colorblind-friendly)
    SEQUENTIAL = 'viridis'  # or 'cividis', 'plasma'

    # Diverging colors
    DIVERGING = 'RdYlBu_r'

    # Specific use colors
    MEAN_LINE = '#0173B2'  # Blue
    ERROR_BAR = '#0173B2'
    SCATTER_POINTS = '#949494'  # Gray
    GRID = '#CCCCCC'

    @classmethod
    def get_color_cycle(cls, n_colors: int) -> List[str]:
        """Get a list of n colors from the qualitative palette"""
        colors = list(cls.QUALITATIVE.values())
        if n_colors <= len(colors):
            return colors[:n_colors]
        # Repeat colors if needed
        return (colors * ((n_colors // len(colors)) + 1))[:n_colors]


def setup_scientific_style():
    """
    Configure matplotlib for professional scientific publications
    Following Nature/Cell/Science submission guidelines
    """
    # Font settings
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
    plt.rcParams['font.size'] = 9

    # Figure settings
    plt.rcParams['figure.figsize'] = (7, 5)  # Nature single column: 89mm, double: 183mm
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['savefig.dpi'] = 300
    plt.rcParams['savefig.bbox'] = 'tight'
    plt.rcParams['savefig.transparent'] = False

    # Axes settings
    plt.rcParams['axes.linewidth'] = 0.8
    plt.rcParams['axes.labelsize'] = 10
    plt.rcParams['axes.titlesize'] = 11
    plt.rcParams['axes.labelweight'] = 'bold'
    plt.rcParams['axes.titleweight'] = 'bold'
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.spines.right'] = False
    plt.rcParams['axes.grid'] = True
    plt.rcParams['axes.axisbelow'] = True

    # Grid settings
    plt.rcParams['grid.alpha'] = 0.3
    plt.rcParams['grid.linewidth'] = 0.5
    plt.rcParams['grid.color'] = ScientificPalette.GRID

    # Legend settings
    plt.rcParams['legend.fontsize'] = 8
    plt.rcParams['legend.frameon'] = False
    plt.rcParams['legend.loc'] = 'best'

    # Tick settings
    plt.rcParams['xtick.labelsize'] = 9
    plt.rcParams['ytick.labelsize'] = 9
    plt.rcParams['xtick.major.width'] = 0.8
    plt.rcParams['ytick.major.width'] = 0.8
    plt.rcParams['xtick.major.size'] = 3.5
    plt.rcParams['ytick.major.size'] = 3.5

    # Line settings
    plt.rcParams['lines.linewidth'] = 1.5
    plt.rcParams['lines.markersize'] = 6

    # Error bar settings
    plt.rcParams['errorbar.capsize'] = 3

    # Set seaborn style
    sns.set_style("ticks", {
        'axes.grid': True,
        'axes.edgecolor': '0.2',
        'grid.color': ScientificPalette.GRID,
        'grid.linestyle': '-'
    })
    sns.set_palette(list(ScientificPalette.QUALITATIVE.values()))


# Constants for visualization settings
class PlotSettings:
    """Centralized plot settings and constants"""
    # Phase colors
    PHASE_COLORS = {
        'early': '#E8F4F8',
        'mid': '#FFF4E6',
        'late': '#F0F8E8'
    }

    # Phase boundaries (in days)
    EARLY_PHASE_END = 7
    MID_PHASE_END = 14

    # Plot styling
    PHASE_ALPHA = 0.15
    PHASE_LABEL_Y_POS = 0.98
    PHASE_LABEL_FONTSIZE = 7

    TREND_LINE_WIDTH = 2
    TREND_LINE_ALPHA = 0.7

    ZERO_LINE_WIDTH = 1.5
    ZERO_LINE_ALPHA = 0.6

    STATS_BOX_FONTSIZE = 8
    STATS_BOX_ALPHA = 0.5

    ERRORBAR_LINEWIDTH = 2
    ERRORBAR_MARKERSIZE = 7
    ERRORBAR_CAPSIZE = 4
    ERRORBAR_CAPTHICK = 1.5

    # Axis settings
    Y_MARGIN = 0.15
    GRID_ALPHA = 0.3
    GRID_LINEWIDTH = 0.5


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
            'linewidth': PlotSettings.ERRORBAR_LINEWIDTH,
            'markersize': PlotSettings.ERRORBAR_MARKERSIZE,
            'color': color,
            'ecolor': color,
            'capsize': PlotSettings.ERRORBAR_CAPSIZE,
            'capthick': PlotSettings.ERRORBAR_CAPTHICK,
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
    def add_differentiation_phases(ax: plt.Axes, x_min: float, x_max: float, phase_type: str = 'day'):
        """
        Add visual background shading for differentiation phases

        Parameters:
        -----------
        ax : plt.Axes
            Axis to add phases to
        x_min : float
            Minimum x value (day or week number)
        x_max : float
            Maximum x value (day or week number)
        phase_type : str
            Type of x-axis ('day' or 'week')
        """
        # Get phase definitions based on actual data range
        if phase_type == 'day':
            phases = BaseLightResponseVisualizer._get_day_phases(x_min, x_max)
        else:  # week
            phases = BaseLightResponseVisualizer._get_week_phases(x_min, x_max)

        # Add shaded regions and labels
        x_range = ax.get_xlim()
        x_range_width = x_range[1] - x_range[0]

        for start, end, label, color in phases:
            # Add background shading
            ax.axvspan(start, end, alpha=PlotSettings.PHASE_ALPHA, color=color, zorder=0)

            # Calculate x position as fraction for consistent placement
            mid_x = (start + end) / 2
            x_frac = (mid_x - x_range[0]) / x_range_width if x_range_width > 0 else 0.5

            # Add phase label
            ax.text(x_frac, PlotSettings.PHASE_LABEL_Y_POS, label,
                   transform=ax.transAxes,
                   ha='center', va='top',
                   fontsize=PlotSettings.PHASE_LABEL_FONTSIZE,
                   style='italic', color='gray',
                   alpha=0.8, weight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                            edgecolor='none', alpha=0.7))

    @staticmethod
    def _get_day_phases(x_min: float, x_max: float) -> List[Tuple[float, float, str, str]]:
        """Get phase definitions for daily view based on data range"""
        colors = PlotSettings.PHASE_COLORS
        phases = []

        # Determine which phases to show based on data range
        # Early phase: 0-7 days
        if x_min < PlotSettings.EARLY_PHASE_END:
            phase_start = max(x_min, 0)
            phase_end = min(x_max, PlotSettings.EARLY_PHASE_END)
            if phase_end > phase_start:
                phases.append((phase_start, phase_end, 'Early', colors['early']))

        # Mid phase: 7-14 days
        if x_max > PlotSettings.EARLY_PHASE_END and x_min < PlotSettings.MID_PHASE_END:
            phase_start = max(x_min, PlotSettings.EARLY_PHASE_END)
            phase_end = min(x_max, PlotSettings.MID_PHASE_END)
            if phase_end > phase_start:
                phases.append((phase_start, phase_end, 'Mid', colors['mid']))

        # Late phase: 14+ days
        if x_max > PlotSettings.MID_PHASE_END:
            phase_start = max(x_min, PlotSettings.MID_PHASE_END)
            phase_end = x_max
            if phase_end > phase_start:
                phases.append((phase_start, phase_end, 'Late', colors['late']))

        # If no specific phases, just create a single phase
        if not phases:
            phases.append((x_min, x_max, 'Data Range', colors['early']))

        return phases

    @staticmethod
    def _get_week_phases(x_min: float, x_max: float) -> List[Tuple[float, float, str, str]]:
        """Get phase definitions for weekly view based on data range"""
        colors = PlotSettings.PHASE_COLORS
        mid_point = (x_min + x_max) / 2

        return [
            (x_min, mid_point, 'Early', colors['early']),
            (mid_point, x_max, 'Late', colors['mid'])
        ]

    @staticmethod
    def optimize_x_limits(ax: plt.Axes, x_data: np.ndarray, margin: float = 0.05):
        """
        Optimize X-axis limits based on data range

        Parameters:
        -----------
        ax : plt.Axes
            Axis to optimize
        x_data : np.ndarray
            X data values
        margin : float
            Margin as fraction of data range (default 5%)
        """
        # Remove NaN values
        x_clean = x_data[~np.isnan(x_data)]

        if len(x_clean) == 0:
            return

        x_min, x_max = x_clean.min(), x_clean.max()
        x_range = x_max - x_min

        # Add margin
        if x_range > 0:
            ax.set_xlim(x_min - margin * x_range, x_max + margin * x_range)
        else:
            # If all values are the same, add fixed margin
            ax.set_xlim(x_min - 1, x_max + 1)

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
            Dictionary containing slope, r_squared, and p_value (None if scipy not available)
        """
        try:
            from scipy import stats
            scipy_available = True
        except ImportError:
            scipy_available = False

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
        ax.plot(x_smooth, y_smooth, '--', color=color,
               linewidth=PlotSettings.TREND_LINE_WIDTH,
               alpha=PlotSettings.TREND_LINE_ALPHA,
               label=label, zorder=3)

        # Calculate statistics for linear fit (only if scipy is available)
        if degree == 1 and scipy_available:
            slope, intercept, r_value, p_value, std_err = stats.linregress(x_clean, y_clean)
            return {
                'slope': slope,
                'r_squared': r_value**2,
                'p_value': p_value
            }
        elif degree == 1:
            # Basic statistics without scipy
            # Calculate slope manually for linear regression
            x_mean = np.mean(x_clean)
            y_mean = np.mean(y_clean)
            slope = np.sum((x_clean - x_mean) * (y_clean - y_mean)) / np.sum((x_clean - x_mean)**2)

            # Calculate R-squared
            y_pred = coeffs[0] * x_clean + coeffs[1]
            ss_res = np.sum((y_clean - y_pred)**2)
            ss_tot = np.sum((y_clean - y_mean)**2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            return {
                'slope': slope,
                'r_squared': r_squared,
                'p_value': None  # p-value requires scipy
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
        p_val = stats_dict.get('p_value', None)

        # Build text with available statistics
        text = f'Slope: {slope:.3e}\n$R^2$: {r_sq:.3f}'

        # Add p-value if available (requires scipy)
        if p_val is not None:
            # Determine significance
            if p_val < 0.001:
                sig = '***'
            elif p_val < 0.01:
                sig = '**'
            elif p_val < 0.05:
                sig = '*'
            else:
                sig = 'ns'
            text += f'\np: {p_val:.3e} {sig}'

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
               fontsize=PlotSettings.STATS_BOX_FONTSIZE,
               verticalalignment=va, horizontalalignment=ha,
               bbox=dict(boxstyle='round', facecolor='wheat',
                        alpha=PlotSettings.STATS_BOX_ALPHA),
               zorder=10)

    @staticmethod
    def optimize_y_limits(ax: plt.Axes, y_data: np.ndarray,
                         margin: float = None):
        """
        Optimize Y-axis limits based on data range

        Parameters:
        -----------
        ax : plt.Axes
            Axis to optimize
        y_data : np.ndarray
            Y data values
        margin : float, optional
            Margin as fraction of data range. If None, uses PlotSettings.Y_MARGIN
        """
        if margin is None:
            margin = PlotSettings.Y_MARGIN

        # Remove NaN values efficiently
        y_clean = y_data[~np.isnan(y_data)]

        if len(y_clean) == 0:
            return

        y_min, y_max = y_clean.min(), y_clean.max()
        y_range = y_max - y_min

        # Add margin
        if y_range > 0:
            ax.set_ylim(y_min - margin * y_range, y_max + margin * y_range)
        else:
            # If all values are the same, add fixed margin
            ax.set_ylim(y_min - 1, y_max + 1)

    @staticmethod
    def add_zero_line(ax: plt.Axes):
        """
        Add a zero reference line to the plot

        Parameters:
        -----------
        ax : plt.Axes
            Axis to add zero line to
        """
        ax.axhline(y=0, color='gray', linestyle='--',
                  linewidth=PlotSettings.ZERO_LINE_WIDTH,
                  alpha=PlotSettings.ZERO_LINE_ALPHA,
                  zorder=1, label='Zero Line')

    @staticmethod
    def calculate_grouped_statistics(data: pd.DataFrame, group_col: str,
                                     value_col: str) -> pd.DataFrame:
        """
        Calculate statistics (mean, std, count, se) for grouped data

        Parameters:
        -----------
        data : pd.DataFrame
            Input dataframe
        group_col : str
            Column to group by
        value_col : str
            Column to calculate statistics on

        Returns:
        --------
        pd.DataFrame
            Dataframe with mean, std, count, se columns
        """
        grouped = data.groupby(group_col)[value_col].agg(['mean', 'std', 'count']).reset_index()
        grouped['se'] = grouped['std'] / np.sqrt(grouped['count'])
        return grouped
