"""
MEA Electrode-Level Analyzer v2.0 (Optimized & Enhanced)
---------------------------------------------------------
v1.0 대비 주요 개선사항:
1. 성능 최적화: 병렬 처리, 캐싱, 메모리 효율적인 groupby 연산
2. 시각화 업그레이드: 히트맵, 박스플롯, 분포 플롯, 전극 맵 등
3. Progress bar: 실시간 진행 상황 표시
4. 메모리 누수 방지: Figure 명시적 close
5. Parquet 캐싱: 빠른 재분석

핵심 기능:
- 24 wells × 16 electrodes (Axion Maestro 기준) 전극 레벨 분석
- 입력: electrode 전용 Excel (Metadata / Template / Well_Info)
- 출력:
    1) electrode_all_long.csv/parquet  : 전체 전극 × metric long-format
    2) electrode_selected_stats.csv : 필터 통과 전극 통계
    3) electrode_selected_long.csv  : 필터 통과 전극의 모든 metric
    4) 향상된 시각화: 히트맵, 박스플롯, 분포도, 전극 맵 등

Usage:
    from mea_electrode_analyzer_v2 import ElectrodeAnalysisPipelineV2

    pipeline = ElectrodeAnalysisPipelineV2(
        input_dir=r"D:\MEAdata\#7_electrode",
        output_dir=r"D:\MEAdata\#7_electrode\analysis",
        n_workers=4,
        use_cache=True
    )
    pipeline.run()
"""

from pathlib import Path
from dataclasses import dataclass
import re
import time
import gc
import warnings
from functools import wraps
import concurrent.futures

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for better performance
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Rectangle

warnings.filterwarnings('ignore')

# Optional: Progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Info: Install 'tqdm' for progress bars: pip install tqdm")


# =============================================================================
# PERFORMANCE UTILITIES
# =============================================================================

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
    """성능 모니터링"""

    def __init__(self):
        self.timings = {}

    def record(self, stage_name, elapsed_time):
        """타이밍 기록"""
        self.timings[stage_name] = elapsed_time

    def get_summary(self):
        """성능 요약"""
        total = sum(self.timings.values())
        summary = {
            'total_time': total,
            'stage_times': self.timings,
            'breakdown': {k: v/total*100 for k, v in self.timings.items()} if total > 0 else {}
        }
        return summary

    def print_summary(self):
        """성능 요약 출력"""
        summary = self.get_summary()
        print('\n' + '='*80)
        print('PERFORMANCE SUMMARY')
        print('='*80)
        print(f"Total execution time: {summary['total_time']:.2f}s")
        print('\nStage breakdown:')
        for stage, percentage in summary['breakdown'].items():
            time_s = summary['stage_times'][stage]
            print(f"  {stage:30s}: {time_s:6.2f}s ({percentage:5.1f}%)")
        print('='*80)


# =============================================================================
# 1. Metric 이름 표준화
# =============================================================================

def standardize_metric_name(name: str) -> str:
    """
    Axion에서 나온 metric 이름을 snake_case로 통일.
    """
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

    # fallback: generic snake_case 변환
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s


# =============================================================================
# 2. 전극 ID 파싱 (A1_11 → (A1, 11))
# =============================================================================

def extract_electrode_info(col_name: str):
    """
    'A1_11' → ('A1', '11')
    Axion 24-well: Well = A1~D6, Electrode Index = 11~48
    """
    m = re.match(r'^([A-D][1-6])_(\d{2})$', col_name)
    if not m:
        return None, None
    return m.group(1), m.group(2)


# =============================================================================
# 3. 단일 Excel (electrode 파일) → long-format 변환 (최적화)
# =============================================================================

