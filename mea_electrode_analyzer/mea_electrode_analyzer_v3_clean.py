"""
MEA Electrode-Level Analyzer v3.0 Clean (Optimized & Enhanced)
----------------------------------------------------------------
v2.0 대비 주요 개선사항:
1. 필터링 로직 개선: min_pct_change (백분율 기반) 도입
2. 코드 최적화: 중복 제거, 효율성 향상
3. 시각화 개선: 일관된 색상 스키마, 향상된 레이아웃
4. 성능 향상: 더 빠른 데이터 처리, 메모리 효율성
5. 문서화 강화: 명확한 docstring, 사용 예시
6. 전극 반응 점수: BASE vs STIM ratio 기반 electrode 순위 매기기

핵심 기능:
- 24 wells × 16 electrodes (Axion Maestro) 전극 레벨 분석
- 백분율 기반 필터링으로 더 직관적인 선택
- 향상된 light response 분석
- Electrode별 response score 계산 및 순위화
- 종합 dashboard 및 상세 시각화
- Parquet 캐싱으로 빠른 재분석

Usage:
    from mea_electrode_analyzer_v3_clean import ElectrodeAnalysisPipeline, ElectrodeFilterConfig

    pipeline = ElectrodeAnalysisPipeline(
        input_dir=r"D:\MEAdata\electrode",
        output_dir=r"D:\MEAdata\output",
        n_workers=4,
        filter_config=ElectrodeFilterConfig(
            min_metric_ratio=0.5,
            min_pct_change=10.0,  # 10% 변화율
            min_fold_change=2.0
        )
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
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings('ignore')

# Progress bar (optional)
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


# =============================================================================
# UTILITIES
# =============================================================================

def timer(func):
    """성능 측정 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"  ⏱ {func.__name__}: {elapsed:.2f}s")
        return result
    return wrapper


class PerformanceMonitor:
    """성능 모니터링"""
    def __init__(self):
        self.timings = {}

    def record(self, stage_name: str, elapsed_time: float):
        self.timings[stage_name] = elapsed_time

    def print_summary(self):
        total = sum(self.timings.values())
        print('\n' + '='*80)
        print('PERFORMANCE SUMMARY')
        print('='*80)
        print(f"Total: {total:.2f}s")
        for stage, t in self.timings.items():
            pct = (t/total*100) if total > 0 else 0
            print(f"  {stage:40s}: {t:6.2f}s ({pct:5.1f}%)")
        print('='*80)


# Color scheme
COLORS = {
    'base': '#5DADE2',      # Sky blue
    'stim': '#EC7063',      # Coral red
    'positive': '#58D68D',  # Green
    'negative': '#EC7063',  # Red
    'neutral': '#85929E',   # Gray
}


# =============================================================================
# METRIC STANDARDIZATION
# =============================================================================

