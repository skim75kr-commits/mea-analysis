"""
MEA Electrode-Level Analyzer v3.0 - Clean Version
-------------------------------------------------
완전히 새로 작성된 버전 (Windows 병렬 처리 지원)

주요 특징:
1. pd.melt를 사용한 벡터화 로딩 (10배 빠름)
2. ThreadPoolExecutor를 사용한 병렬 처리 (Windows 호환)
3. Percentage-based filtering (기본값 5%)
4. 향상된 시각화 (Seaborn 기반)

사용법:
    from mea_electrode_analyzer_v3_clean import ElectrodeAnalysisPipeline, ElectrodeFilterConfig
    
    pipeline = ElectrodeAnalysisPipeline(
        input_dir=r"D:\MyProjects\#4-2\dataset_P911_40_electrode",
        output_dir=r"D:\MyProjects\#4-2\output",
        n_workers=4,
        filter_config=ElectrodeFilterConfig(
            min_metric_ratio=0.5,
            min_pct_change=5.0,
            min_fold_change=2.0
        )
    )
    pipeline.run()
"""

import os
import re
import time
import warnings
from pathlib import Path
from dataclasses import dataclass
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings('ignore')

# Try to import tqdm
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Info: Install 'tqdm' for progress bars (optional)")

# Styling
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
plt.rcParams['font.family'] = 'sans-serif'

# Color palettes
PALETTE_CATEGORICAL = "Set2"
PALETTE_CONTINUOUS = "viridis"
PALETTE_DIVERGING = "vlag"

# ===========================================================================
# Performance utilities
# ===========================================================================