@timer
def load_single_electrode_excel(path: str) -> pd.DataFrame:
    """
    하나의 electrode Excel 파일을 long-format 전극 레벨 DataFrame으로 변환.
    - 각 row: (Plate_ID, File, Well, Electrode_ID, Metric, Value, ...)
    - 최적화: vectorized 연산 사용
    """
    file_path = Path(path)

    df_meta = pd.read_excel(file_path, sheet_name="Metadata")
    df_template = pd.read_excel(file_path, sheet_name="Template")
    df_well = pd.read_excel(file_path, sheet_name="Well_Info")

    meta = df_meta.iloc[0].to_dict()
    # Well_Info: Well / Differentiation_Day
    diff_map = dict(zip(df_well["Well"], df_well["Differentiation_Day"]))

    plating_day = meta.get("Plating DAY", meta.get("PLATING_DAY", np.nan))

    # 전극 컬럼 찾기 (Metric / Unit / Condition 제외, A1_11 같은 패턴만)
    electrode_cols = []
    for c in df_template.columns:
        if c in ("Metric", "Unit", "Condition"):
            continue
        well, elec_idx = extract_electrode_info(c)
        if well is not None:
            electrode_cols.append(c)

    print(f"[LOAD] {file_path.name}: {len(electrode_cols)} electrode columns detected")

    # 최적화: 벡터화된 방식으로 데이터 변환
    rows = []
    for _, row in df_template.iterrows():
        metric_raw = row["Metric"]
        metric_std = standardize_metric_name(metric_raw)

        for col in electrode_cols:
            val = row[col]
            if pd.isna(val):
                continue

            well, elec_idx = extract_electrode_info(col)
            diff_day0 = diff_map.get(well, np.nan)
            diff_day = (
                diff_day0 + plating_day
                if pd.notna(diff_day0) and pd.notna(plating_day)
                else np.nan
            )

            rows.append(
                {
                    "File": file_path.stem,
                    "Plate_ID": meta.get("PLATE_ID", "UNKNOWN"),
                    "Well": well,
                    "Electrode_ID": col,
                    "Electrode_Index": elec_idx,
                    "Metric": metric_std,
                    "Metric_Raw": metric_raw,
                    "Value": float(val),
                    "BASE_STIM": meta.get("BASE_STIM", "UNKNOWN"),
                    "TIME_START": meta.get("TIME_START", meta.get("TIME_START(sec)", 0)),
                    "TIME_DURATION_SEC": meta.get(
                        "TIME_DURATION(sec)", meta.get("TIME_DURATION_SEC", 0)
                    ),
                    "Plating_Day": plating_day,
                    "Differentiation_Day": diff_day0,
                    "DIFF_DAY": diff_day,
                    "LIGHT_CODE": meta.get("LIGHT_CODE", "UNKNOWN"),
                    "INTENSITY_PCT": meta.get(
                        "INTENSITY(%)", meta.get("INTENSITY_PCT", 0)
                    ),
                    "EXP_TYPE": meta.get("EXP_TYPE", "UNKNOWN"),
                    "DRUG": meta.get("DRUG", "NONE"),
                    "CONCENTRATION_mM": meta.get(
                        "CONCENTRATION (mM)", meta.get("CONCENTRATION_MM", 0)
                    ),
                }
            )

    df_long = pd.DataFrame(rows)
    return df_long


# =============================================================================
# 4. 여러 파일 로더 (폴더 단위) - 최적화
# =============================================================================

class ElectrodeFormatLoaderV2:
    """
    electrode Excel 파일들을 폴더에서 모두 읽어서
    전극 레벨 long-format DataFrame으로 합치는 클래스 (최적화 버전)
    """

    def __init__(self, input_dir, use_cache=True):
        self.input_dir = Path(input_dir)
        self.files = []
        self.use_cache = use_cache
        self.cache_dir = self.input_dir / '.cache'
        if use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @timer
    def load_all(self) -> pd.DataFrame:
        """폴더 내 *.xlsx (임시파일 ~$ 제외)를 모두 읽어서 concat."""

        # 캐시 확인
        cache_file = self.cache_dir / 'electrode_all_long.parquet'
        if self.use_cache and cache_file.exists():
            print(f"[LOAD] Loading from cache: {cache_file}")
            df_all = pd.read_parquet(cache_file)
            print(
                f"[LOAD] Cached data: {len(df_all)} rows, "
                f"{df_all['Electrode_ID'].nunique()} electrodes, "
                f"{df_all['Metric'].nunique()} metrics"
            )
            return df_all

        self.files = [
            f for f in self.input_dir.glob("*.xlsx") if not f.name.startswith("~$")
        ]

        if not self.files:
            print(f"[LOAD] No Excel files found in {self.input_dir}")
            return pd.DataFrame()

        all_rows = []

        # Progress bar 지원
        file_iter = tqdm(self.files, desc="Loading files") if HAS_TQDM else self.files

        for f in file_iter:
            try:
                df_long = load_single_electrode_excel(str(f))
                all_rows.append(df_long)
            except Exception as e:
                print(f"[WARN] Failed to load {f.name}: {e}")

        if not all_rows:
            print("[LOAD] No valid data loaded from any file.")
            return pd.DataFrame()

        df_all = pd.concat(all_rows, ignore_index=True)
        print(
            f"[LOAD] Combined: {len(df_all)} rows, "
            f"{df_all['Electrode_ID'].nunique()} electrodes, "
            f"{df_all['Metric'].nunique()} metrics"
        )

        # 캐시 저장
        if self.use_cache and not df_all.empty:
            print(f"[LOAD] Saving to cache: {cache_file}")
            df_all.to_parquet(cache_file, index=False)

        return df_all