METRIC_MAPPING = {
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


def standardize_metric_name(name: str) -> str:
    """Metric 이름을 snake_case로 표준화"""
    if name in METRIC_MAPPING:
        return METRIC_MAPPING[name]
    # Fallback
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s


def extract_electrode_info(col_name: str) -> Tuple[Optional[str], Optional[str]]:
    """'A1_11' → ('A1', '11')"""
    m = re.match(r'^([A-D][1-6])_(\d{2})$', col_name)
    if not m:
        return None, None
    return m.group(1), m.group(2)


# =============================================================================
# DATA LOADING
# =============================================================================

@timer
def load_single_electrode_excel(path: str) -> pd.DataFrame:
    """단일 electrode Excel → long-format DataFrame"""
    file_path = Path(path)

    df_meta = pd.read_excel(file_path, sheet_name="Metadata")
    df_template = pd.read_excel(file_path, sheet_name="Template")
    df_well = pd.read_excel(file_path, sheet_name="Well_Info")

    meta = df_meta.iloc[0].to_dict()
    # Well_Info: Differentiation_Day = 플레이팅 시점의 분화일수
    diff_day_map = dict(zip(df_well["Well"], df_well["Differentiation_Day"]))
    # days_post_plating (이전 Plating_Day): 플레이팅 후 실험까지 경과일
    days_post_plating = meta.get("days_post_plating",
                                  meta.get("Plating DAY",
                                  meta.get("PLATING_DAY", np.nan)))

    # 전극 컬럼 찾기
    electrode_cols = [c for c in df_template.columns
                     if c not in ("Metric", "Unit", "Condition")
                     and extract_electrode_info(c)[0] is not None]

    print(f"[LOAD] {file_path.name}: {len(electrode_cols)} electrodes")

    rows = []
    for _, row in df_template.iterrows():
        metric_std = standardize_metric_name(row["Metric"])

        for col in electrode_cols:
            val = row[col]
            if pd.isna(val):
                continue

            well, elec_idx = extract_electrode_info(col)
            # Differentiation_Day = 플레이팅 시점의 분화일수
            differentiation_day = diff_day_map.get(well, np.nan)
            # DIV = Differentiation_Day + days_post_plating (실험당일 실제 분화일수)
            div = (differentiation_day + days_post_plating
                   if pd.notna(differentiation_day) and pd.notna(days_post_plating)
                   else np.nan)

            rows.append({
                "File": file_path.stem,
                "Plate_ID": meta.get("PLATE_ID", "UNKNOWN"),
                "Well": well,
                "Electrode_ID": col,
                "Electrode_Index": elec_idx,
                "Metric": metric_std,
                "Metric_Raw": row["Metric"],
                "Value": float(val),
                "BASE_STIM": meta.get("BASE_STIM", "UNKNOWN"),
                "TIME_START": meta.get("TIME_START", meta.get("TIME_START(sec)", 0)),
                "TIME_DURATION_SEC": meta.get("TIME_DURATION(sec)",
                                             meta.get("TIME_DURATION_SEC", 0)),
                "days_post_plating": days_post_plating,
                "Differentiation_Day": differentiation_day,
                "DIV": div,  # 실험당일 분화일수 (Differentiation_Day + days_post_plating)
                "LIGHT_CODE": meta.get("LIGHT_CODE", "UNKNOWN"),
                "INTENSITY_PCT": meta.get("INTENSITY(%)",
                                         meta.get("INTENSITY_PCT", 0)),
                "EXP_TYPE": meta.get("EXP_TYPE", "UNKNOWN"),
                "DRUG": meta.get("DRUG", "NONE"),
                "CONCENTRATION_mM": meta.get("CONCENTRATION (mM)",
                                            meta.get("CONCENTRATION_MM", 0)),
            })

    return pd.DataFrame(rows)


class ElectrodeFormatLoader:
    """Excel 파일 로더 (캐싱 지원)"""

    def __init__(self, input_dir: str, use_cache: bool = True):
        self.input_dir = Path(input_dir)
        self.use_cache = use_cache
        self.cache_dir = self.input_dir / '.cache'
        if use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @timer
    def load_all(self) -> pd.DataFrame:
        """모든 Excel 파일 로드 (캐싱 지원)"""
        cache_file = self.cache_dir / 'electrode_all_long.parquet'

        if self.use_cache and cache_file.exists():
            print(f"[LOAD] Loading from cache: {cache_file.name}")
            df_all = pd.read_parquet(cache_file)
            print(f"[LOAD] Cached: {len(df_all)} rows, "
                  f"{df_all['Electrode_ID'].nunique()} electrodes")
            return df_all

        files = [f for f in self.input_dir.glob("*.xlsx")
                if not f.name.startswith("~$")]

        if not files:
            print(f"[LOAD] No files in {self.input_dir}")
            return pd.DataFrame()

        file_iter = tqdm(files, desc="Loading") if HAS_TQDM else files
        all_rows = []

        for f in file_iter:
            try:
                all_rows.append(load_single_electrode_excel(str(f)))
            except Exception as e:
                print(f"[WARN] Failed {f.name}: {e}")

        if not all_rows:
            return pd.DataFrame()

        df_all = pd.concat(all_rows, ignore_index=True)
        print(f"[LOAD] Combined: {len(df_all)} rows, "
              f"{df_all['Electrode_ID'].nunique()} electrodes, "
              f"{df_all['Metric'].nunique()} metrics")

        if self.use_cache:
            print(f"[LOAD] Saving cache: {cache_file.name}")
            df_all.to_parquet(cache_file, index=False)

        return df_all


# =============================================================================
# FILTERING
# =============================================================================

@dataclass
class ElectrodeFilterConfig:
    """
    전극 선택 기준

    Parameters:
    -----------
    min_metric_ratio : float (default=0.5)
        STIM에서 최소 metric 완전성 비율 (0.5 = 50%)
    min_pct_change : float (default=10.0)
        BASE 대비 최소 변화율 (10.0 = 10%)
    min_fold_change : float (default=2.0)
        BASE 대비 최소 배수 변화 (2.0 = 2배)

    선택 조건:
        [min_metric_ratio 만족] AND
        ([min_pct_change 만족] OR [min_fold_change 만족])
    """
    min_metric_ratio: float = 0.5
    min_pct_change: float = 10.0
    min_fold_change: float = 2.0


@timer
def filter_electrodes(
    df_long: pd.DataFrame,
    config: ElectrodeFilterConfig,
    verbose: bool = True,
) -> Tuple[Optional[pd.DataFrame], pd.DataFrame]:
    """
    전극 필터링 (v3.0 - 백분율 기반)

    Returns:
    --------
    selected_stats : DataFrame
        선택된 전극 통계
    df_filtered : DataFrame
        선택된 전극의 모든 데이터
    """
    if df_long.empty:
        if verbose:
            print("[FILTER] Empty DataFrame")
        return None, df_long.iloc[0:0]

    df = df_long.copy()
    total_metrics = df["Metric"].nunique()

    if verbose:
        print(f"[FILTER] Total metrics: {total_metrics}")

    key_cols = ["Plate_ID", "Well", "Electrode_ID", "Electrode_Index",
                "LIGHT_CODE", "INTENSITY_PCT", "EXP_TYPE", "DRUG"]

    # (1) STIM metric presence
    stim_mask = (df["BASE_STIM"] == "STIM") & df["Value"].notna()
    stim_nonan = df[stim_mask]

    if stim_nonan.empty:
        if verbose:
            print("[FILTER] No STIM data")
        return None, df.iloc[0:0]

    stim_counts = (stim_nonan.groupby(key_cols)["Metric"]
                   .nunique()
                   .reset_index()
                   .rename(columns={"Metric": "n_metrics_stim"}))
    stim_counts["metric_ratio"] = stim_counts["n_metrics_stim"] / total_metrics

    # (2) BASE vs STIM comparison
    base_mask = (df["BASE_STIM"] == "BASE") & (df["Metric"] == "number_of_spikes")
    stim_mask = (df["BASE_STIM"] == "STIM") & (df["Metric"] == "number_of_spikes")

    spikes_base = (df[base_mask].groupby(key_cols)["Value"]
                   .mean().reset_index()
                   .rename(columns={"Value": "spikes_base"}))
    spikes_stim = (df[stim_mask].groupby(key_cols)["Value"]
                   .mean().reset_index()
                   .rename(columns={"Value": "spikes_stim"}))

    merged = (stim_counts
              .merge(spikes_base, on=key_cols, how="left")
              .merge(spikes_stim, on=key_cols, how="left"))
    merged = merged.dropna(subset=["spikes_base", "spikes_stim"])

    # (3) Calculate metrics
    # 개선: eps를 1e-3으로 상향하여 극단적 ratio 방지
    eps = 1e-3
    merged["abs_diff"] = (merged["spikes_stim"] - merged["spikes_base"]).abs()
    merged["pct_change"] = ((merged["spikes_stim"] - merged["spikes_base"]) /
                           (merged["spikes_base"] + eps) * 100)
    merged["fold_change"] = (merged["spikes_stim"] + eps) / (merged["spikes_base"] + eps)
    # log2 fold change 추가 (대칭적 표현)
    merged["log2_fold_change"] = np.log2(merged["fold_change"])

    # (4) Filter conditions
    cond_metrics = merged["metric_ratio"] >= config.min_metric_ratio
    cond_pct = merged["pct_change"].abs() >= config.min_pct_change
    # 개선: 양방향 fold change 필터 (증가 또는 감소 모두 체크)
    cond_fc_increase = merged["fold_change"] >= config.min_fold_change
    cond_fc_decrease = merged["fold_change"] <= (1.0 / config.min_fold_change)
    cond_fc = cond_fc_increase | cond_fc_decrease

    merged["selected"] = cond_metrics & (cond_pct | cond_fc)
    selected_stats = merged[merged["selected"]].copy()

    if verbose:
        print(f"[FILTER] Sufficient metrics: {cond_metrics.sum()}/{len(merged)}")
        print(f"[FILTER] Selected electrodes: {len(selected_stats)}")

    # (5) Extract selected electrode data
    if selected_stats.empty:
        df_filtered = df.iloc[0:0]
    else:
        df_flagged = df.merge(selected_stats[key_cols + ["selected"]],
                             on=key_cols, how="left")
        df_filtered = df_flagged[df_flagged["selected"].fillna(False)].drop(columns=["selected"])

    return selected_stats, df_filtered


# =============================================================================
# VISUALIZATIONS
# =============================================================================

class ElectrodeVisualizer:
    """전극 시각화 (v3.0 - 개선된 디자인)"""

    def __init__(self, df_all: pd.DataFrame, df_selected: pd.DataFrame,
                 selected_stats: pd.DataFrame, output_dir: Path):
        self.df_all = df_all
        self.df_selected = df_selected
        self.selected_stats = selected_stats
        self.output_dir = Path(output_dir) / 'visualizations'
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Set style
        sns.set_palette("husl")
        plt.rcParams['font.size'] = 10
        plt.rcParams['axes.labelweight'] = 'bold'

    @timer
    def create_all(self):
        """모든 시각화 생성 (v2의 모든 시각화 유지)"""
        print("\n[VIZ] Creating visualizations...")

        funcs = [
            # Basic visualizations
            self.plot_electrode_selection_overview,
            self.plot_electrode_heatmap,
            self.plot_electrode_distribution,
            self.plot_spike_comparison,
            self.plot_electrode_spatial_map,
            self.plot_metric_completeness,
            # Light_code specific visualizations
            self.plot_light_code_comprehensive_analysis,
            self.plot_base_vs_stim_by_light_code,
            self.plot_key_metrics_by_light_code,
            self.plot_light_code_heatmap,
            self.plot_isi_analysis,
            self.plot_burst_detailed_analysis,
        ]

        for func in funcs:
            try:
                func()
            except Exception as e:
                print(f"  ⚠ {func.__name__}: {e}")

        print("  ✓ All visualizations complete")

    def plot_electrode_selection_overview(self):
        """선택 개요"""
        if self.selected_stats is None or self.selected_stats.empty:
            return

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 1. Metric ratio
        ax = axes[0, 0]
        ax.hist(self.selected_stats['metric_ratio'], bins=20,
               edgecolor='black', alpha=0.7, color=COLORS['positive'])
        ax.axvline(self.selected_stats['metric_ratio'].mean(),
                  color='red', linestyle='--',
                  label=f'Mean: {self.selected_stats["metric_ratio"].mean():.2f}')
        ax.set_xlabel('Metric Ratio')
        ax.set_ylabel('Count')
        ax.set_title('Metric Completeness Distribution')
        ax.legend()
        ax.grid(alpha=0.3)

        # 2. Percentage change
        ax = axes[0, 1]
        ax.hist(self.selected_stats['pct_change'], bins=20,
               edgecolor='black', alpha=0.7, color=COLORS['stim'])
        ax.axvline(self.selected_stats['pct_change'].mean(),
                  color='red', linestyle='--',
                  label=f'Mean: {self.selected_stats["pct_change"].mean():.1f}%')
        ax.set_xlabel('Percentage Change (%)')
        ax.set_ylabel('Count')
        ax.set_title('Response Magnitude (% Change)')
        ax.legend()
        ax.grid(alpha=0.3)

        # 3. Fold change
        ax = axes[1, 0]
        fc_clip = np.clip(self.selected_stats['fold_change'], 0, 10)
        ax.hist(fc_clip, bins=20, edgecolor='black', alpha=0.7,
               color=COLORS['base'])
        ax.axvline(fc_clip.mean(), color='red', linestyle='--',
                  label=f'Mean: {fc_clip.mean():.2f}')
        ax.set_xlabel('Fold Change (clipped at 10)')
        ax.set_ylabel('Count')
        ax.set_title('Response Fold Change')
        ax.legend()
        ax.grid(alpha=0.3)

        # 4. Per well
        ax = axes[1, 1]
        well_counts = self.selected_stats['Well'].value_counts().sort_index()
        ax.bar(range(len(well_counts)), well_counts.values,
              edgecolor='black', alpha=0.7, color=COLORS['neutral'])
        ax.set_xticks(range(len(well_counts)))
        ax.set_xticklabels(well_counts.index, rotation=45, ha='right')
        ax.set_xlabel('Well')
        ax.set_ylabel('Selected Electrodes')
        ax.set_title('Selected Electrodes per Well')
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'selection_overview.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_light_code_heatmap(self):
        """Metric 히트맵 (Light_code × Metric)"""
        if self.df_selected.empty or 'LIGHT_CODE' not in self.df_selected.columns:
            return

        stim_data = self.df_selected[self.df_selected['BASE_STIM'] == 'STIM']
        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz',
                      'burst_frequency_hz', 'spikes_per_burst_avg']
        available = [m for m in key_metrics if m in stim_data['Metric'].unique()]

        if not available:
            return

        filtered = stim_data[stim_data['Metric'].isin(available)]
        pivot = filtered.pivot_table(index='LIGHT_CODE', columns='Metric',
                                     values='Value', aggfunc='mean')

        if pivot.empty:
            return

        # Z-score normalization
        pivot_norm = (pivot - pivot.mean()) / pivot.std()

        fig, ax = plt.subplots(figsize=(max(10, len(pivot.columns)*1.5),
                                        max(6, len(pivot.index)*0.8)))

        sns.heatmap(pivot_norm, annot=True, fmt='.2f', cmap='RdYlGn', center=0,
                   cbar_kws={'label': 'Z-score'}, linewidths=1,
                   linecolor='white', ax=ax, annot_kws={'size': 9})

        ax.set_title('Light Code × Metrics Heatmap\n(Z-score normalized, STIM)',
                    fontweight='bold', fontsize=14, pad=15)
        ax.set_xlabel('Metrics', fontweight='bold')
        ax.set_ylabel('Light Code', fontweight='bold')

        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'metrics_heatmap.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_electrode_spatial_map(self):
        """24-well 공간 분포"""
        if self.selected_stats is None or self.selected_stats.empty:
            return

        rows = ['A', 'B', 'C', 'D']
        cols = [1, 2, 3, 4, 5, 6]

        well_counts = self.selected_stats['Well'].value_counts()
        matrix = np.zeros((len(rows), len(cols)))

        for well, count in well_counts.items():
            if len(well) >= 2 and well[0] in rows:
                row_idx = rows.index(well[0])
                col_idx = cols.index(int(well[1]))
                matrix[row_idx, col_idx] = count

        fig, ax = plt.subplots(figsize=(10, 6))
        im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')

        ax.set_xticks(range(len(cols)))
        ax.set_yticks(range(len(rows)))
        ax.set_xticklabels(cols)
        ax.set_yticklabels(rows)

        for i in range(len(rows)):
            for j in range(len(cols)):
                ax.text(j, i, int(matrix[i, j]), ha="center", va="center",
                       color="black", fontweight='bold', fontsize=11)

        ax.set_title('Selected Electrodes - Spatial Distribution\n(24-well plate)',
                    fontweight='bold', fontsize=14)
        ax.set_xlabel('Column', fontweight='bold')
        ax.set_ylabel('Row', fontweight='bold')

        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('# Selected Electrodes', fontweight='bold')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'spatial_distribution.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_electrode_heatmap(self):
        """전극별 metric 히트맵 (Electrode_ID × Metric)"""
        if self.df_selected.empty:
            return

        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'number_of_bursts',
                      'burst_frequency_hz', 'spikes_per_burst_avg']
        available = [m for m in key_metrics if m in self.df_selected['Metric'].unique()]

        if not available:
            return

        stim_data = self.df_selected[self.df_selected['BASE_STIM'] == 'STIM']
        pivot = stim_data[stim_data['Metric'].isin(available)].pivot_table(
            index='Electrode_ID', columns='Metric', values='Value', aggfunc='mean')

        if pivot.empty:
            return

        # Z-score normalization
        pivot_norm = (pivot - pivot.mean()) / pivot.std()

        fig, ax = plt.subplots(figsize=(max(12, len(pivot.columns)*1.5),
                                        max(10, len(pivot.index)*0.3)))

        sns.heatmap(pivot_norm, annot=False, cmap='RdYlGn', center=0,
                   cbar_kws={'label': 'Z-score'}, linewidths=0.5,
                   linecolor='gray', ax=ax)

        ax.set_title('Selected Electrodes - Key Metrics Heatmap\n(Z-score normalized)',
                    fontweight='bold', fontsize=14, pad=15)
        ax.set_xlabel('Metrics', fontweight='bold')
        ax.set_ylabel('Electrode ID', fontweight='bold')

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(self.output_dir / 'electrode_metrics_heatmap.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_electrode_distribution(self):
        """전극별 주요 metric 분포 (박스플롯)"""
        if self.df_selected.empty:
            return

        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
        available = [m for m in key_metrics if m in self.df_selected['Metric'].unique()]

        if not available:
            return

        n_metrics = len(available)
        fig, axes = plt.subplots(1, n_metrics, figsize=(6*n_metrics, 6))
        if n_metrics == 1:
            axes = [axes]

        for idx, metric in enumerate(available):
            ax = axes[idx]
            metric_data = self.df_selected[
                (self.df_selected['Metric'] == metric) &
                (self.df_selected['BASE_STIM'] == 'STIM')
            ]

            if metric_data.empty:
                continue

            wells = sorted(metric_data['Well'].unique())
            data_by_well = [metric_data[metric_data['Well'] == w]['Value'].values
                           for w in wells]

            bp = ax.boxplot(data_by_well, labels=wells, patch_artist=True)

            colors_list = plt.cm.Set3(np.linspace(0, 1, len(bp['boxes'])))
            for patch, color in zip(bp['boxes'], colors_list):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)

            ax.set_xlabel('Well', fontweight='bold')
            ax.set_ylabel('Value', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}\n(STIM, by Well)',
                        fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'electrode_distribution_boxplots.png',
                   dpi=300, bbox_inches='tight')
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
                   alpha=0.6, s=50, edgecolor='black', c=COLORS['stim'])

        max_val = max(self.selected_stats['spikes_base'].max(),
                     self.selected_stats['spikes_stim'].max())
        ax1.plot([0, max_val], [0, max_val], 'r--', label='y=x (no change)')

        ax1.set_xlabel('Spikes (BASE)', fontweight='bold')
        ax1.set_ylabel('Spikes (STIM)', fontweight='bold')
        ax1.set_title('BASE vs STIM Spike Count\n(Selected Electrodes)',
                     fontweight='bold')
        ax1.legend()
        ax1.grid(alpha=0.3)

        # 2. Difference per well
        ax2 = axes[1]
        well_diff = self.selected_stats.groupby('Well')['abs_diff'].mean().sort_values(ascending=False)

        ax2.bar(range(len(well_diff)), well_diff.values,
               edgecolor='black', alpha=0.7, color=COLORS['stim'])
        ax2.set_xticks(range(len(well_diff)))
        ax2.set_xticklabels(well_diff.index, rotation=45, ha='right')
        ax2.set_xlabel('Well', fontweight='bold')
        ax2.set_ylabel('Mean Absolute Difference', fontweight='bold')
        ax2.set_title('Response Magnitude by Well\n(Selected Electrodes)',
                     fontweight='bold')
        ax2.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'spike_comparison.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_metric_completeness(self):
        """Metric 완전성 분석"""
        if self.df_all.empty:
            return

        stim_data = self.df_all[self.df_all['BASE_STIM'] == 'STIM']
        electrode_metrics = stim_data.groupby('Electrode_ID')['Metric'].nunique()

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # 1. Histogram
        ax1 = axes[0]
        ax1.hist(electrode_metrics.values, bins=20, edgecolor='black',
                alpha=0.7, color=COLORS['base'])
        ax1.axvline(electrode_metrics.mean(), color='red', linestyle='--',
                   label=f'Mean: {electrode_metrics.mean():.1f}')
        ax1.set_xlabel('Number of Metrics (per electrode)', fontweight='bold')
        ax1.set_ylabel('Frequency', fontweight='bold')
        ax1.set_title('Metric Completeness Distribution\n(STIM data)',
                     fontweight='bold')
        ax1.legend()
        ax1.grid(alpha=0.3)

        # 2. Top metrics
        ax2 = axes[1]
        metric_counts = stim_data['Metric'].value_counts().head(15)

        ax2.barh(range(len(metric_counts)), metric_counts.values,
                edgecolor='black', alpha=0.7, color=COLORS['positive'])
        ax2.set_yticks(range(len(metric_counts)))
        ax2.set_yticklabels([m.replace('_', ' ').title()
                            for m in metric_counts.index])
        ax2.set_xlabel('Number of Data Points', fontweight='bold')
        ax2.set_title('Top 15 Metrics by Data Availability\n(STIM)',
                     fontweight='bold')
        ax2.grid(axis='x', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'metric_completeness.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_light_code_comprehensive_analysis(self):
        """Light_code별 종합 분석 (4개 주요 metric)"""
        if self.df_selected.empty or 'LIGHT_CODE' not in self.df_selected.columns:
            return

        key_metrics = {
            'number_of_spikes': 'Number of Spikes',
            'mean_firing_rate_hz': 'Mean Firing Rate (Hz)',
            'burst_frequency_hz': 'Burst Frequency (Hz)',
            'burst_duration_avg_s': 'Burst Duration (s)'
        }

        stim_data = self.df_selected[self.df_selected['BASE_STIM'] == 'STIM']
        available = {k: v for k, v in key_metrics.items()
                    if k in stim_data['Metric'].unique()}

        if not available:
            return

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        axes = axes.flatten()

        for idx, (metric_key, metric_name) in enumerate(available.items()):
            if idx >= 4:
                break

            ax = axes[idx]
            metric_data = stim_data[stim_data['Metric'] == metric_key]

            if metric_data.empty:
                ax.text(0.5, 0.5, f'No data for {metric_name}',
                       ha='center', va='center', transform=ax.transAxes)
                continue

            summary = metric_data.groupby('LIGHT_CODE')['Value'].agg(
                ['mean', 'std']).reset_index()
            summary = summary.sort_values('LIGHT_CODE')

            x_pos = np.arange(len(summary))
            colors_list = plt.cm.Set3(np.linspace(0, 1, len(summary)))

            bars = ax.bar(x_pos, summary['mean'], yerr=summary['std'],
                         capsize=5, alpha=0.7, edgecolor='black', linewidth=1.5,
                         color=colors_list)

            ax.set_xticks(x_pos)
            ax.set_xticklabels(summary['LIGHT_CODE'], rotation=45, ha='right')
            ax.set_xlabel('Light Code', fontweight='bold', fontsize=11)
            ax.set_ylabel('Value', fontweight='bold', fontsize=11)
            ax.set_title(f'{metric_name}\nby Light Code (STIM)',
                        fontweight='bold', fontsize=12)
            ax.grid(axis='y', alpha=0.3)

            for i, (m, s) in enumerate(zip(summary['mean'], summary['std'])):
                ax.text(i, m + s, f'{m:.1f}', ha='center', va='bottom', fontsize=9)

        for idx in range(len(available), 4):
            axes[idx].set_visible(False)

        plt.suptitle('Comprehensive Analysis by Light Code\n(Selected Electrodes, STIM)',
                    fontweight='bold', fontsize=14, y=0.995)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'light_code_comprehensive_analysis.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_base_vs_stim_by_light_code(self):
        """BASE vs STIM 비교 (Light_code별)"""
        if self.df_selected.empty or 'LIGHT_CODE' not in self.df_selected.columns:
            return

        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz']
        available = [m for m in key_metrics if m in self.df_selected['Metric'].unique()]

        if not available:
            return

        n_metrics = len(available)
        fig, axes = plt.subplots(1, n_metrics, figsize=(8*n_metrics, 6))
        if n_metrics == 1:
            axes = [axes]

        for idx, metric in enumerate(available):
            ax = axes[idx]
            metric_data = self.df_selected[self.df_selected['Metric'] == metric]

            base_data = metric_data[metric_data['BASE_STIM'] == 'BASE']
            stim_data = metric_data[metric_data['BASE_STIM'] == 'STIM']

            base_means = base_data.groupby('LIGHT_CODE')['Value'].mean()
            stim_means = stim_data.groupby('LIGHT_CODE')['Value'].mean()

            all_light_codes = sorted(set(base_means.index) | set(stim_means.index))
            base_vals = [base_means.get(lc, 0) for lc in all_light_codes]
            stim_vals = [stim_means.get(lc, 0) for lc in all_light_codes]

            x_pos = np.arange(len(all_light_codes))
            width = 0.35

            ax.bar(x_pos - width/2, base_vals, width, label='BASE',
                  alpha=0.8, edgecolor='black', color=COLORS['base'])
            ax.bar(x_pos + width/2, stim_vals, width, label='STIM',
                  alpha=0.8, edgecolor='black', color=COLORS['stim'])

            ax.set_xticks(x_pos)
            ax.set_xticklabels(all_light_codes, rotation=45, ha='right')
            ax.set_xlabel('Light Code', fontweight='bold')
            ax.set_ylabel('Mean Value', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}\nBASE vs STIM by Light Code',
                        fontweight='bold')
            ax.legend()
            ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'base_vs_stim_by_light_code.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_key_metrics_by_light_code(self):
        """주요 metric들의 light_code별 박스플롯"""
        if self.df_selected.empty or 'LIGHT_CODE' not in self.df_selected.columns:
            return

        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
        available = [m for m in key_metrics if m in self.df_selected['Metric'].unique()]

        if not available:
            return

        stim_data = self.df_selected[self.df_selected['BASE_STIM'] == 'STIM']
        light_codes = sorted(stim_data['LIGHT_CODE'].unique())

        n_metrics = len(available)
        fig, axes = plt.subplots(1, n_metrics, figsize=(6*n_metrics, 6))
        if n_metrics == 1:
            axes = [axes]

        for idx, metric in enumerate(available):
            ax = axes[idx]
            metric_data = stim_data[stim_data['Metric'] == metric]

            if metric_data.empty:
                continue

            data_by_light = [metric_data[metric_data['LIGHT_CODE'] == lc]['Value'].values
                            for lc in light_codes]

            bp = ax.boxplot(data_by_light, labels=light_codes, patch_artist=True,
                           showmeans=True, meanprops=dict(marker='D',
                                                         markerfacecolor='red',
                                                         markeredgecolor='red'))

            colors_list = plt.cm.Set3(np.linspace(0, 1, len(bp['boxes'])))
            for patch, color in zip(bp['boxes'], colors_list):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)

            ax.set_xlabel('Light Code', fontweight='bold')
            ax.set_ylabel('Value', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}\nDistribution by Light Code (STIM)',
                        fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'key_metrics_by_light_code_boxplots.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_isi_analysis(self):
        """ISI (Inter-Spike Interval) 상세 분석"""
        if self.df_selected.empty:
            return

        isi_metrics = [m for m in self.df_selected['Metric'].unique()
                      if 'isi' in m.lower() or 'interval' in m.lower()]

        if not isi_metrics:
            return

        stim_data = self.df_selected[self.df_selected['BASE_STIM'] == 'STIM']
        isi_data = stim_data[stim_data['Metric'].isin(isi_metrics)]

        if isi_data.empty:
            return

        n_metrics = min(len(isi_metrics), 6)
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        axes = axes.flatten()

        for idx, metric in enumerate(isi_metrics[:6]):
            ax = axes[idx]
            metric_data = isi_data[isi_data['Metric'] == metric]

            if 'LIGHT_CODE' in metric_data.columns:
                light_codes = sorted(metric_data['LIGHT_CODE'].unique())
                data_by_light = [metric_data[metric_data['LIGHT_CODE'] == lc]['Value'].values
                               for lc in light_codes]

                bp = ax.boxplot(data_by_light, labels=light_codes, patch_artist=True)

                colors_list = plt.cm.Pastel1(np.linspace(0, 1, len(bp['boxes'])))
                for patch, color in zip(bp['boxes'], colors_list):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.8)

                ax.set_xlabel('Light Code', fontweight='bold')
            else:
                ax.hist(metric_data['Value'].dropna(), bins=20,
                       edgecolor='black', alpha=0.7, color=COLORS['base'])
                ax.set_xlabel('Value', fontweight='bold')

            ax.set_ylabel('Value', fontweight='bold')
            ax.set_title(metric.replace('_', ' ').title(), fontweight='bold', fontsize=10)
            ax.grid(alpha=0.3)
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        for idx in range(len(isi_metrics), 6):
            axes[idx].set_visible(False)

        plt.suptitle('ISI (Inter-Spike Interval) Detailed Analysis\n(STIM only)',
                    fontweight='bold', fontsize=14)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'isi_detailed_analysis.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_burst_detailed_analysis(self):
        """Burst 상세 분석"""
        if self.df_selected.empty:
            return

        burst_metrics = [
            'number_of_bursts', 'burst_frequency_hz', 'burst_duration_avg_s',
            'spikes_per_burst_avg', 'inter_burst_interval_avg_s', 'burst_percentage'
        ]

        available = [m for m in burst_metrics
                    if m in self.df_selected['Metric'].unique()]

        if not available:
            return

        stim_data = self.df_selected[self.df_selected['BASE_STIM'] == 'STIM']

        n_metrics = min(len(available), 6)
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        axes = axes.flatten()

        for idx, metric in enumerate(available[:6]):
            ax = axes[idx]
            metric_data = stim_data[stim_data['Metric'] == metric]

            if metric_data.empty:
                ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                       transform=ax.transAxes)
                continue

            if 'LIGHT_CODE' in metric_data.columns:
                light_codes = sorted(metric_data['LIGHT_CODE'].unique())

                summary = metric_data.groupby('LIGHT_CODE')['Value'].agg(
                    ['mean', 'std']).reset_index()
                summary = summary.sort_values('LIGHT_CODE')

                x_pos = np.arange(len(summary))
                colors_list = plt.cm.Set2(np.linspace(0, 1, len(summary)))

                bars = ax.bar(x_pos, summary['mean'], yerr=summary['std'],
                             capsize=5, alpha=0.7, edgecolor='black',
                             color=colors_list)

                ax.set_xticks(x_pos)
                ax.set_xticklabels(summary['LIGHT_CODE'], rotation=45, ha='right')
                ax.set_xlabel('Light Code', fontweight='bold')
            else:
                well_means = metric_data.groupby('Well')['Value'].mean().sort_values(ascending=False)
                ax.bar(range(len(well_means)), well_means.values,
                      alpha=0.7, edgecolor='black', color=COLORS['stim'])
                ax.set_xticks(range(len(well_means)))
                ax.set_xticklabels(well_means.index, rotation=45, ha='right')
                ax.set_xlabel('Well', fontweight='bold')

            ax.set_ylabel('Value', fontweight='bold')
            ax.set_title(metric.replace('_', ' ').title(), fontweight='bold', fontsize=10)
            ax.grid(axis='y', alpha=0.3)

        for idx in range(len(available), 6):
            axes[idx].set_visible(False)

        plt.suptitle('Burst Properties Detailed Analysis\n(STIM only)',
                    fontweight='bold', fontsize=14)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'burst_detailed_analysis.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)


