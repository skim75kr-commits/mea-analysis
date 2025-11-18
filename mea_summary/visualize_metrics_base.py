"""
Base classes for MEA Spontaneous Activity Metrics Visualization
Provides common functionality and professional scientific styling
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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


class BaseMetricsVisualizer:
    """
    Base class for metrics visualization with common functionality
    """

    def __init__(self, data_dir: str = '.'):
        """
        Initialize the base visualizer

        Parameters:
        -----------
        data_dir : str
            Directory containing CSV files
        """
        self.data_dir = Path(data_dir)
        self.df: Optional[pd.DataFrame] = None
        self.palette = ScientificPalette()

        # Setup professional styling
        setup_scientific_style()

    def load_data(self, file_pattern: str = '*spontaneous_activity.csv') -> pd.DataFrame:
        """
        Load all CSV files matching the pattern

        Parameters:
        -----------
        file_pattern : str
            Glob pattern for CSV files

        Returns:
        --------
        pd.DataFrame
            Combined dataframe
        """
        csv_files = list(self.data_dir.glob(file_pattern))

        if not csv_files:
            raise FileNotFoundError(f"No CSV files found matching '{file_pattern}' in {self.data_dir}")

        print(f"Found {len(csv_files)} CSV file(s):")
        for f in csv_files:
            print(f"  • {f.name}")

        # Read and combine with error handling
        dfs = []
        for file in csv_files:
            try:
                df_temp = pd.read_csv(file)
                dfs.append(df_temp)
            except Exception as e:
                print(f"  ⚠ Warning: Failed to load {file.name}: {e}")

        if not dfs:
            raise ValueError("No valid CSV files could be loaded")

        self.df = pd.concat(dfs, ignore_index=True)

        # Validate required columns
        required_cols = ['DIFF_DAY', 'Metric', 'Mean']
        missing_cols = [col for col in required_cols if col not in self.df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        print(f"\n✓ Total rows loaded: {len(self.df):,}")
        print(f"✓ Unique metrics: {self.df['Metric'].nunique()}")
        print(f"✓ DIFF_DAY range: {self.df['DIFF_DAY'].min():.0f} - {self.df['DIFF_DAY'].max():.0f}")

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
            ],
            'Network Burst': [
                'network_burst_duration__avg_sec',
                'network_burst_frequency__avg_hz',
                'network_burst_percentage__avg'
            ]
        }
        return categories

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
            'Sec': 'sec'
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
        print(f"  ✓ Saved: {save_path.name}")

        if close:
            plt.close(fig)