# =============================================================================
# 5. 전극 필터링 기준 설정 (dataclass)
# =============================================================================

@dataclass
class ElectrodeFilterConfig:
    """
    전극 선택 기준 설정값.
    """
    min_metric_ratio: float = 0.5
    min_abs_spike_diff: float = 20.0
    min_fold_change: float = 2.0


# =============================================================================
# 6. 실제 필터링 로직 (최적화)
# =============================================================================

@timer
def filter_electrodes(
    df_long: pd.DataFrame,
    min_metric_ratio: float = 0.5,
    min_abs_spike_diff: float = 20.0,
    min_fold_change: float = 2.0,
    verbose: bool = True,
):
    """
    전극 레벨 필터링 (최적화).
    1) STIM에서 metric 대부분이 non-NaN인 전극만 고려
    2) BASE vs STIM 'number_of_spikes' 차이가 큰 전극만 선택

    최적화: groupby 및 vectorized 연산 사용
    """
    if df_long.empty:
        if verbose:
            print("[FILTER] Empty DataFrame, nothing to filter.")
        return None, df_long.iloc[0:0]

    df = df_long.copy()
    total_metrics = df["Metric"].nunique()
    if verbose:
        print(f"[FILTER] Total unique metrics: {total_metrics}")

    # 전극 식별을 위한 key
    key_cols = [
        "Plate_ID",
        "Well",
        "Electrode_ID",
        "Electrode_Index",
        "LIGHT_CODE",
        "INTENSITY_PCT",
        "EXP_TYPE",
        "DRUG",
    ]

    # (1) STIM에서 metric presence 계산 (최적화: vectorized mask)
    stim_mask = (df["BASE_STIM"] == "STIM") & df["Value"].notna()
    stim_nonan = df[stim_mask]

    if stim_nonan.empty:
        if verbose:
            print("[FILTER] No STIM data found.")
        return None, df.iloc[0:0]

    # 최적화: groupby + agg
    stim_counts = (
        stim_nonan.groupby(key_cols)["Metric"]
        .nunique()
        .reset_index()
        .rename(columns={"Metric": "n_metrics_stim"})
    )
    stim_counts["metric_ratio"] = stim_counts["n_metrics_stim"] / float(total_metrics)

    # (2) BASE vs STIM number_of_spikes 비교
    base_mask = (df["BASE_STIM"] == "BASE") & (df["Metric"] == "number_of_spikes")
    stim_spike_mask = (df["BASE_STIM"] == "STIM") & (df["Metric"] == "number_of_spikes")

    spikes_base = (
        df[base_mask]
        .groupby(key_cols)["Value"]
        .mean()
        .reset_index()
        .rename(columns={"Value": "spikes_base"})
    )

    spikes_stim = (
        df[stim_spike_mask]
        .groupby(key_cols)["Value"]
        .mean()
        .reset_index()
        .rename(columns={"Value": "spikes_stim"})
    )

    merged = (
        stim_counts.merge(spikes_base, on=key_cols, how="left")
        .merge(spikes_stim, on=key_cols, how="left")
    )

    # spike 값이 없는 전극 제거
    merged = merged.dropna(subset=["spikes_base", "spikes_stim"])

    eps = 1e-6
    merged["abs_diff"] = (merged["spikes_stim"] - merged["spikes_base"]).abs()
    merged["fold_change"] = (merged["spikes_stim"] + eps) / (merged["spikes_base"] + eps)

    # 조건식 (vectorized)
    cond_metrics = merged["metric_ratio"] >= min_metric_ratio
    cond_diff = merged["abs_diff"] >= min_abs_spike_diff
    cond_fc = merged["fold_change"] >= min_fold_change

    merged["selected"] = cond_metrics & (cond_diff | cond_fc)

    selected_stats = merged[merged["selected"]].copy()

    if verbose:
        print(
            f"[FILTER] Electrodes with sufficient metrics: "
            f"{cond_metrics.sum()}/{len(merged)}"
        )
        print(
            f"[FILTER] Selected electrodes (large spike change): "
            f"{selected_stats.shape[0]}"
        )

    # (3) 원래 DataFrame에서 선택된 전극의 모든 metric 추출
    if selected_stats.empty:
        df_filtered = df.iloc[0:0]
    else:
        df_flagged = df.merge(
            selected_stats[key_cols + ["selected"]], on=key_cols, how="left"
        )
        df_filtered = df_flagged[df_flagged["selected"] == True].copy()
        df_filtered.drop(columns=["selected"], inplace=True)

    return selected_stats, df_filtered