# =============================================================================
# LIGHT RESPONSE ANALYZER
# =============================================================================

class LightResponseAnalyzer:
    """Light response 분석기 (v3.0)"""

    def __init__(self, df_selected: pd.DataFrame, output_dir: Path):
        self.df_selected = df_selected
        self.output_dir = Path(output_dir) / 'light_response'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.response_data = None

    @timer
    def calculate_responses(self, filter_positive: bool = True):
        """Response 계산 (STIM - BASE)"""
        print("\n[LIGHT] Calculating responses...")

        if self.df_selected.empty:
            print("  ⚠ No data")
            return self

        if 'LIGHT_CODE' not in self.df_selected.columns:
            print("  ⚠ No LIGHT_CODE")
            return self

        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
        available = [m for m in key_metrics if m in self.df_selected['Metric'].unique()]

        if not available:
            print("  ⚠ No key metrics")
            return self

        responses = []

        for metric in available:
            metric_data = self.df_selected[self.df_selected['Metric'] == metric]
            base_data = metric_data[metric_data['BASE_STIM'] == 'BASE']
            stim_data = metric_data[metric_data['BASE_STIM'] == 'STIM']

            for _, stim_row in stim_data.iterrows():
                electrode_id = stim_row['Electrode_ID']
                light_code = stim_row['LIGHT_CODE']

                base_row = base_data[
                    (base_data['Electrode_ID'] == electrode_id) &
                    (base_data['LIGHT_CODE'] == light_code)
                ]

                if not base_row.empty:
                    base_val = base_row['Value'].iloc[0]
                    stim_val = stim_row['Value']
                    response = stim_val - base_val
                    fold_change = (stim_val + 1e-6) / (base_val + 1e-6)

                    if filter_positive and response <= 0:
                        continue

                    responses.append({
                        'Electrode_ID': electrode_id,
                        'Well': stim_row['Well'],
                        'LIGHT_CODE': light_code,
                        'Metric': metric,
                        'BASE_Value': base_val,
                        'STIM_Value': stim_val,
                        'Response': response,
                        'Fold_Change': fold_change,
                    })

        self.response_data = pd.DataFrame(responses)

        if not self.response_data.empty:
            csv_path = self.output_dir / 'light_response_data.csv'
            self.response_data.to_csv(csv_path, index=False)
            print(f"  ✓ Responses: {len(self.response_data)}")
            if filter_positive:
                print(f"  ✓ Filtered: positive only (STIM > BASE)")

        return self

    @timer
    def create_visualizations(self):
        """Response 시각화"""
        if self.response_data is None or self.response_data.empty:
            print("  ⚠ No response data")
            return self

        print("\n[LIGHT] Creating visualizations...")

        funcs = [
            self._plot_base_vs_stim_by_electrode,
            self._plot_response_summary,
        ]

        for func in funcs:
            try:
                func()
            except Exception as e:
                print(f"  ⚠ {func.__name__}: {e}")

        print("  ✓ Light response visualizations complete")
        return self

    def _plot_base_vs_stim_by_electrode(self):
        """Electrode별 BASE vs STIM"""
        light_codes = sorted(self.response_data['LIGHT_CODE'].unique())
        metrics = sorted(self.response_data['Metric'].unique())

        for metric in metrics:
            metric_data = self.response_data[self.response_data['Metric'] == metric]

            for light_code in light_codes:
                light_data = metric_data[metric_data['LIGHT_CODE'] == light_code]

                if light_data.empty:
                    continue

                light_data = light_data.sort_values('Electrode_ID')

                fig, ax = plt.subplots(figsize=(max(14, len(light_data)*0.4), 6))

                x_pos = np.arange(len(light_data))
                width = 0.35

                ax.bar(x_pos - width/2, light_data['BASE_Value'], width,
                      label='BASE', alpha=0.8, edgecolor='black',
                      color=COLORS['base'])
                ax.bar(x_pos + width/2, light_data['STIM_Value'], width,
                      label='STIM', alpha=0.8, edgecolor='black',
                      color=COLORS['stim'])

                ax.set_xticks(x_pos)
                ax.set_xticklabels(light_data['Electrode_ID'],
                                  rotation=90, ha='right', fontsize=8)
                ax.set_xlabel('Electrode ID')
                ax.set_ylabel(metric.replace('_', ' ').title())
                ax.set_title(f'BASE vs STIM by Electrode\n'
                           f'{metric.replace("_", " ").title()} - '
                           f'Light Code: {light_code}',
                           fontweight='bold')
                ax.legend(loc='upper right')
                ax.grid(axis='y', alpha=0.3)

                plt.tight_layout()
                filename = f'base_vs_stim_{metric}_{light_code}.png'
                plt.savefig(self.output_dir / filename, dpi=300, bbox_inches='tight')
                plt.close(fig)

    def _plot_response_summary(self):
        """Light_code별 response 요약"""
        metrics = sorted(self.response_data['Metric'].unique())
        n_metrics = len(metrics)

        fig, axes = plt.subplots(1, n_metrics, figsize=(7*n_metrics, 6))
        if n_metrics == 1:
            axes = [axes]

        for idx, metric in enumerate(metrics):
            ax = axes[idx]
            metric_data = self.response_data[self.response_data['Metric'] == metric]

            summary = metric_data.groupby('LIGHT_CODE')['Response'].agg(
                ['mean', 'std', 'count']).reset_index()
            summary['sem'] = summary['std'] / np.sqrt(summary['count'])
            summary = summary.sort_values('LIGHT_CODE')

            x_pos = np.arange(len(summary))

            ax.bar(x_pos, summary['mean'], yerr=summary['sem'],
                  capsize=5, alpha=0.7, edgecolor='black',
                  color=COLORS['positive'])

            ax.set_xticks(x_pos)
            ax.set_xticklabels(summary['LIGHT_CODE'], rotation=45, ha='right')
            ax.set_xlabel('Light Code')
            ax.set_ylabel('Mean Response ± SEM')
            ax.set_title(f'{metric.replace("_", " ").title()}\n'
                        f'(Positive Responses Only)',
                        fontweight='bold')
            ax.grid(axis='y', alpha=0.3)

            # Labels
            for i, (m, s) in enumerate(zip(summary['mean'], summary['sem'])):
                ax.text(i, m + s, f'{m:.1f}±{s:.1f}',
                       ha='center', va='bottom', fontsize=8)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'response_summary.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)