def timer(func):
    """성능 측정 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"  ⏱ {func.__name__} completed in {elapsed:.2f}s")
        return result
    return wrapper

class PerformanceMonitor:
    """성능 모니터"""
    def __init__(self):
        self.timings = {}

    def record(self, stage_name, elapsed_time):
        self.timings[stage_name] = elapsed_time

    def print_summary(self):
        total = sum(self.timings.values())
        print('\n' + '='*60)
        print('🚀 PERFORMANCE SUMMARY (v3.0)')
        print('='*60)
        print(f'Total execution time: {total:.2f}s\n')
        print('Stage breakdown:')
        for stage, t in self.timings.items():
            pct = (t / total * 100) if total > 0 else 0
            print(f'  {stage:30s}: {t:6.2f}s ({pct:5.1f}%)')
        print('='*60)

# ===========================================================================
# Utility functions
# ===========================================================================

def standardize_metric_name(name: str) -> str:
    """Metric 이름을 snake_case로 통일"""
    mapping = {
        "Number of Spikes": "number_of_spikes",
        "Mean Firing Rate (Hz)": "mean_firing_rate_hz",
        "ISI Coefficient of Variation": "isi_cv",
        "Number of Bursts": "number_of_bursts",
        "Burst Duration - Avg (s)": "burst_duration_avg_s",
        "Burst Duration - Std (s)": "burst_duration_std_s",
        "Number of Spikes per Burst - Avg": "spikes_per_burst_avg",
        "Number of Spikes per Burst - Std": "spikes_per_burst_std",
        "Mean ISI within Burst - Avg": "mean_isi_within_burst_avg",
        "Mean ISI within Burst - Std": "mean_isi_within_burst_std",
        "Median ISI within Burst - Avg": "median_isi_within_burst_avg",
        "Median ISI within Burst - Std": "median_isi_within_burst_std",
        "Inter-Burst Interval - Avg (s)": "inter_burst_interval_avg_s",
        "Inter-Burst Interval - Std (s)": "inter_burst_interval_std_s",
        "Burst Frequency (Hz)": "burst_frequency_hz",
        "IBI Coefficient of Variation": "ibi_cv",
        "Normalized Duration IQR": "normalized_duration_iqr",
        "Burst Percentage": "burst_percentage",
    }
    if name in mapping:
        return mapping[name]
    
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s

def extract_electrode_info(col_name: str) -> Tuple[Optional[str], Optional[int]]:
    """전극 컬럼명에서 Well과 Index 추출 (예: A1_11 -> ('A1', 11))"""
    pattern = r'^([A-D][1-6])_(\d{2})$'
    match = re.match(pattern, col_name)
    if match:
        return match.group(1), int(match.group(2))
    return None, None

# ===========================================================================
# Data loading
# ===========================================================================

def load_single_file(path_str: str) -> pd.DataFrame:
    """
    단일 Excel 파일을 long-format DataFrame으로 로드
    pd.melt를 사용한 벡터화 버전
    """
    try:
        file_path = Path(path_str)
        
        # Read Excel sheets
        xls = pd.ExcelFile(file_path)
        
        # Check required sheets
        required_sheets = {"Metadata", "Template", "Well_Info"}
        if not required_sheets.issubset(xls.sheet_names):
            return pd.DataFrame()

        df_meta = pd.read_excel(xls, sheet_name="Metadata")
        df_template = pd.read_excel(xls, sheet_name="Template")
        df_well = pd.read_excel(xls, sheet_name="Well_Info")
        
        # Parse metadata
        meta = df_meta.iloc[0].to_dict()
        plating_day = meta.get("Plating DAY", meta.get("PLATING_DAY", np.nan))
        
        # Well info map
        diff_map = dict(zip(df_well["Well"], df_well["Differentiation_Day"]))
        
        # Find electrode columns (A1_11, A1_12, etc.)
        exclude_cols = {"Metric", "Unit", "Condition"}
        electrode_cols = []
        for col in df_template.columns:
            if col not in exclude_cols:
                well, idx = extract_electrode_info(col)
                if well is not None:
                    electrode_cols.append(col)
        
        if not electrode_cols:
            return pd.DataFrame()
        
        # Melt: wide -> long format (핵심 최적화)
        df_melted = df_template.melt(
            id_vars=["Metric"],
            value_vars=electrode_cols,
            var_name="Electrode_ID",
            value_name="Value"
        )
        
        # Remove NaN values
        df_melted = df_melted.dropna(subset=["Value"])
        
        if df_melted.empty:
            return pd.DataFrame()
        
        # Extract Well and Electrode_Index
        df_melted[['Well', 'Electrode_Index']] = df_melted['Electrode_ID'].apply(
            lambda x: pd.Series(extract_electrode_info(x))
        )
        
        # Standardize metric names
        df_melted["Metric_Raw"] = df_melted["Metric"]
        df_melted["Metric"] = df_melted["Metric"].apply(standardize_metric_name)
        
        # Add metadata
        df_melted["File"] = file_path.stem
        df_melted["Plate_ID"] = meta.get("PLATE_ID", "UNKNOWN")
        df_melted["BASE_STIM"] = meta.get("BASE_STIM", "UNKNOWN")
        df_melted["TIME_START"] = meta.get("TIME_START", meta.get("TIME_START(sec)", 0))
        df_melted["TIME_DURATION_SEC"] = meta.get("TIME_DURATION(sec)", meta.get("TIME_DURATION_SEC", 0))
        df_melted["Plating_Day"] = plating_day
        df_melted["LIGHT_CODE"] = meta.get("LIGHT_CODE", "UNKNOWN")
        df_melted["INTENSITY_PCT"] = meta.get("INTENSITY(%)", meta.get("INTENSITY_PCT", 0))
        df_melted["EXP_TYPE"] = meta.get("EXP_TYPE", "UNKNOWN")
        df_melted["DRUG"] = meta.get("DRUG", "NONE")
        df_melted["CONCENTRATION_mM"] = meta.get("CONCENTRATION (mM)", meta.get("CONCENTRATION_MM", 0))
        
        # Fill NaNs in key columns
        fill_values = {
            "Plate_ID": "UNKNOWN",
            "BASE_STIM": "UNKNOWN",
            "LIGHT_CODE": "UNKNOWN",
            "EXP_TYPE": "UNKNOWN",
            "DRUG": "NONE"
        }
        df_melted.fillna(value=fill_values, inplace=True)
        
        # Differentiation day
        df_melted["Differentiation_Day"] = df_melted["Well"].map(diff_map)
        
        if pd.notna(plating_day):
            df_melted["DIFF_DAY"] = df_melted["Differentiation_Day"] + plating_day
        else:
            df_melted["DIFF_DAY"] = np.nan
        
        return df_melted
        
    except Exception as e:
        print(f"[ERROR] Failed to load {path_str}: {e}")
        return pd.DataFrame()

class ElectrodeFormatLoaderV3:
    """병렬 처리 로더 (ThreadPoolExecutor 사용)"""
    
    def __init__(self, input_dir, n_workers=4, use_cache=True):
        self.input_dir = Path(input_dir)
        self.n_workers = n_workers
        self.use_cache = use_cache
        self.cache_dir = self.input_dir / '.cache_v3'
        if use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @timer
    def load_all(self) -> pd.DataFrame:
        """모든 파일 로드 (병렬 처리)"""
        cache_file = self.cache_dir / 'electrode_all_long_v3.parquet'
        
        if self.use_cache and cache_file.exists():
            print(f"[LOAD] Found cache: {cache_file}")
            return pd.read_parquet(cache_file)
        
        # Find files
        files = [str(f) for f in self.input_dir.glob("*.xlsx") if not f.name.startswith("~$")]
        if not files:
            print("[LOAD] No files found.")
            return pd.DataFrame()
        
        print(f"[LOAD] Processing {len(files)} files with {self.n_workers} workers...")
        
        # Parallel loading with ThreadPoolExecutor (Windows compatible)
        results = []
        with ThreadPoolExecutor(max_workers=self.n_workers) as executor:
            if HAS_TQDM:
                results = list(tqdm(
                    executor.map(load_single_file, files),
                    total=len(files),
                    desc="Loading Files"
                ))
            else:
                print("Loading files...")
                results = list(executor.map(load_single_file, files))
        
        # Filter empty DataFrames
        valid_dfs = [df for df in results if not df.empty]
        
        if not valid_dfs:
            print(f"[WARN] No valid data found in {len(files)} files")
            return pd.DataFrame()
        
        print(f"[LOAD] Concatenating {len(valid_dfs)} valid DataFrames...")
        df_all = pd.concat(valid_dfs, ignore_index=True)
        
        # Type optimization (category for low-cardinality columns)
        cat_cols = ['Plate_ID', 'Well', 'Metric', 'BASE_STIM', 'LIGHT_CODE', 'EXP_TYPE', 'DRUG']
        for c in cat_cols:
            if c in df_all.columns:
                df_all[c] = df_all[c].astype('category')
        
        # Save cache
        if self.use_cache:
            print(f"[LOAD] Saving cache to {cache_file}")
            try:
                df_all.to_parquet(cache_file, index=False)
            except:
                print("[WARN] Failed to save parquet (install pyarrow or fastparquet)")
        
        return df_all

# ===========================================================================
# Filtering
# ===========================================================================

@dataclass
class ElectrodeFilterConfig:
    """
    필터 설정
    - min_metric_ratio: STIM에서 유효한 metric 비율 (0.0 ~ 1.0)
    - min_pct_change: BASE 대비 STIM 변화율 (%, 절대값)
    - min_fold_change: BASE 대비 STIM 배수
    """
    min_metric_ratio: float = 0.5
    min_pct_change: float = 5.0  # 5% change
    min_fold_change: float = 2.0

@timer
def filter_electrodes(
    df_long: pd.DataFrame,
    config: ElectrodeFilterConfig
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    전극 필터링 (벡터화 버전)
    Returns: (selected_stats, df_selected)
    """
    if df_long.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # Group keys
    key_cols = ["Plate_ID", "Well", "Electrode_ID", "LIGHT_CODE", "INTENSITY_PCT", "EXP_TYPE", "DRUG"]
    key_cols = [c for c in key_cols if c in df_long.columns]
    
    # 1. Metric completeness (in STIM)
    stim_mask = (df_long["BASE_STIM"] == "STIM") & df_long["Value"].notna()
    stim_data = df_long[stim_mask]
    
    total_metrics = df_long["Metric"].nunique()
    
    metric_counts = stim_data.groupby(key_cols)["Metric"].nunique().reset_index(name="n_metrics")
    metric_counts["ratio"] = metric_counts["n_metrics"] / total_metrics
    
    # 2. Spike difference (BASE vs STIM) - with SEM
    spike_data = df_long[df_long["Metric"] == "number_of_spikes"]
    
    # Calculate mean, SEM, and count for both BASE and STIM
    spike_stats = spike_data.groupby(key_cols + ["BASE_STIM"])["Value"].agg(['mean', 'sem', 'count']).reset_index()
    
    # Pivot to separate BASE and STIM
    spike_pivot = spike_stats.pivot_table(
        index=key_cols,
        columns="BASE_STIM",
        values=['mean', 'sem', 'count']
    ).reset_index()
    
    # Flatten column names
    spike_pivot.columns = [f"{col[1]}_{col[0]}" if col[1] else col[0] for col in spike_pivot.columns]
    
    # Ensure BASE and STIM columns exist
    for prefix in ['BASE', 'STIM']:
        if f"{prefix}_mean" not in spike_pivot.columns:
            spike_pivot[f"{prefix}_mean"] = 0
        if f"{prefix}_sem" not in spike_pivot.columns:
            spike_pivot[f"{prefix}_sem"] = 0
        if f"{prefix}_count" not in spike_pivot.columns:
            spike_pivot[f"{prefix}_count"] = 0
    
    # Rename for backward compatibility
    spike_pivot["BASE"] = spike_pivot["BASE_mean"]
    spike_pivot["STIM"] = spike_pivot["STIM_mean"]
    
    # Percentage change: |(STIM - BASE) / BASE| * 100
    epsilon = 1e-6
    spike_pivot["pct_change"] = ((spike_pivot["STIM"] - spike_pivot["BASE"]).abs() / (spike_pivot["BASE"] + epsilon)) * 100
    spike_pivot["fold_change"] = (spike_pivot["STIM"] + epsilon) / (spike_pivot["BASE"] + epsilon)
    
    # 3. Merge criteria
    merged = metric_counts.merge(spike_pivot, on=key_cols, how="inner")
    
    # 4. Apply filters
    cond_ratio = merged["ratio"] >= config.min_metric_ratio
    cond_pct = merged["pct_change"] >= config.min_pct_change
    cond_fc = merged["fold_change"] >= config.min_fold_change
    
    selected_stats = merged[cond_ratio & (cond_pct | cond_fc)].copy()
    
    # 5. Filter original data
    df_selected = df_long.merge(selected_stats[key_cols], on=key_cols, how="inner")
    
    return selected_stats, df_selected