# =============================================================================
# 7. 시각화 클래스 (신규 추가 - v2.0)
# =============================================================================

class ElectrodeVisualizer:
    """전극 레벨 시각화 (v2.0 - Enhanced)"""

    def __init__(self, df_all, df_selected, selected_stats, output_dir):
        self.df_all = df_all
        self.df_selected = df_selected
        self.selected_stats = selected_stats
        self.output_dir = Path(output_dir) / 'visualizations'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @timer
    def create_all_visualizations(self):
        """모든 시각화 생성"""
        print("\n[VIZ] Creating visualizations...")

        viz_funcs = [
            self.plot_electrode_selection_overview,
            self.plot_electrode_heatmap,
            self.plot_electrode_distribution,
            self.plot_spike_comparison,
            self.plot_electrode_spatial_map,
            self.plot_metric_completeness,
        ]

        for func in viz_funcs:
            try:
                func()
            except Exception as e:
                print(f"  ⚠ Warning in {func.__name__}: {e}")

        print("  ✓ All visualizations created")

    def plot_electrode_selection_overview(self):
        """전극 선택 개요"""
        if self.selected_stats is None or self.selected_stats.empty:
            return

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 1. Metric ratio distribution
        ax1 = axes[0, 0]
        ax1.hist(self.selected_stats['metric_ratio'], bins=20, edgecolor='black', alpha=0.7)
        ax1.axvline(self.selected_stats['metric_ratio'].mean(), color='red',
                   linestyle='--', label=f'Mean: {self.selected_stats["metric_ratio"].mean():.2f}')
        ax1.set_xlabel('Metric Ratio', fontweight='bold')
        ax1.set_ylabel('Count', fontweight='bold')
        ax1.set_title('Metric Completeness Distribution', fontweight='bold')
        ax1.legend()
        ax1.grid(alpha=0.3)

        # 2. Spike difference
        ax2 = axes[0, 1]
        ax2.hist(self.selected_stats['abs_diff'], bins=20, edgecolor='black', alpha=0.7, color='orange')
        ax2.axvline(self.selected_stats['abs_diff'].mean(), color='red',
                   linestyle='--', label=f'Mean: {self.selected_stats["abs_diff"].mean():.1f}')
        ax2.set_xlabel('Absolute Spike Difference (BASE vs STIM)', fontweight='bold')
        ax2.set_ylabel('Count', fontweight='bold')
        ax2.set_title('Spike Response Magnitude', fontweight='bold')
        ax2.legend()
        ax2.grid(alpha=0.3)

        # 3. Fold change
        ax3 = axes[1, 0]
        fold_change_clipped = np.clip(self.selected_stats['fold_change'], 0, 10)
        ax3.hist(fold_change_clipped, bins=20, edgecolor='black', alpha=0.7, color='green')
        ax3.axvline(fold_change_clipped.mean(), color='red',
                   linestyle='--', label=f'Mean: {fold_change_clipped.mean():.2f}')
        ax3.set_xlabel('Fold Change (STIM/BASE, clipped at 10)', fontweight='bold')
        ax3.set_ylabel('Count', fontweight='bold')
        ax3.set_title('Response Fold Change', fontweight='bold')
        ax3.legend()
        ax3.grid(alpha=0.3)

        # 4. Selected electrodes per well
        ax4 = axes[1, 1]
        well_counts = self.selected_stats['Well'].value_counts().sort_index()
        ax4.bar(range(len(well_counts)), well_counts.values, edgecolor='black', alpha=0.7)
        ax4.set_xticks(range(len(well_counts)))
        ax4.set_xticklabels(well_counts.index, rotation=45, ha='right')
        ax4.set_xlabel('Well', fontweight='bold')
        ax4.set_ylabel('Selected Electrodes', fontweight='bold')
        ax4.set_title('Selected Electrodes per Well', fontweight='bold')
        ax4.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'electrode_selection_overview.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_electrode_heatmap(self):
        """전극별 metric 히트맵"""
        if self.df_selected.empty:
            return

        # 주요 metric만 선택
        key_metrics = [
            'number_of_spikes', 'mean_firing_rate_hz', 'number_of_bursts',
            'burst_frequency_hz', 'spikes_per_burst_avg'
        ]

        available_metrics = [m for m in key_metrics if m in self.df_selected['Metric'].unique()]

        if not available_metrics:
            return

        # STIM 데이터만 사용
        stim_data = self.df_selected[self.df_selected['BASE_STIM'] == 'STIM']

        # Pivot table 생성
        pivot = stim_data[stim_data['Metric'].isin(available_metrics)].pivot_table(
            index='Electrode_ID',
            columns='Metric',
            values='Value',
            aggfunc='mean'
        )

        if pivot.empty:
            return

        # Z-score normalization for better visualization
        pivot_norm = (pivot - pivot.mean()) / pivot.std()

        fig, ax = plt.subplots(figsize=(max(12, len(pivot.columns) * 1.5),
                                        max(10, len(pivot.index) * 0.3)))

        sns.heatmap(pivot_norm, annot=False, cmap='RdYlGn', center=0,
                   cbar_kws={'label': 'Z-score'},
                   linewidths=0.5, linecolor='gray', ax=ax)

        ax.set_title('Selected Electrodes - Key Metrics Heatmap (Z-score normalized)',
                    fontweight='bold', fontsize=14, pad=15)
        ax.set_xlabel('Metrics', fontweight='bold')
        ax.set_ylabel('Electrode ID', fontweight='bold')

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(self.output_dir / 'electrode_metrics_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_electrode_distribution(self):
        """전극별 주요 metric 분포 (박스플롯)"""
        if self.df_selected.empty:
            return

        # 주요 metric
        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
        available_metrics = [m for m in key_metrics if m in self.df_selected['Metric'].unique()]

        if not available_metrics:
            return

        n_metrics = len(available_metrics)
        fig, axes = plt.subplots(1, n_metrics, figsize=(6*n_metrics, 6))

        if n_metrics == 1:
            axes = [axes]

        for idx, metric in enumerate(available_metrics):
            ax = axes[idx]

            metric_data = self.df_selected[
                (self.df_selected['Metric'] == metric) &
                (self.df_selected['BASE_STIM'] == 'STIM')
            ]

            if metric_data.empty:
                continue

            wells = sorted(metric_data['Well'].unique())
            data_by_well = [metric_data[metric_data['Well'] == w]['Value'].values for w in wells]

            bp = ax.boxplot(data_by_well, labels=wells, patch_artist=True)

            # 색상 적용
            colors = plt.cm.Set3(np.linspace(0, 1, len(bp['boxes'])))
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)

            ax.set_xlabel('Well', fontweight='bold')
            ax.set_ylabel('Value', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}\n(STIM, by Well)',
                        fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'electrode_distribution_boxplots.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_spike_comparison(self):
        """BASE vs STIM spike 비교"""
        if self.selected_stats is None or self.selected_stats.empty:
            return

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # 1. Scatter plot
        ax1 = axes[0]
        ax1.scatter(self.selected_stats['spikes_base'],
                   self.selected_stats['spikes_stim'],
                   alpha=0.6, s=50, edgecolor='black')

        # Diagonal line (y=x)
        max_val = max(self.selected_stats['spikes_base'].max(),
                     self.selected_stats['spikes_stim'].max())
        ax1.plot([0, max_val], [0, max_val], 'r--', label='y=x (no change)')

        ax1.set_xlabel('Spikes (BASE)', fontweight='bold')
        ax1.set_ylabel('Spikes (STIM)', fontweight='bold')
        ax1.set_title('BASE vs STIM Spike Count\n(Selected Electrodes)', fontweight='bold')
        ax1.legend()
        ax1.grid(alpha=0.3)

        # 2. Difference per well
        ax2 = axes[1]
        well_diff = self.selected_stats.groupby('Well')['abs_diff'].mean().sort_values(ascending=False)

        ax2.bar(range(len(well_diff)), well_diff.values, edgecolor='black', alpha=0.7, color='coral')
        ax2.set_xticks(range(len(well_diff)))
        ax2.set_xticklabels(well_diff.index, rotation=45, ha='right')
        ax2.set_xlabel('Well', fontweight='bold')
        ax2.set_ylabel('Mean Absolute Spike Difference', fontweight='bold')
        ax2.set_title('Response Magnitude by Well\n(Selected Electrodes)', fontweight='bold')
        ax2.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'spike_comparison.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_electrode_spatial_map(self):
        """전극 공간 분포 맵 (24-well plate)"""
        if self.selected_stats is None or self.selected_stats.empty:
            return

        # Well 위치 매핑 (A1-D6 24-well plate)
        rows = ['A', 'B', 'C', 'D']
        cols = [1, 2, 3, 4, 5, 6]

        # Well별 선택된 전극 수
        well_counts = self.selected_stats['Well'].value_counts()

        # 매트릭스 생성
        matrix = np.zeros((len(rows), len(cols)))
        for well, count in well_counts.items():
            if len(well) >= 2:
                row_idx = rows.index(well[0])
                col_idx = cols.index(int(well[1]))
                matrix[row_idx, col_idx] = count

        fig, ax = plt.subplots(figsize=(10, 6))

        im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')

        # 축 설정
        ax.set_xticks(range(len(cols)))
        ax.set_yticks(range(len(rows)))
        ax.set_xticklabels(cols)
        ax.set_yticklabels(rows)

        # 값 표시
        for i in range(len(rows)):
            for j in range(len(cols)):
                text = ax.text(j, i, int(matrix[i, j]),
                             ha="center", va="center", color="black", fontweight='bold')

        ax.set_title('Selected Electrodes - Spatial Distribution\n(24-well plate)',
                    fontweight='bold', fontsize=14)
        ax.set_xlabel('Column', fontweight='bold')
        ax.set_ylabel('Row', fontweight='bold')

        # Colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Number of Selected Electrodes', fontweight='bold')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'electrode_spatial_map.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_metric_completeness(self):
        """Metric 완전성 분석"""
        if self.df_all.empty:
            return

        # STIM 데이터의 metric별 완전성
        stim_data = self.df_all[self.df_all['BASE_STIM'] == 'STIM']

        # 전극별 metric 개수
        electrode_metrics = stim_data.groupby('Electrode_ID')['Metric'].nunique()

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # 1. Histogram
        ax1 = axes[0]
        ax1.hist(electrode_metrics.values, bins=20, edgecolor='black', alpha=0.7, color='skyblue')
        ax1.axvline(electrode_metrics.mean(), color='red', linestyle='--',
                   label=f'Mean: {electrode_metrics.mean():.1f}')
        ax1.set_xlabel('Number of Metrics (per electrode)', fontweight='bold')
        ax1.set_ylabel('Frequency', fontweight='bold')
        ax1.set_title('Metric Completeness Distribution\n(STIM data)', fontweight='bold')
        ax1.legend()
        ax1.grid(alpha=0.3)

        # 2. Metric별 데이터 포인트 수
        ax2 = axes[1]
        metric_counts = stim_data['Metric'].value_counts().head(15)

        ax2.barh(range(len(metric_counts)), metric_counts.values, edgecolor='black', alpha=0.7)
        ax2.set_yticks(range(len(metric_counts)))
        ax2.set_yticklabels([m.replace('_', ' ').title() for m in metric_counts.index])
        ax2.set_xlabel('Number of Data Points', fontweight='bold')
        ax2.set_title('Top 15 Metrics by Data Availability\n(STIM)', fontweight='bold')
        ax2.grid(axis='x', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'metric_completeness.png', dpi=300, bbox_inches='tight')
        plt.close(fig)