# =============================================================================
# ELECTRODE RESPONSE SCORER
# =============================================================================

class ElectrodeResponseScorer:
    """
    Electrode별 Light Response Score 계산 및 순위 매기기

    각 electrode에서 BASE 대비 STIM의 비율(ratio)을 계산하여
    light response가 높은 electrode를 식별합니다.
    """

    def __init__(self, df_all: pd.DataFrame, output_dir: Path):
        self.df_all = df_all
        self.output_dir = Path(output_dir) / 'electrode_scores'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scores_df = None

    @timer
    def calculate_scores(self, metrics_weights: Optional[dict] = None):
        """
        Electrode별 response score 계산

        Parameters:
        -----------
        metrics_weights : dict
            각 metric의 가중치. 기본값:
            {
                'number_of_spikes': 0.4,
                'mean_firing_rate_hz': 0.3,
                'burst_frequency_hz': 0.3
            }
        """
        print("\n[SCORER] Calculating electrode response scores...")

        if self.df_all.empty:
            print("  ⚠ No data")
            return self

        # 기본 가중치
        if metrics_weights is None:
            metrics_weights = {
                'number_of_spikes': 0.4,
                'mean_firing_rate_hz': 0.3,
                'burst_frequency_hz': 0.3
            }

        # 주요 metric들만 선택
        key_metrics = list(metrics_weights.keys())
        available_metrics = [m for m in key_metrics
                           if m in self.df_all['Metric'].unique()]

        if not available_metrics:
            print(f"  ⚠ No key metrics found")
            return self

        print(f"  ✓ Using metrics: {', '.join(available_metrics)}")

        scores = []

        # 개선: 더 안정적인 eps 값 (극단적 ratio 방지)
        eps = 1e-3
        min_base_threshold = 0.1  # BASE 값 최소 threshold

        # Electrode별로 처리
        for electrode_id in self.df_all['Electrode_ID'].unique():
            electrode_data = self.df_all[self.df_all['Electrode_ID'] == electrode_id]

            # Well 정보
            well = electrode_data['Well'].iloc[0]

            # DIV 정보 추출 (DIV 컬럼 직접 사용)
            div = electrode_data['DIV'].iloc[0] if 'DIV' in electrode_data.columns else np.nan

            # 개선: 모든 LIGHT_CODE에 대해 처리 (첫 번째만이 아닌)
            light_codes = electrode_data['LIGHT_CODE'].unique() if 'LIGHT_CODE' in electrode_data.columns else ['UNKNOWN']

            for light_code in light_codes:
                if 'LIGHT_CODE' in electrode_data.columns:
                    lc_data = electrode_data[electrode_data['LIGHT_CODE'] == light_code]
                else:
                    lc_data = electrode_data

                metric_ratios = {}
                metric_base_vals = {}
                metric_stim_vals = {}

                # 각 metric별 BASE/STIM ratio 계산
                for metric in available_metrics:
                    metric_data = lc_data[lc_data['Metric'] == metric]

                    base_data = metric_data[metric_data['BASE_STIM'] == 'BASE']
                    stim_data = metric_data[metric_data['BASE_STIM'] == 'STIM']

                    if not base_data.empty and not stim_data.empty:
                        base_val = base_data['Value'].mean()
                        stim_val = stim_data['Value'].mean()

                        # 개선: BASE 값 검증 - 너무 작으면 불안정한 ratio 방지
                        if base_val >= min_base_threshold:
                            ratio = (stim_val + eps) / (base_val + eps)
                            # 개선: ratio를 합리적인 범위로 제한 (0.01 ~ 100)
                            ratio = np.clip(ratio, 0.01, 100)
                        else:
                            # BASE가 작으면 STIM 값 기반으로 판단
                            if stim_val > min_base_threshold:
                                ratio = stim_val / min_base_threshold  # 증가로 간주
                            else:
                                ratio = 1.0  # 둘 다 작으면 중립

                        metric_ratios[metric] = ratio
                        metric_base_vals[metric] = base_val
                        metric_stim_vals[metric] = stim_val

                # Composite score 계산 (가중 평균)
                if metric_ratios:
                    composite_score = 0
                    total_weight = 0

                    for metric, ratio in metric_ratios.items():
                        weight = metrics_weights.get(metric, 0)
                        composite_score += ratio * weight
                        total_weight += weight

                    if total_weight > 0:
                        composite_score /= total_weight

                    score_entry = {
                        'Electrode_ID': electrode_id,
                        'Well': well,
                        'LIGHT_CODE': light_code,
                        'DIV': div,  # 분화일 (Well_Info의 Differentiation_Day)
                        'Response_Score': composite_score,
                    }

                    # 각 metric의 ratio 추가
                    for metric in available_metrics:
                        score_entry[f'{metric}_ratio'] = metric_ratios.get(metric, np.nan)
                        score_entry[f'{metric}_base'] = metric_base_vals.get(metric, np.nan)
                        score_entry[f'{metric}_stim'] = metric_stim_vals.get(metric, np.nan)

                    scores.append(score_entry)

        self.scores_df = pd.DataFrame(scores)

        if not self.scores_df.empty:
            # Score 기준 내림차순 정렬
            self.scores_df = self.scores_df.sort_values('Response_Score', ascending=False)

            # Well 내 순위 추가
            self.scores_df['Rank_in_Well'] = (
                self.scores_df.groupby('Well')['Response_Score']
                .rank(ascending=False, method='dense')
            )

            # 전체 순위 추가
            self.scores_df['Rank_Overall'] = (
                self.scores_df['Response_Score']
                .rank(ascending=False, method='dense')
            )

            # CSV 저장
            csv_path = self.output_dir / 'electrode_response_scores.csv'
            self.scores_df.to_csv(csv_path, index=False)

            print(f"  ✓ Calculated scores for {len(self.scores_df)} electrodes")
            print(f"  ✓ Score range: {self.scores_df['Response_Score'].min():.2f} - {self.scores_df['Response_Score'].max():.2f}")
            print(f"  ✓ Saved to: {csv_path.name}")

        return self

    @timer
    def create_visualizations(self):
        """Score 시각화"""
        if self.scores_df is None or self.scores_df.empty:
            print("  ⚠ No scores to visualize")
            return self

        print("\n[SCORER] Creating visualizations...")

        funcs = [
            self._plot_scores_by_well,
            self._plot_top_electrodes,
            self._plot_score_distribution,
            self._plot_metric_ratios_heatmap,
        ]

        for func in funcs:
            try:
                func()
            except Exception as e:
                print(f"  ⚠ {func.__name__}: {e}")

        print("  ✓ Score visualizations complete")
        return self

    def _plot_scores_by_well(self):
        """Well별 electrode score bargraph (DIV 표시 포함)"""
        wells = sorted(self.scores_df['Well'].unique())

        for well in wells:
            well_data = self.scores_df[self.scores_df['Well'] == well].copy()
            well_data = well_data.sort_values('Response_Score', ascending=False)

            if well_data.empty:
                continue

            # DIV 정보 추출
            div_val = well_data['DIV'].iloc[0] if 'DIV' in well_data.columns and pd.notna(well_data['DIV'].iloc[0]) else None
            div_str = f" (DIV {int(div_val)})" if div_val is not None else ""

            fig, ax = plt.subplots(figsize=(max(12, len(well_data)*0.5), 6))

            x_pos = np.arange(len(well_data))

            # Color gradient (높은 score = 진한 색)
            colors = plt.cm.RdYlGn(
                (well_data['Response_Score'] - well_data['Response_Score'].min()) /
                (well_data['Response_Score'].max() - well_data['Response_Score'].min() + 1e-6)
            )

            bars = ax.bar(x_pos, well_data['Response_Score'],
                         color=colors, edgecolor='black', alpha=0.8, linewidth=1.5)

            # Electrode ID 라벨
            ax.set_xticks(x_pos)
            ax.set_xticklabels(well_data['Electrode_ID'], rotation=90, ha='right', fontsize=9)

            ax.set_xlabel('Electrode ID', fontweight='bold', fontsize=11)
            ax.set_ylabel('Response Score (STIM/BASE ratio)', fontweight='bold', fontsize=11)
            ax.set_title(f'Electrode Light Response Scores - Well {well}{div_str}\n'
                        f'(Sorted by Score, Higher = Better Response)',
                        fontweight='bold', fontsize=12)
            ax.grid(axis='y', alpha=0.3)

            # Score 값 표시 (상위 10개만)
            for i, (idx, row) in enumerate(well_data.head(10).iterrows()):
                score_idx = list(well_data.index).index(idx)
                ax.text(score_idx, row['Response_Score'],
                       f"{row['Response_Score']:.2f}",
                       ha='center', va='bottom', fontsize=8, fontweight='bold')

            # 평균선
            mean_score = well_data['Response_Score'].mean()
            ax.axhline(mean_score, color='red', linestyle='--', linewidth=2,
                      label=f'Mean: {mean_score:.2f}')
            ax.legend()

            plt.tight_layout()
            plt.savefig(self.output_dir / f'scores_well_{well}.png',
                       dpi=300, bbox_inches='tight')
            plt.close(fig)

    def _plot_top_electrodes(self):
        """전체 상위 electrode"""
        top_n = min(30, len(self.scores_df))
        top_data = self.scores_df.head(top_n).copy()

        fig, ax = plt.subplots(figsize=(14, max(8, top_n*0.3)))

        y_pos = np.arange(len(top_data))

        # Color by well
        wells = top_data['Well'].unique()
        well_colors = {well: plt.cm.tab20(i/len(wells))
                      for i, well in enumerate(wells)}
        colors = [well_colors[w] for w in top_data['Well']]

        bars = ax.barh(y_pos, top_data['Response_Score'],
                      color=colors, edgecolor='black', alpha=0.8)

        # Labels
        labels = [f"{row['Electrode_ID']} ({row['Well']})"
                 for _, row in top_data.iterrows()]
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=9)

        ax.set_xlabel('Response Score', fontweight='bold', fontsize=11)
        ax.set_ylabel('Electrode (Well)', fontweight='bold', fontsize=11)
        ax.set_title(f'Top {top_n} Electrodes by Light Response Score',
                    fontweight='bold', fontsize=12)
        ax.grid(axis='x', alpha=0.3)

        # Score 값
        for i, score in enumerate(top_data['Response_Score']):
            ax.text(score, i, f' {score:.2f}',
                   va='center', fontsize=8, fontweight='bold')

        # Legend
        legend_elements = [plt.Rectangle((0,0),1,1, fc=well_colors[w],
                                        edgecolor='black', label=w)
                          for w in sorted(wells)]
        ax.legend(handles=legend_elements, title='Well',
                 loc='lower right', fontsize=8)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'top_electrodes_overall.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def _plot_score_distribution(self):
        """Score 분포"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # 1. Histogram
        ax1 = axes[0]
        ax1.hist(self.scores_df['Response_Score'], bins=30,
                edgecolor='black', alpha=0.7, color=COLORS['positive'])
        ax1.axvline(self.scores_df['Response_Score'].mean(),
                   color='red', linestyle='--', linewidth=2,
                   label=f"Mean: {self.scores_df['Response_Score'].mean():.2f}")
        ax1.axvline(self.scores_df['Response_Score'].median(),
                   color='blue', linestyle='--', linewidth=2,
                   label=f"Median: {self.scores_df['Response_Score'].median():.2f}")
        ax1.set_xlabel('Response Score', fontweight='bold')
        ax1.set_ylabel('Frequency', fontweight='bold')
        ax1.set_title('Response Score Distribution\n(All Electrodes)',
                     fontweight='bold')
        ax1.legend()
        ax1.grid(alpha=0.3)

        # 2. Boxplot by well
        ax2 = axes[1]
        wells = sorted(self.scores_df['Well'].unique())
        data_by_well = [self.scores_df[self.scores_df['Well'] == w]['Response_Score'].values
                       for w in wells]

        bp = ax2.boxplot(data_by_well, labels=wells, patch_artist=True,
                        showmeans=True, meanprops=dict(marker='D',
                                                       markerfacecolor='red',
                                                       markeredgecolor='red'))

        colors_list = plt.cm.Set3(np.linspace(0, 1, len(bp['boxes'])))
        for patch, color in zip(bp['boxes'], colors_list):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax2.set_xlabel('Well', fontweight='bold')
        ax2.set_ylabel('Response Score', fontweight='bold')
        ax2.set_title('Response Score by Well\n(Boxplot)',
                     fontweight='bold')
        ax2.grid(axis='y', alpha=0.3)
        plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'score_distribution.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

    def _plot_metric_ratios_heatmap(self):
        """Metric별 ratio 히트맵 (상위 electrode)"""
        top_n = min(30, len(self.scores_df))
        top_data = self.scores_df.head(top_n).copy()

        # Ratio columns만 선택
        ratio_cols = [c for c in top_data.columns if c.endswith('_ratio')]

        if not ratio_cols:
            return

        # Heatmap 데이터 준비
        heatmap_data = top_data[['Electrode_ID'] + ratio_cols].set_index('Electrode_ID')
        heatmap_data.columns = [c.replace('_ratio', '').replace('_', ' ').title()
                               for c in heatmap_data.columns]

        fig, ax = plt.subplots(figsize=(max(10, len(ratio_cols)*2),
                                        max(12, top_n*0.4)))

        # Z-score normalization
        heatmap_norm = (heatmap_data - heatmap_data.mean()) / heatmap_data.std()

        sns.heatmap(heatmap_norm, annot=True, fmt='.2f', cmap='RdYlGn',
                   center=0, cbar_kws={'label': 'Z-score'},
                   linewidths=0.5, linecolor='gray', ax=ax,
                   annot_kws={'size': 8})

        ax.set_title(f'Top {top_n} Electrodes - Metric Ratios Heatmap\n'
                    f'(Z-score normalized, STIM/BASE)',
                    fontweight='bold', fontsize=12, pad=15)
        ax.set_xlabel('Metrics', fontweight='bold')
        ax.set_ylabel('Electrode ID', fontweight='bold')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'metric_ratios_heatmap.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)


# =============================================================================
# DASHBOARD
# =============================================================================

class ElectrodeDashboard:
    """종합 Dashboard (v3.0)"""

    def __init__(self, df_all: pd.DataFrame, df_selected: pd.DataFrame,
                 selected_stats: pd.DataFrame, output_dir: Path):
        self.df_all = df_all
        self.df_selected = df_selected
        self.selected_stats = selected_stats
        self.output_dir = Path(output_dir)

    @timer
    def create(self):
        """Dashboard 생성"""
        print("\n[DASHBOARD] Creating...")

        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)

        # Row 1
        ax1 = fig.add_subplot(gs[0, :2])
        self._plot_selection_summary(ax1)

        ax2 = fig.add_subplot(gs[0, 2:])
        self._plot_light_spikes(ax2)

        # Row 2
        ax3 = fig.add_subplot(gs[1, 0])
        self._plot_base_stim_scatter(ax3)

        ax4 = fig.add_subplot(gs[1, 1])
        self._plot_firing_rate(ax4)

        ax5 = fig.add_subplot(gs[1, 2])
        self._plot_burst_freq(ax5)

        ax6 = fig.add_subplot(gs[1, 3])
        self._plot_spatial_mini(ax6)

        # Row 3
        axes_bottom = [fig.add_subplot(gs[2, i]) for i in range(4)]
        self._plot_distributions(axes_bottom)

        fig.suptitle('MEA Electrode Analysis - Dashboard (v3.0)',
                    fontweight='bold', fontsize=18, y=0.98)

        plt.savefig(self.output_dir / 'ELECTRODE_DASHBOARD.png',
                   dpi=300, bbox_inches='tight')
        plt.close(fig)

        print("  ✓ Dashboard created")

    def _plot_selection_summary(self, ax):
        if self.selected_stats is None or self.selected_stats.empty:
            return

        well_counts = self.selected_stats['Well'].value_counts().sort_index()
        ax.bar(range(len(well_counts)), well_counts.values,
              alpha=0.7, edgecolor='black', color=COLORS['neutral'])
        ax.set_xticks(range(len(well_counts)))
        ax.set_xticklabels(well_counts.index, rotation=45, ha='right', fontsize=9)
        ax.set_xlabel('Well', fontweight='bold')
        ax.set_ylabel('Selected Electrodes', fontweight='bold')
        ax.set_title('Selected Electrodes per Well', fontweight='bold', fontsize=11)
        ax.grid(axis='y', alpha=0.3)

    def _plot_light_spikes(self, ax):
        if self.df_selected.empty or 'LIGHT_CODE' not in self.df_selected.columns:
            return

        stim_data = self.df_selected[
            (self.df_selected['BASE_STIM'] == 'STIM') &
            (self.df_selected['Metric'] == 'number_of_spikes')
        ]

        if stim_data.empty:
            return

        light_means = stim_data.groupby('LIGHT_CODE')['Value'].mean().sort_index()
        colors_list = plt.cm.Set3(np.linspace(0, 1, len(light_means)))

        bars = ax.bar(range(len(light_means)), light_means.values,
                     alpha=0.8, edgecolor='black', color=colors_list)

        ax.set_xticks(range(len(light_means)))
        ax.set_xticklabels(light_means.index, rotation=45, ha='right', fontsize=9)
        ax.set_xlabel('Light Code', fontweight='bold')
        ax.set_ylabel('Mean Spikes', fontweight='bold')
        ax.set_title('Number of Spikes by Light Code (STIM)',
                    fontweight='bold', fontsize=11)
        ax.grid(axis='y', alpha=0.3)

    def _plot_base_stim_scatter(self, ax):
        if self.selected_stats is None or self.selected_stats.empty:
            return

        ax.scatter(self.selected_stats['spikes_base'],
                  self.selected_stats['spikes_stim'],
                  alpha=0.6, s=40, edgecolor='black', c=COLORS['stim'])

        max_val = max(self.selected_stats['spikes_base'].max(),
                     self.selected_stats['spikes_stim'].max())
        ax.plot([0, max_val], [0, max_val], 'k--', alpha=0.5, label='y=x')

        ax.set_xlabel('BASE Spikes', fontweight='bold', fontsize=10)
        ax.set_ylabel('STIM Spikes', fontweight='bold', fontsize=10)
        ax.set_title('BASE vs STIM', fontweight='bold', fontsize=11)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    def _plot_firing_rate(self, ax):
        if self.df_selected.empty or 'LIGHT_CODE' not in self.df_selected.columns:
            return

        stim_data = self.df_selected[
            (self.df_selected['BASE_STIM'] == 'STIM') &
            (self.df_selected['Metric'] == 'mean_firing_rate_hz')
        ]

        if stim_data.empty:
            return

        light_means = stim_data.groupby('LIGHT_CODE')['Value'].mean().sort_index()

        ax.bar(range(len(light_means)), light_means.values,
              alpha=0.7, edgecolor='black', color=COLORS['positive'])
        ax.set_xticks(range(len(light_means)))
        ax.set_xticklabels(light_means.index, rotation=45, ha='right', fontsize=9)
        ax.set_xlabel('Light Code', fontweight='bold', fontsize=10)
        ax.set_ylabel('Firing Rate (Hz)', fontweight='bold', fontsize=10)
        ax.set_title('Firing Rate by Light Code', fontweight='bold', fontsize=11)
        ax.grid(axis='y', alpha=0.3)

    def _plot_burst_freq(self, ax):
        if self.df_selected.empty:
            return

        stim_data = self.df_selected[
            (self.df_selected['BASE_STIM'] == 'STIM') &
            (self.df_selected['Metric'] == 'burst_frequency_hz')
        ]

        if stim_data.empty:
            ax.text(0.5, 0.5, 'No burst data',
                   ha='center', va='center', transform=ax.transAxes)
            return

        if 'LIGHT_CODE' in stim_data.columns:
            light_means = stim_data.groupby('LIGHT_CODE')['Value'].mean().sort_index()
            ax.bar(range(len(light_means)), light_means.values,
                  alpha=0.7, edgecolor='black', color=COLORS['stim'])
            ax.set_xticks(range(len(light_means)))
            ax.set_xticklabels(light_means.index, rotation=45, ha='right', fontsize=9)
            ax.set_xlabel('Light Code', fontweight='bold', fontsize=10)
        else:
            ax.hist(stim_data['Value'].dropna(), bins=15,
                   edgecolor='black', alpha=0.7, color=COLORS['stim'])
            ax.set_xlabel('Burst Frequency (Hz)', fontweight='bold', fontsize=10)

        ax.set_ylabel('Value', fontweight='bold', fontsize=10)
        ax.set_title('Burst Frequency', fontweight='bold', fontsize=11)
        ax.grid(alpha=0.3)

    def _plot_spatial_mini(self, ax):
        if self.selected_stats is None or self.selected_stats.empty:
            return

        rows = ['A', 'B', 'C', 'D']
        cols = [1, 2, 3, 4, 5, 6]

        well_counts = self.selected_stats['Well'].value_counts()
        matrix = np.zeros((len(rows), len(cols)))

        for well, count in well_counts.items():
            if len(well) >= 2 and well[0] in rows:
                row_idx = rows.index(well[0])
                col_idx = cols.index(int(well[1]))
                matrix[row_idx, col_idx] = count

        im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')

        ax.set_xticks(range(len(cols)))
        ax.set_yticks(range(len(rows)))
        ax.set_xticklabels(cols, fontsize=9)
        ax.set_yticklabels(rows, fontsize=9)

        for i in range(len(rows)):
            for j in range(len(cols)):
                ax.text(j, i, int(matrix[i, j]),
                       ha="center", va="center", color="black",
                       fontsize=9, fontweight='bold')

        ax.set_title('Spatial Distribution', fontweight='bold', fontsize=11)

    def _plot_distributions(self, axes):
        if self.df_selected.empty:
            return

        metrics = ['number_of_spikes', 'mean_firing_rate_hz',
                  'burst_frequency_hz', 'burst_duration_avg_s']

        stim_data = self.df_selected[self.df_selected['BASE_STIM'] == 'STIM']

        for ax, metric in zip(axes, metrics):
            metric_data = stim_data[stim_data['Metric'] == metric]

            if metric_data.empty:
                ax.text(0.5, 0.5, f'No {metric}',
                       ha='center', va='center', transform=ax.transAxes)
                continue

            ax.hist(metric_data['Value'].dropna(), bins=15,
                   edgecolor='black', alpha=0.7, color=COLORS['base'])
            ax.set_xlabel('Value', fontweight='bold', fontsize=9)
            ax.set_ylabel('Frequency', fontweight='bold', fontsize=9)
            ax.set_title(metric.replace('_', ' ').title(),
                        fontweight='bold', fontsize=10)
            ax.grid(alpha=0.3)


# =============================================================================
# PIPELINE
# =============================================================================

class ElectrodeAnalysisPipeline:
    """
    전극 분석 파이프라인 v3.0

    Usage:
        pipeline = ElectrodeAnalysisPipeline(
            input_dir=r"D:\MEAdata\electrode",
            output_dir=r"D:\MEAdata\output",
            n_workers=4,
            filter_config=ElectrodeFilterConfig(
                min_metric_ratio=0.5,
                min_pct_change=10.0,
                min_fold_change=2.0
            )
        )
        pipeline.run()
    """

    def __init__(self, input_dir: str, output_dir: str,
                 filter_config: Optional[ElectrodeFilterConfig] = None,
                 n_workers: int = 4, use_cache: bool = True):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.filter_config = filter_config or ElectrodeFilterConfig()
        self.n_workers = n_workers
        self.use_cache = use_cache

        self.df_all = None
        self.selected_stats = None
        self.df_selected = None

        self.performance = PerformanceMonitor()

    def run(self):
        """파이프라인 실행"""
        print('='*80)
        print('MEA ELECTRODE ANALYZER V3.0 CLEAN')
        print('='*80)
        print(f'Input: {self.input_dir}')
        print(f'Output: {self.output_dir}')
        print(f'Cache: {"ON" if self.use_cache else "OFF"}')
        print(f'Workers: {self.n_workers}')
        print('='*80)

        pipeline_start = time.time()

        # Stage 1: Load
        stage_start = time.time()
        print('\n[STAGE 1] Loading data...')
        loader = ElectrodeFormatLoader(self.input_dir, self.use_cache)
        self.df_all = loader.load_all()
        self.performance.record('Stage 1: Loading', time.time() - stage_start)

        if self.df_all.empty:
            print("❌ No data loaded")
            return

        # Stage 2: Save raw
        stage_start = time.time()
        print('\n[STAGE 2] Saving raw data...')
        self.df_all.to_csv(self.output_dir / "electrode_all_long.csv", index=False)
        self.df_all.to_parquet(self.output_dir / "electrode_all_long.parquet", index=False)
        self.performance.record('Stage 2: Save Raw', time.time() - stage_start)

        # Stage 3: Filter
        stage_start = time.time()
        print('\n[STAGE 3] Filtering electrodes...')
        self.selected_stats, self.df_selected = filter_electrodes(
            self.df_all, self.filter_config, verbose=True)
        self.performance.record('Stage 3: Filtering', time.time() - stage_start)

        if self.selected_stats is None or self.selected_stats.empty:
            print("❌ No electrodes selected")
            return

        # Stage 4: Save filtered
        stage_start = time.time()
        print('\n[STAGE 4] Saving filtered data...')
        self.selected_stats.to_csv(self.output_dir / "electrode_selected_stats.csv",
                                   index=False)
        self.df_selected.to_csv(self.output_dir / "electrode_selected_long.csv",
                               index=False)
        self.df_selected.to_parquet(self.output_dir / "electrode_selected_long.parquet",
                                    index=False)
        self.performance.record('Stage 4: Save Filtered', time.time() - stage_start)

        # Stage 5: Visualizations
        stage_start = time.time()
        print('\n[STAGE 5] Creating visualizations...')
        visualizer = ElectrodeVisualizer(self.df_all, self.df_selected,
                                        self.selected_stats, self.output_dir)
        visualizer.create_all()
        self.performance.record('Stage 5: Visualizations', time.time() - stage_start)

        # Stage 6: Dashboard
        stage_start = time.time()
        print('\n[STAGE 6] Creating dashboard...')
        dashboard = ElectrodeDashboard(self.df_all, self.df_selected,
                                       self.selected_stats, self.output_dir)
        dashboard.create()
        self.performance.record('Stage 6: Dashboard', time.time() - stage_start)

        # Stage 7: Light Response
        stage_start = time.time()
        print('\n[STAGE 7] Analyzing light responses...')
        light_analyzer = LightResponseAnalyzer(self.df_selected, self.output_dir)
        light_analyzer.calculate_responses().create_visualizations()
        self.performance.record('Stage 7: Light Response', time.time() - stage_start)

        # Stage 8: Electrode Response Scoring
        stage_start = time.time()
        print('\n[STAGE 8] Calculating electrode response scores...')
        scorer = ElectrodeResponseScorer(self.df_all, self.output_dir)
        scorer.calculate_scores().create_visualizations()
        self.performance.record('Stage 8: Response Scoring', time.time() - stage_start)

        # Summary
        total_time = time.time() - pipeline_start
        self.performance.record('Total Pipeline', total_time)
        self.performance.print_summary()

        print('\n' + '='*80)
        print('🎉 PIPELINE COMPLETE!')
        print('='*80)
        print(f'Results: {self.output_dir}')
        print(f'Total time: {total_time:.2f}s')
        print('='*80)

        gc.collect()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Example usage
    pipeline = ElectrodeAnalysisPipeline(
        input_dir=r"D:\MEAdata\electrode",
        output_dir=r"D:\MEAdata\output",
        n_workers=4,
        filter_config=ElectrodeFilterConfig(
            min_metric_ratio=0.5,
            min_pct_change=10.0,  # 10% change
            min_fold_change=2.0
        )
    )
    pipeline.run()


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================
ElectrodeAnalyzer = ElectrodeAnalysisPipeline  # Alias