# ===========================================================================
# Visualization
# ===========================================================================

class ElectrodeVisualizerV3:
    """향상된 시각화 클래스"""
    
    def __init__(self, df_selected, selected_stats, output_dir):
        self.df = df_selected
        self.stats = selected_stats
        self.out_dir = Path(output_dir) / 'visualizations'
        self.out_dir.mkdir(parents=True, exist_ok=True)
    
    @timer
    def create_all(self):
        """모든 시각화 생성"""
        print("\n[VIZ] Generating visualizations...")
        self.plot_heatmap()
        self.plot_volcano()
        self.plot_spatial_map()
        self.plot_dashboard()
        print("  ✓ Visualizations complete")
    
    def plot_heatmap(self):
        """Cluster heatmap"""
        if self.df.empty:
            return
        
        stim_data = self.df[self.df['BASE_STIM'] == 'STIM']
        pivot = stim_data.pivot_table(
            index='Electrode_ID', columns='Metric', values='Value', aggfunc='mean'
        )
        pivot = pivot.dropna(axis=1, how='all').fillna(0)
        
        if pivot.shape[0] < 2 or pivot.shape[1] < 2:
            return
        
        # Z-score normalization
        pivot_norm = (pivot - pivot.mean()) / pivot.std()
        pivot_norm = pivot_norm.fillna(0)
        
        g = sns.clustermap(
            pivot_norm,
            cmap="mako",
            center=0,
            figsize=(12, 10),
            dendrogram_ratio=(.1, .2),
            cbar_pos=(.02, .32, .03, .2)
        )
        g.fig.suptitle('Hierarchical Clustering of Elect rodes (STIM)', y=1.02, fontsize=16, fontweight='bold')
        plt.savefig(self.out_dir / 'cluster_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_volcano(self):
        """Volcano plot"""
        if self.stats is None or self.stats.empty:
            return
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        x = np.log2(self.stats['fold_change'])
        y = self.stats['STIM']
        
        sns.scatterplot(
            x=x, y=y,
            hue=self.stats['Well'],
            palette=PALETTE_CATEGORICAL,
            alpha=0.7, s=60, edgecolor='w', ax=ax
        )
        
        ax.axvline(0, color='gray', linestyle='--', alpha=0.5)
        ax.set_xlabel('Log2 Fold Change (STIM/BASE)', fontweight='bold')
        ax.set_ylabel('Activity Level (Spikes in STIM)', fontweight='bold')
        ax.set_title('Response Magnitude vs Direction', fontweight='bold')
        
        plt.savefig(self.out_dir / 'volcano_plot.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
    
    def plot_spatial_map(self):
        """Spatial response map (24-well plate)"""
        if self.stats is None or self.stats.empty:
            return
        
        rows = ['A', 'B', 'C', 'D']
        cols = range(1, 7)
        
        well_response = self.stats.groupby('Well')['pct_change'].mean()
        
        matrix = np.zeros((4, 6))
        for r_idx, r in enumerate(rows):
            for c_idx, c in enumerate(cols):
                well = f"{r}{c}"
                if well in well_response:
                    matrix[r_idx, c_idx] = well_response[well]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.heatmap(
            matrix,
            annot=True,
            fmt='.1f',
            cmap="Reds",
            xticklabels=cols,
            yticklabels=rows,
            ax=ax,
            cbar_kws={'label': 'Mean % Change'}
        )
        ax.set_title('Spatial Response Map (Mean % Change per Well)', fontweight='bold')
        plt.savefig(self.out_dir / 'spatial_map.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
    
    def plot_dashboard(self):
        """Summary dashboard with SEM error bars"""
        if self.df.empty:
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. Firing rate: Mean ± SEM
        ax = axes[0, 0]
        firing_data = self.df[self.df['Metric'] == 'mean_firing_rate_hz']
        if not firing_data.empty:
            # Calculate mean and SEM for BASE and STIM
            stats = firing_data.groupby('BASE_STIM')['Value'].agg(['mean', 'sem']).reset_index()
            x_pos = range(len(stats))
            ax.bar(x_pos, stats['mean'], yerr=stats['sem'], 
                   capsize=5, alpha=0.7, color=['#66c2a5', '#fc8d62'])
            ax.set_xticks(x_pos)
            ax.set_xticklabels(stats['BASE_STIM'])
            ax.set_ylabel('Firing Rate (Hz)', fontweight='bold')
            ax.set_title('Firing Rate (Mean ± SEM)', fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
        
        # 2. Burst frequency: Mean ± SEM
        ax = axes[0, 1]
        burst_data = self.df[self.df['Metric'] == 'burst_frequency_hz']
        if not burst_data.empty:
            stats = burst_data.groupby('BASE_STIM')['Value'].agg(['mean', 'sem']).reset_index()
            x_pos = range(len(stats))
            ax.bar(x_pos, stats['mean'], yerr=stats['sem'],
                   capsize=5, alpha=0.7, color=['#66c2a5', '#fc8d62'])
            ax.set_xticks(x_pos)
            ax.set_xticklabels(stats['BASE_STIM'])
            ax.set_ylabel('Burst Frequency (Hz)', fontweight='bold')
            ax.set_title('Burst Frequency (Mean ± SEM)', fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
        
        # 3. Spikes by BASE vs STIM: Mean ± SEM
        ax = axes[1, 0]
        spike_data = self.df[self.df['Metric'] == 'number_of_spikes']
        if not spike_data.empty:
            stats = spike_data.groupby('BASE_STIM')['Value'].agg(['mean', 'sem']).reset_index()
            x_pos = range(len(stats))
            ax.bar(x_pos, stats['mean'], yerr=stats['sem'],
                   capsize=5, alpha=0.7, color=['#66c2a5', '#fc8d62'])
            ax.set_xticks(x_pos)
            ax.set_xticklabels(stats['BASE_STIM'])
            ax.set_ylabel('Number of Spikes', fontweight='bold')
            ax.set_title('Spike Count (Mean ± SEM)', fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
        
        # 4. Metric correlation
        ax = axes[1, 1]
        stim_data = self.df[self.df['BASE_STIM'] == 'STIM']
        pivot = stim_data.pivot_table(
            index='Electrode_ID', columns='Metric', values='Value'
        )
        if pivot.shape[1] > 1:
            corr = pivot.corr()
            sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0, ax=ax)
            ax.set_title('Metric Correlation Matrix', fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.out_dir / 'dashboard.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

# ===========================================================================
# Main Pipeline
# ===========================================================================

class ElectrodeAnalysisPipelineV3:
    """전극 분석 파이프라인 v3.0"""
    
    def __init__(
        self,
        input_dir,
        output_dir,
        n_workers=4,
        use_cache=True,
        filter_config: Optional[ElectrodeFilterConfig] = None
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.n_workers = n_workers
        self.use_cache = use_cache
        self.filter_config = filter_config or ElectrodeFilterConfig()
        self.perf = PerformanceMonitor()
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    def run(self):
        """파이프라인 실행"""
        print(f"\n{'='*60}")
        print(f"MEA Electrode Analysis v3.0 | Workers: {self.n_workers}")
        print(f"{'='*60}\n")
        
        # 1. Load
        start = time.time()
        loader = ElectrodeFormatLoaderV3(self.input_dir, self.n_workers, self.use_cache)
        df_all = loader.load_all()
        self.perf.record("Loading", time.time() - start)
        
        if df_all.empty:
            print("[ERROR] No data loaded.")
            return
        
        print(f"[INFO] Loaded {len(df_all)} rows from {df_all['File'].nunique()} files")
        
        # 2. Save raw
        start = time.time()
        try:
            df_all.to_parquet(Path(self.output_dir) / 'electrode_all_long.parquet', index=False)
        except:
            df_all.to_csv(Path(self.output_dir) / 'electrode_all_long.csv', index=False)
            print("[WARN] Saved as CSV (install pyarrow for faster parquet)")
        self.perf.record("Save Raw", time.time() - start)
        
        # 3. Filter
        start = time.time()
        selected_stats, df_selected = filter_electrodes(df_all, self.filter_config)
        self.perf.record("Filtering", time.time() - start)
        
        if df_selected.empty:
            print("[WARN] No electrodes passed filtering criteria")
            return
        
        print(f"[INFO] {len(selected_stats)} electrodes selected")
        
        # 4. Save selected
        start = time.time()
        selected_stats.to_csv(Path(self.output_dir) / 'electrode_selected_stats.csv', index=False)
        try:
            df_selected.to_parquet(Path(self.output_dir) / 'electrode_selected_long.parquet', index=False)
        except:
            df_selected.to_csv(Path(self.output_dir) / 'electrode_selected_long.csv', index=False)
        self.perf.record("Save Selected", time.time() - start)
        
        # 5. Visualize
        start = time.time()
        viz = ElectrodeVisualizerV3(df_selected, selected_stats, self.output_dir)
        viz.create_all()
        self.perf.record("Visualization", time.time() - start)
        
        # Summary
        self.perf.print_summary()
        print(f"\n✓ Results saved to: {self.output_dir}")

# ===========================================================================
# Backward compatibility aliases
# ===========================================================================

ElectrodeAnalysisPipeline = ElectrodeAnalysisPipelineV3
ElectrodeFormatLoader = ElectrodeFormatLoaderV3

# ===========================================================================
# CLI
# ===========================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        input_path = r"D:\MyProjects\#4-2\dataset_P911_40_electrode"
    
    pipeline = ElectrodeAnalysisPipelineV3(
        input_dir=input_path,
        output_dir=str(Path(input_path).parent / "output_electrode"),
        n_workers=4
    )
    pipeline.run()