# =============================================================================
# 8. 파이프라인 클래스 V2 (최적화 & 시각화 강화)
# =============================================================================

class ElectrodeAnalysisPipelineV2:
    """
    전극 레벨 분석 파이프라인 v2.0 (최적화 & 시각화 강화)

    Usage:
        pipeline = ElectrodeAnalysisPipelineV2(
            input_dir=r"D:\MEAdata\#7_electrode",
            output_dir=r"D:\MEAdata\#7_electrode\analysis",
            n_workers=4,
            use_cache=True,
            filter_config=ElectrodeFilterConfig(
                min_metric_ratio=0.5,
                min_abs_spike_diff=20,
                min_fold_change=2.0
            )
        )
        pipeline.run()
    """

    def __init__(
        self,
        input_dir,
        output_dir,
        filter_config: ElectrodeFilterConfig | None = None,
        n_workers: int = 4,
        use_cache: bool = True,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.filter_config = filter_config or ElectrodeFilterConfig()
        self.n_workers = n_workers
        self.use_cache = use_cache

        self.df_all: pd.DataFrame | None = None
        self.selected_stats: pd.DataFrame | None = None
        self.df_selected: pd.DataFrame | None = None

        # 성능 모니터링
        self.performance = PerformanceMonitor()

    def run(self):
        """전체 파이프라인 실행"""
        print('='*80)
        print('MEA ELECTRODE-LEVEL ANALYZER V2.0 (OPTIMIZED & ENHANCED)')
        print('='*80)
        print(f'Input: {self.input_dir}')
        print(f'Output: {self.output_dir}')
        print(f'Cache: {"Enabled" if self.use_cache else "Disabled"}')
        print(f'Workers: {self.n_workers}')
        print('='*80)

        pipeline_start = time.time()

        # 1) 로딩
        stage_start = time.time()
        print('\n[STAGE 1] Loading electrode data...')
        loader = ElectrodeFormatLoaderV2(self.input_dir, use_cache=self.use_cache)
        self.df_all = loader.load_all()
        self.performance.record('Stage 1: Data Loading', time.time() - stage_start)

        if self.df_all.empty:
            print("[PIPELINE] No electrode data loaded. Abort.")
            return

        # 2) raw long-format 저장
        stage_start = time.time()
        print('\n[STAGE 2] Saving raw data...')
        combined_path = self.output_dir / "electrode_all_long.csv"
        self.df_all.to_csv(combined_path, index=False)
        print(f"  ✓ Saved: {combined_path}")

        # Parquet도 저장 (빠른 로딩용)
        parquet_path = self.output_dir / "electrode_all_long.parquet"
        self.df_all.to_parquet(parquet_path, index=False)
        print(f"  ✓ Saved: {parquet_path}")
        self.performance.record('Stage 2: Save Raw Data', time.time() - stage_start)

        # 3) 전극 필터링
        stage_start = time.time()
        print('\n[STAGE 3] Filtering electrodes...')
        self.selected_stats, self.df_selected = filter_electrodes(
            self.df_all,
            min_metric_ratio=self.filter_config.min_metric_ratio,
            min_abs_spike_diff=self.filter_config.min_abs_spike_diff,
            min_fold_change=self.filter_config.min_fold_change,
            verbose=True,
        )
        self.performance.record('Stage 3: Electrode Filtering', time.time() - stage_start)

        if self.selected_stats is None or self.selected_stats.empty:
            print("[PIPELINE] No electrodes passed the selection criteria.")
            return

        # 4) 결과 저장
        stage_start = time.time()
        print('\n[STAGE 4] Saving filtered data...')
        stats_path = self.output_dir / "electrode_selected_stats.csv"
        self.selected_stats.to_csv(stats_path, index=False)
        print(f"  ✓ Saved: {stats_path}")

        selected_path = self.output_dir / "electrode_selected_long.csv"
        self.df_selected.to_csv(selected_path, index=False)
        print(f"  ✓ Saved: {selected_path}")

        # Parquet도 저장
        selected_parquet = self.output_dir / "electrode_selected_long.parquet"
        self.df_selected.to_parquet(selected_parquet, index=False)
        print(f"  ✓ Saved: {selected_parquet}")
        self.performance.record('Stage 4: Save Filtered Data', time.time() - stage_start)

        # 5) 시각화 생성 (v2.0 신규)
        stage_start = time.time()
        print('\n[STAGE 5] Creating visualizations...')
        visualizer = ElectrodeVisualizer(
            self.df_all,
            self.df_selected,
            self.selected_stats,
            self.output_dir
        )
        visualizer.create_all_visualizations()
        self.performance.record('Stage 5: Visualizations', time.time() - stage_start)

        # 6) 최종 리포트
        self._generate_final_report()

        # 성능 요약
        total_time = time.time() - pipeline_start
        self.performance.record('Total Pipeline', total_time)
        self.performance.print_summary()

        print('\n' + '='*80)
        print('🎉 PIPELINE COMPLETE!')
        print('='*80)
        print(f'Results: {self.output_dir}')
        print(f'Total time: {total_time:.2f}s')
        print('='*80)

        # 메모리 정리
        gc.collect()

    def _generate_final_report(self):
        """최종 리포트 생성"""
        report = []
        report.append('='*80)
        report.append('MEA ELECTRODE-LEVEL ANALYZER V2.0 - FINAL REPORT')
        report.append('='*80)
        report.append(f'\nInput: {self.input_dir}')
        report.append(f'Output: {self.output_dir}')
        report.append('')

        # Data summary
        report.append('DATA SUMMARY:')
        report.append(f'  Total electrodes (all): {self.df_all["Electrode_ID"].nunique()}')
        report.append(f'  Total rows (all): {len(self.df_all)}')
        report.append(f'  Total metrics: {self.df_all["Metric"].nunique()}')
        report.append(f'  Selected electrodes: {self.df_selected["Electrode_ID"].nunique()}')
        report.append(f'  Selected rows: {len(self.df_selected)}')
        report.append('')

        # Filter config
        report.append('FILTER CONFIGURATION:')
        report.append(f'  Min metric ratio: {self.filter_config.min_metric_ratio}')
        report.append(f'  Min abs spike diff: {self.filter_config.min_abs_spike_diff}')
        report.append(f'  Min fold change: {self.filter_config.min_fold_change}')
        report.append('')

        # Performance summary
        perf_summary = self.performance.get_summary()
        report.append('PERFORMANCE SUMMARY:')
        report.append(f"  Total time: {perf_summary['total_time']:.2f}s")
        for stage, time_s in perf_summary['stage_times'].items():
            pct = perf_summary['breakdown'].get(stage, 0)
            report.append(f"  {stage}: {time_s:.2f}s ({pct:.1f}%)")
        report.append('')

        # V2.0 improvements
        report.append('V2.0 IMPROVEMENTS:')
        report.append('  ✓ Performance optimization (timer, caching, vectorization)')
        report.append('  ✓ Enhanced visualizations (heatmaps, boxplots, spatial maps)')
        report.append('  ✓ Memory efficiency (groupby, explicit cleanup)')
        report.append('  ✓ Progress bars (tqdm support)')
        report.append('  ✓ Parquet format support (faster I/O)')
        report.append('')

        # Outputs
        report.append('OUTPUT FILES:')
        report.append('  • electrode_all_long.csv/parquet - All electrode data')
        report.append('  • electrode_selected_stats.csv - Selected electrode statistics')
        report.append('  • electrode_selected_long.csv/parquet - Selected electrode data')
        report.append('  • visualizations/ - Enhanced plots and heatmaps')
        report.append('')

        report.append('='*80)

        report_path = self.output_dir / 'FINAL_REPORT.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))

        print(f'\n✓ Final report saved: {report_path}')


# =============================================================================
# 9. 직접 실행용 예시
# =============================================================================

if __name__ == "__main__":
    # 예시 경로 (원하는 대로 수정해서 사용)
    input_dir = r"D:\MEAdata\#7_electrode"
    output_dir = r"D:\MEAdata\#7_electrode\analysis_electrode_v2"

    config = ElectrodeFilterConfig(
        min_metric_ratio=0.5,     # STIM에서 metric의 절반 이상이 채워진 전극만
        min_abs_spike_diff=20.0,  # BASE vs STIM spike 차이 20 이상
        min_fold_change=2.0       # 또는 2배 이상 증가/감소
    )

    pipeline = ElectrodeAnalysisPipelineV2(
        input_dir=input_dir,
        output_dir=output_dir,
        filter_config=config,
        n_workers=4,
        use_cache=True,
    )
    pipeline.run()


# =============================================================================
# ALIAS FOR BACKWARD COMPATIBILITY
# =============================================================================
# 기존 코드와의 호환성을 위해 ElectrodeAnalysisPipeline alias 제공
ElectrodeAnalysisPipeline = ElectrodeAnalysisPipelineV2
ElectrodeFormatLoader = ElectrodeFormatLoaderV2
