"""
MEA Variable Recording Duration Analyzer
=========================================
다양한 측정 시간(recording duration)을 감안한 MEA 분석 파이프라인

문제:
- Control: base/stim 각각 120sec 측정
- Drug: base/stim 각각 300sec 측정
- Washout: 다른 시간으로 측정 가능

해결책:
- Number of spikes → Spikes/min (firing rate)
- Number of bursts → Bursts/min
- 모든 절대값 metric을 시간 기반으로 정규화
- Ratio 기반 비교 (drug/control, washout/control)

핵심 Metrics:
- Rate-based: spikes/min, bursts/min, mean_firing_rate_hz
- Duration-independent: burst_duration_avg_s, inter_burst_interval_avg_s
- Ratio metrics: STIM/BASE ratio, drug/control ratio

Usage:
    from mea_variable_duration_analyzer import VariableDurationAnalyzer

    analyzer = VariableDurationAnalyzer(
        electrode_data_path=r"D:\\output\\electrode_all_long.parquet",
        output_dir=r"D:\\output\\variable_duration_analysis"
    )
    analyzer.run()
"""

from pathlib import Path
import time
from functools import wraps
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from dataclasses import dataclass
import gc
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


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
    'control': '#3498DB',   # Blue
    'drug': '#E74C3C',      # Red
    'washout': '#2ECC71',   # Green
    'positive': '#58D68D',  # Light green
    'negative': '#EC7063',  # Red
    'neutral': '#85929E',   # Gray
    'BL': '#0066CC',        # Blue Light
    'GR': '#00AA00',        # Green
    'OR': '#FF8800',        # Orange
    'RD': '#DD0000',        # Red
}


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class VariableDurationConfig:
    """
    Variable duration 분석 설정

    Parameters:
    -----------
    normalize_to_per_min : bool
        True면 절대값을 분당(per minute)으로 정규화
    use_rate_metrics_only : bool
        True면 rate 기반 metric만 사용 (number_of_spikes 대신 mean_firing_rate_hz)
    min_recording_duration_sec : float
        최소 recording duration (이보다 짧은 데이터는 제외)
    control_conditions : list
        Control로 분류할 DRUG 값들
    drug_conditions : list
        Drug으로 분류할 DRUG 값들 (비어있으면 'NONE'이 아닌 모든 값)
    washout_conditions : list
        Washout으로 분류할 DRUG 값들
    """
    normalize_to_per_min: bool = True
    use_rate_metrics_only: bool = False
    min_recording_duration_sec: float = 30.0
    control_conditions: List[str] = None
    drug_conditions: List[str] = None
    washout_conditions: List[str] = None

    def __post_init__(self):
        if self.control_conditions is None:
            self.control_conditions = ['NONE', 'CONTROL', 'CTRL', 'VEH', 'VEHICLE']
        if self.washout_conditions is None:
            self.washout_conditions = ['WASHOUT', 'WASH', 'WO', 'RECOVERY']


# Metrics that should be normalized by time
ABSOLUTE_METRICS = {
    'number_of_spikes',
    'number_of_bursts',
}

# Metrics that are already rate-based or time-independent
RATE_METRICS = {
    'mean_firing_rate_hz',      # Already in Hz (spikes/sec)
    'burst_frequency_hz',       # Already in Hz
    'isi_cv',                   # Coefficient of variation (dimensionless)
    'ibi_cv',                   # Coefficient of variation (dimensionless)
    'burst_percentage',         # Percentage (dimensionless)
}

DURATION_METRICS = {
    'burst_duration_avg_s',
    'burst_duration_std_s',
    'inter_burst_interval_avg_s',
    'inter_burst_interval_std_s',
    'mean_isi_within_burst_avg',
    'mean_isi_within_burst_std',
    'median_isi_within_burst_avg',
    'median_isi_within_burst_std',
}

PER_BURST_METRICS = {
    'spikes_per_burst_avg',
    'spikes_per_burst_std',
    'normalized_duration_iqr',
}


# =============================================================================
# DATA NORMALIZER
# =============================================================================

class DurationNormalizer:
    """Recording duration에 따른 데이터 정규화"""

    def __init__(self, config: VariableDurationConfig):
        self.config = config

    @timer
    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Recording duration에 따라 데이터 정규화

        절대값 metric (number_of_spikes, number_of_bursts) →
        분당 rate (spikes_per_min, bursts_per_min)으로 변환
        """
        print('\n[NORMALIZER] Normalizing data by recording duration...')

        if df.empty:
            return df

        # TIME_DURATION_SEC 컬럼 확인
        if 'TIME_DURATION_SEC' not in df.columns:
            print('  ⚠ No TIME_DURATION_SEC column, using default 120s')
            df['TIME_DURATION_SEC'] = 120.0

        # 최소 duration 필터
        original_len = len(df)
        df = df[df['TIME_DURATION_SEC'] >= self.config.min_recording_duration_sec].copy()
        if len(df) < original_len:
            print(f'  ⚠ Filtered out {original_len - len(df)} rows with short duration')

        # Duration 분포 출력
        durations = df['TIME_DURATION_SEC'].unique()
        print(f'  ✓ Recording durations: {sorted(durations)} sec')

        if not self.config.normalize_to_per_min:
            print('  ⚠ Normalization disabled, returning raw data')
            return df

        # 새로운 normalized 컬럼 생성
        normalized_rows = []

        for _, row in df.iterrows():
            new_row = row.copy()
            metric = row['Metric']
            value = row['Value']
            duration_sec = row['TIME_DURATION_SEC']
            duration_min = duration_sec / 60.0

            if metric in ABSOLUTE_METRICS and pd.notna(value) and duration_min > 0:
                # 절대값 → 분당 rate로 변환
                if metric == 'number_of_spikes':
                    new_row['Metric'] = 'spikes_per_min'
                    new_row['Value'] = value / duration_min
                elif metric == 'number_of_bursts':
                    new_row['Metric'] = 'bursts_per_min'
                    new_row['Value'] = value / duration_min

                new_row['Original_Metric'] = metric
                new_row['Original_Value'] = value
                new_row['Normalized'] = True
            else:
                new_row['Original_Metric'] = metric
                new_row['Original_Value'] = value
                new_row['Normalized'] = False

            normalized_rows.append(new_row)

        df_normalized = pd.DataFrame(normalized_rows)

        # 결과 요약
        n_normalized = df_normalized['Normalized'].sum()
        print(f'  ✓ Normalized {n_normalized} rows')
        print(f'  ✓ New metrics: spikes_per_min, bursts_per_min')

        return df_normalized


# =============================================================================
# CONDITION CLASSIFIER
# =============================================================================

class ConditionClassifier:
    """Control, Drug, Washout 조건 분류"""

    def __init__(self, config: VariableDurationConfig):
        self.config = config

    @timer
    def classify(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        DRUG 컬럼 기반으로 Condition 분류

        Returns:
        --------
        DataFrame with 'Condition' column: 'CONTROL', 'DRUG', 'WASHOUT', or 'OTHER'
        """
        print('\n[CLASSIFIER] Classifying conditions...')

        if df.empty:
            return df

        df = df.copy()

        # DRUG 컬럼 확인
        if 'DRUG' not in df.columns:
            print('  ⚠ No DRUG column, assuming all CONTROL')
            df['Condition'] = 'CONTROL'
            return df

        # Condition 분류
        def classify_row(drug_val):
            if pd.isna(drug_val):
                return 'CONTROL'

            drug_upper = str(drug_val).upper().strip()

            # Control 조건 확인
            if drug_upper in [c.upper() for c in self.config.control_conditions]:
                return 'CONTROL'

            # Washout 조건 확인
            if drug_upper in [c.upper() for c in self.config.washout_conditions]:
                return 'WASHOUT'

            # Drug 조건 확인
            if self.config.drug_conditions:
                if drug_upper in [c.upper() for c in self.config.drug_conditions]:
                    return 'DRUG'
            else:
                # 기본: CONTROL이나 WASHOUT이 아니면 DRUG
                return 'DRUG'

            return 'OTHER'

        df['Condition'] = df['DRUG'].apply(classify_row)

        # 결과 요약
        condition_counts = df['Condition'].value_counts()
        print(f'  ✓ Conditions:')
        for cond, count in condition_counts.items():
            print(f'    - {cond}: {count} rows')

        return df


# =============================================================================
# RATIO ANALYZER
# =============================================================================

class RatioAnalyzer:
    """
    Ratio 기반 분석기

    주요 기능:
    1. STIM/BASE ratio (light response)
    2. Drug/Control ratio
    3. Washout/Control ratio
    4. Fold change 계산
    """

    def __init__(self, df: pd.DataFrame, output_dir: Path):
        self.df = df
        self.output_dir = Path(output_dir) / 'ratio_analysis'
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.stim_base_ratios = None
        self.condition_ratios = None
        self.summary = None

    @timer
    def analyze_stim_base_ratio(self) -> pd.DataFrame:
        """
        STIM/BASE ratio 계산 (Light Response)

        모든 조건에서 STIM과 BASE의 비율 계산
        """
        print('\n[RATIO] Calculating STIM/BASE ratios...')

        if self.df.empty or 'BASE_STIM' not in self.df.columns:
            print('  ⚠ No BASE_STIM column')
            return pd.DataFrame()

        base_df = self.df[self.df['BASE_STIM'] == 'BASE']
        stim_df = self.df[self.df['BASE_STIM'] == 'STIM']

        if base_df.empty or stim_df.empty:
            print('  ⚠ Missing BASE or STIM data')
            return pd.DataFrame()

        # 그룹 컬럼 정의
        group_cols = ['Well', 'Electrode_ID', 'Metric']
        optional_cols = ['LIGHT_CODE', 'Condition', 'DRUG', 'DIV']
        for col in optional_cols:
            if col in self.df.columns:
                group_cols.append(col)

        # BASE와 STIM 평균
        base_agg = base_df.groupby(group_cols)['Value'].mean().reset_index()
        base_agg = base_agg.rename(columns={'Value': 'BASE_Value'})

        stim_agg = stim_df.groupby(group_cols)['Value'].mean().reset_index()
        stim_agg = stim_agg.rename(columns={'Value': 'STIM_Value'})

        # 병합
        merged = base_agg.merge(stim_agg, on=group_cols, how='outer')

        # Ratio 계산
        eps = 1e-6
        merged['STIM_BASE_Ratio'] = (merged['STIM_Value'] + eps) / (merged['BASE_Value'] + eps)
        merged['STIM_BASE_Diff'] = merged['STIM_Value'] - merged['BASE_Value']
        merged['STIM_BASE_PctChange'] = (merged['STIM_BASE_Diff'] / (merged['BASE_Value'] + eps)) * 100
        merged['Log2_FC'] = np.log2(merged['STIM_BASE_Ratio'])

        # 통계적 유의성 표시
        merged['Response_Direction'] = 'no_change'
        merged.loc[merged['Log2_FC'] > 0.5, 'Response_Direction'] = 'increase'
        merged.loc[merged['Log2_FC'] < -0.5, 'Response_Direction'] = 'decrease'

        self.stim_base_ratios = merged

        # 저장
        merged.to_csv(self.output_dir / 'stim_base_ratios.csv', index=False)

        print(f'  ✓ Calculated {len(merged)} STIM/BASE ratios')
        print(f'  ✓ Increase: {(merged["Response_Direction"]=="increase").sum()}')
        print(f'  ✓ Decrease: {(merged["Response_Direction"]=="decrease").sum()}')
        print(f'  ✓ No change: {(merged["Response_Direction"]=="no_change").sum()}')

        return merged

    @timer
    def analyze_condition_ratios(self) -> pd.DataFrame:
        """
        Drug/Control, Washout/Control ratio 계산

        Recording duration이 달라도 rate-based metric을 사용하면
        직접 비교 가능
        """
        print('\n[RATIO] Calculating Condition ratios...')

        if self.df.empty or 'Condition' not in self.df.columns:
            print('  ⚠ No Condition column')
            return pd.DataFrame()

        control_df = self.df[self.df['Condition'] == 'CONTROL']
        drug_df = self.df[self.df['Condition'] == 'DRUG']
        washout_df = self.df[self.df['Condition'] == 'WASHOUT']

        results = []

        # 그룹 컬럼
        group_cols = ['Well', 'Metric', 'BASE_STIM']
        optional_cols = ['LIGHT_CODE', 'DIV']
        for col in optional_cols:
            if col in self.df.columns:
                group_cols.append(col)

        # Control 평균
        if not control_df.empty:
            control_agg = control_df.groupby(group_cols).agg({
                'Value': ['mean', 'std', 'count'],
                'TIME_DURATION_SEC': 'mean'
            }).reset_index()
            control_agg.columns = group_cols + ['Control_Mean', 'Control_Std',
                                                 'Control_N', 'Control_Duration']
        else:
            print('  ⚠ No CONTROL data')
            return pd.DataFrame()

        # Drug 분석
        if not drug_df.empty:
            drug_agg = drug_df.groupby(group_cols).agg({
                'Value': ['mean', 'std', 'count'],
                'TIME_DURATION_SEC': 'mean'
            }).reset_index()
            drug_agg.columns = group_cols + ['Drug_Mean', 'Drug_Std',
                                              'Drug_N', 'Drug_Duration']

            # Drug/Control ratio
            drug_ratio = control_agg.merge(drug_agg, on=group_cols, how='inner')

            eps = 1e-6
            drug_ratio['Drug_Control_Ratio'] = (
                (drug_ratio['Drug_Mean'] + eps) / (drug_ratio['Control_Mean'] + eps)
            )
            drug_ratio['Drug_Control_Diff'] = drug_ratio['Drug_Mean'] - drug_ratio['Control_Mean']
            drug_ratio['Drug_Control_PctChange'] = (
                drug_ratio['Drug_Control_Diff'] / (drug_ratio['Control_Mean'] + eps) * 100
            )
            drug_ratio['Drug_Log2_FC'] = np.log2(drug_ratio['Drug_Control_Ratio'])
            drug_ratio['Comparison'] = 'Drug_vs_Control'
            drug_ratio['Duration_Ratio'] = drug_ratio['Drug_Duration'] / drug_ratio['Control_Duration']

            results.append(drug_ratio)

            print(f'  ✓ Drug/Control: {len(drug_ratio)} comparisons')
            print(f'    Duration ratio (Drug/Control): {drug_ratio["Duration_Ratio"].mean():.2f}x')

        # Washout 분석
        if not washout_df.empty:
            washout_agg = washout_df.groupby(group_cols).agg({
                'Value': ['mean', 'std', 'count'],
                'TIME_DURATION_SEC': 'mean'
            }).reset_index()
            washout_agg.columns = group_cols + ['Washout_Mean', 'Washout_Std',
                                                 'Washout_N', 'Washout_Duration']

            # Washout/Control ratio
            washout_ratio = control_agg.merge(washout_agg, on=group_cols, how='inner')

            eps = 1e-6
            washout_ratio['Washout_Control_Ratio'] = (
                (washout_ratio['Washout_Mean'] + eps) / (washout_ratio['Control_Mean'] + eps)
            )
            washout_ratio['Washout_Control_Diff'] = washout_ratio['Washout_Mean'] - washout_ratio['Control_Mean']
            washout_ratio['Washout_Control_PctChange'] = (
                washout_ratio['Washout_Control_Diff'] / (washout_ratio['Control_Mean'] + eps) * 100
            )
            washout_ratio['Washout_Log2_FC'] = np.log2(washout_ratio['Washout_Control_Ratio'])
            washout_ratio['Comparison'] = 'Washout_vs_Control'
            washout_ratio['Duration_Ratio'] = washout_ratio['Washout_Duration'] / washout_ratio['Control_Duration']

            results.append(washout_ratio)

            print(f'  ✓ Washout/Control: {len(washout_ratio)} comparisons')

        if results:
            # 결과 결합
            self.condition_ratios = pd.concat(results, ignore_index=True)
            self.condition_ratios.to_csv(self.output_dir / 'condition_ratios.csv', index=False)

            return self.condition_ratios

        return pd.DataFrame()

    @timer
    def create_summary(self) -> pd.DataFrame:
        """분석 요약 생성"""
        print('\n[RATIO] Creating summary...')

        summary_rows = []

        # Rate metrics만 사용하는 것을 권장
        recommended_metrics = ['spikes_per_min', 'bursts_per_min', 'mean_firing_rate_hz',
                               'burst_frequency_hz', 'burst_duration_avg_s',
                               'spikes_per_burst_avg']

        # STIM/BASE ratio 요약
        if self.stim_base_ratios is not None and not self.stim_base_ratios.empty:
            for metric in recommended_metrics:
                metric_data = self.stim_base_ratios[self.stim_base_ratios['Metric'] == metric]
                if not metric_data.empty:
                    summary_rows.append({
                        'Analysis': 'STIM_BASE_Ratio',
                        'Metric': metric,
                        'Mean_Ratio': metric_data['STIM_BASE_Ratio'].mean(),
                        'Std_Ratio': metric_data['STIM_BASE_Ratio'].std(),
                        'Mean_Log2FC': metric_data['Log2_FC'].mean(),
                        'N_Increase': (metric_data['Response_Direction'] == 'increase').sum(),
                        'N_Decrease': (metric_data['Response_Direction'] == 'decrease').sum(),
                        'N_NoChange': (metric_data['Response_Direction'] == 'no_change').sum(),
                        'Total_N': len(metric_data)
                    })

        # Condition ratio 요약
        if self.condition_ratios is not None and not self.condition_ratios.empty:
            for comparison in self.condition_ratios['Comparison'].unique():
                comp_data = self.condition_ratios[self.condition_ratios['Comparison'] == comparison]

                for metric in recommended_metrics:
                    metric_data = comp_data[comp_data['Metric'] == metric]
                    if not metric_data.empty:
                        if 'Drug' in comparison:
                            ratio_col = 'Drug_Control_Ratio'
                            log2_col = 'Drug_Log2_FC'
                        else:
                            ratio_col = 'Washout_Control_Ratio'
                            log2_col = 'Washout_Log2_FC'

                        summary_rows.append({
                            'Analysis': comparison,
                            'Metric': metric,
                            'Mean_Ratio': metric_data[ratio_col].mean(),
                            'Std_Ratio': metric_data[ratio_col].std(),
                            'Mean_Log2FC': metric_data[log2_col].mean(),
                            'Duration_Ratio': metric_data['Duration_Ratio'].mean(),
                            'Total_N': len(metric_data)
                        })

        self.summary = pd.DataFrame(summary_rows)

        if not self.summary.empty:
            self.summary.to_csv(self.output_dir / 'ratio_summary.csv', index=False)
            print(f'  ✓ Summary: {len(self.summary)} entries')

        return self.summary


# =============================================================================
# VISUALIZER
# =============================================================================

class VariableDurationVisualizer:
    """Variable duration 분석 시각화"""

    def __init__(self, df: pd.DataFrame, ratio_analyzer: RatioAnalyzer,
                 output_dir: Path):
        self.df = df
        self.ratio_analyzer = ratio_analyzer
        self.output_dir = Path(output_dir) / 'visualizations'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @timer
    def create_all(self):
        """모든 시각화 생성"""
        print('\n[VIZ] Creating visualizations...')

        funcs = [
            self.plot_duration_distribution,
            self.plot_rate_comparison,
            self.plot_stim_base_ratios,
            self.plot_condition_comparison,
            self.plot_fold_change_heatmap,
            self.plot_metric_correlation,
            self.plot_condition_timeline,
        ]

        for func in funcs:
            try:
                func()
            except Exception as e:
                print(f'  ⚠ {func.__name__}: {e}')

        print('  ✓ All visualizations complete')

    def plot_duration_distribution(self):
        """Recording duration 분포"""
        if 'TIME_DURATION_SEC' not in self.df.columns:
            return

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # 1. Histogram
        ax = axes[0]
        durations = self.df['TIME_DURATION_SEC'].dropna()
        ax.hist(durations, bins=20, edgecolor='black', alpha=0.7, color=COLORS['neutral'])
        ax.set_xlabel('Recording Duration (sec)', fontweight='bold')
        ax.set_ylabel('Count', fontweight='bold')
        ax.set_title('Recording Duration Distribution', fontweight='bold')
        ax.grid(alpha=0.3)

        # Duration 별 통계 표시
        unique_durations = sorted(durations.unique())
        text = 'Unique durations:\n'
        for d in unique_durations[:5]:
            count = (durations == d).sum()
            text += f'{d:.0f}s: {count}\n'
        ax.text(0.95, 0.95, text, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        # 2. Condition별 duration
        ax = axes[1]
        if 'Condition' in self.df.columns:
            conditions = ['CONTROL', 'DRUG', 'WASHOUT']
            durations_by_cond = []
            labels = []
            colors = []

            for cond in conditions:
                cond_data = self.df[self.df['Condition'] == cond]['TIME_DURATION_SEC'].dropna()
                if len(cond_data) > 0:
                    durations_by_cond.append(cond_data.values)
                    labels.append(f'{cond}\n({cond_data.mean():.0f}s avg)')
                    colors.append(COLORS.get(cond.lower(), COLORS['neutral']))

            if durations_by_cond:
                bp = ax.boxplot(durations_by_cond, labels=labels, patch_artist=True)
                for patch, color in zip(bp['boxes'], colors):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.7)

                ax.set_ylabel('Recording Duration (sec)', fontweight='bold')
                ax.set_title('Duration by Condition', fontweight='bold')
                ax.grid(axis='y', alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'No Condition data', ha='center', va='center',
                   transform=ax.transAxes)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'duration_distribution.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_rate_comparison(self):
        """Rate 기반 metric 비교 (normalized vs raw)"""
        rate_metrics = ['spikes_per_min', 'bursts_per_min', 'mean_firing_rate_hz']
        available = [m for m in rate_metrics if m in self.df['Metric'].unique()]

        if not available:
            return

        fig, axes = plt.subplots(1, len(available), figsize=(6*len(available), 6))
        if len(available) == 1:
            axes = [axes]

        for idx, metric in enumerate(available):
            ax = axes[idx]
            metric_data = self.df[self.df['Metric'] == metric]

            if 'Condition' in metric_data.columns:
                conditions = ['CONTROL', 'DRUG', 'WASHOUT']
                data_by_cond = []
                labels = []
                colors = []

                for cond in conditions:
                    cond_data = metric_data[metric_data['Condition'] == cond]['Value'].dropna()
                    if len(cond_data) > 0:
                        data_by_cond.append(cond_data.values)
                        labels.append(cond)
                        colors.append(COLORS.get(cond.lower(), COLORS['neutral']))

                if data_by_cond:
                    bp = ax.boxplot(data_by_cond, labels=labels, patch_artist=True)
                    for patch, color in zip(bp['boxes'], colors):
                        patch.set_facecolor(color)
                        patch.set_alpha(0.7)
            else:
                ax.boxplot(metric_data['Value'].dropna().values)

            ax.set_ylabel('Value', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}', fontweight='bold')
            ax.grid(axis='y', alpha=0.3)

        plt.suptitle('Rate-Based Metrics by Condition\n(Duration-independent comparison)',
                    fontweight='bold', fontsize=14)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'rate_comparison.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_stim_base_ratios(self):
        """STIM/BASE ratio 시각화"""
        if self.ratio_analyzer.stim_base_ratios is None:
            return

        ratios = self.ratio_analyzer.stim_base_ratios

        rate_metrics = ['spikes_per_min', 'bursts_per_min', 'mean_firing_rate_hz',
                       'burst_frequency_hz']
        available = [m for m in rate_metrics if m in ratios['Metric'].unique()]

        if not available:
            return

        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        axes = axes.flatten()

        for idx, metric in enumerate(available[:4]):
            ax = axes[idx]
            metric_data = ratios[ratios['Metric'] == metric]

            if metric_data.empty:
                ax.text(0.5, 0.5, f'No {metric} data', ha='center', va='center',
                       transform=ax.transAxes)
                continue

            # Log2 Fold Change 분포
            log2_fc = metric_data['Log2_FC'].dropna()

            colors_arr = ['green' if x > 0.5 else 'red' if x < -0.5 else 'gray'
                         for x in log2_fc]
            ax.hist(log2_fc, bins=30, edgecolor='black', alpha=0.7, color=COLORS['stim'])
            ax.axvline(0, color='black', linestyle='--', linewidth=2, label='No change')
            ax.axvline(0.5, color='green', linestyle=':', linewidth=1.5, label='FC > 1.4')
            ax.axvline(-0.5, color='red', linestyle=':', linewidth=1.5, label='FC < 0.7')

            ax.set_xlabel('Log2 Fold Change (STIM/BASE)', fontweight='bold')
            ax.set_ylabel('Count', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}\n'
                        f'(Mean FC: {metric_data["STIM_BASE_Ratio"].mean():.2f})',
                        fontweight='bold')
            ax.legend(fontsize=8)
            ax.grid(alpha=0.3)

        for idx in range(len(available[:4]), 4):
            axes[idx].set_visible(False)

        plt.suptitle('Light Response: STIM/BASE Ratio Distribution\n'
                    '(Duration-normalized metrics)',
                    fontweight='bold', fontsize=14)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'stim_base_ratios.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_condition_comparison(self):
        """Condition별 비교 (Control vs Drug vs Washout)"""
        if self.ratio_analyzer.condition_ratios is None:
            return

        cond_ratios = self.ratio_analyzer.condition_ratios

        # Drug vs Control
        drug_data = cond_ratios[cond_ratios['Comparison'] == 'Drug_vs_Control']

        if drug_data.empty:
            return

        rate_metrics = ['spikes_per_min', 'bursts_per_min', 'mean_firing_rate_hz']
        available = [m for m in rate_metrics if m in drug_data['Metric'].unique()]

        if not available:
            return

        fig, axes = plt.subplots(1, len(available), figsize=(6*len(available), 6))
        if len(available) == 1:
            axes = [axes]

        for idx, metric in enumerate(available):
            ax = axes[idx]
            metric_data = drug_data[drug_data['Metric'] == metric]

            if metric_data.empty:
                continue

            # Bar plot: Control vs Drug
            x = np.arange(len(metric_data))
            width = 0.35

            # 데이터가 너무 많으면 상위 10개만
            if len(metric_data) > 10:
                metric_data = metric_data.head(10)
                x = np.arange(10)

            ax.bar(x - width/2, metric_data['Control_Mean'], width,
                  label='Control', color=COLORS['control'], alpha=0.8, edgecolor='black')
            ax.bar(x + width/2, metric_data['Drug_Mean'], width,
                  label='Drug', color=COLORS['drug'], alpha=0.8, edgecolor='black')

            ax.set_xlabel('Well', fontweight='bold')
            ax.set_ylabel('Value', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}\n'
                        f'(Drug/Control ratio: {metric_data["Drug_Control_Ratio"].mean():.2f})',
                        fontweight='bold')
            ax.legend()
            ax.grid(axis='y', alpha=0.3)

            if 'Well' in metric_data.columns:
                ax.set_xticks(x)
                ax.set_xticklabels(metric_data['Well'].values, rotation=45, ha='right')

        plt.suptitle('Control vs Drug Comparison\n'
                    '(Rate-based metrics, duration-independent)',
                    fontweight='bold', fontsize=14)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'condition_comparison.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_fold_change_heatmap(self):
        """Fold Change 히트맵"""
        if self.ratio_analyzer.stim_base_ratios is None:
            return

        ratios = self.ratio_analyzer.stim_base_ratios

        # Well × Metric 피벗
        rate_metrics = ['spikes_per_min', 'bursts_per_min', 'mean_firing_rate_hz',
                       'burst_frequency_hz', 'spikes_per_burst_avg']
        available = [m for m in rate_metrics if m in ratios['Metric'].unique()]

        if not available:
            return

        pivot = ratios[ratios['Metric'].isin(available)].pivot_table(
            index='Well', columns='Metric', values='Log2_FC', aggfunc='mean')

        if pivot.empty:
            return

        fig, ax = plt.subplots(figsize=(max(10, len(pivot.columns)*1.5),
                                        max(8, len(pivot.index)*0.4)))

        sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn', center=0,
                   cbar_kws={'label': 'Log2 Fold Change'}, ax=ax,
                   linewidths=0.5, linecolor='white')

        ax.set_title('Light Response Fold Change (STIM/BASE)\n'
                    '(Well × Metric, Log2 scale)',
                    fontweight='bold', fontsize=14)
        ax.set_xlabel('Metric', fontweight='bold')
        ax.set_ylabel('Well', fontweight='bold')

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(self.output_dir / 'fold_change_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_metric_correlation(self):
        """Rate metric 간 상관관계"""
        rate_metrics = ['spikes_per_min', 'mean_firing_rate_hz', 'bursts_per_min',
                       'burst_frequency_hz']
        available = [m for m in rate_metrics if m in self.df['Metric'].unique()]

        if len(available) < 2:
            return

        # Pivot to wide format
        pivot = self.df[self.df['Metric'].isin(available)].pivot_table(
            index=['Well', 'Electrode_ID', 'BASE_STIM'],
            columns='Metric', values='Value', aggfunc='mean')

        if pivot.empty or len(pivot.columns) < 2:
            return

        # Correlation matrix
        corr = pivot.corr()

        fig, ax = plt.subplots(figsize=(10, 8))

        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
        sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0,
                   mask=mask, cbar_kws={'label': 'Correlation'}, ax=ax,
                   linewidths=0.5, linecolor='white')

        ax.set_title('Rate Metrics Correlation\n(Duration-independent)',
                    fontweight='bold', fontsize=14)

        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'metric_correlation.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_condition_timeline(self):
        """Condition 순서 (Control → Drug → Washout)"""
        if 'Condition' not in self.df.columns:
            return

        rate_metrics = ['spikes_per_min', 'mean_firing_rate_hz']
        available = [m for m in rate_metrics if m in self.df['Metric'].unique()]

        if not available:
            return

        fig, axes = plt.subplots(1, len(available), figsize=(8*len(available), 6))
        if len(available) == 1:
            axes = [axes]

        condition_order = ['CONTROL', 'DRUG', 'WASHOUT']

        for idx, metric in enumerate(available):
            ax = axes[idx]
            metric_data = self.df[self.df['Metric'] == metric]

            # Condition별 평균
            means = []
            stds = []
            labels = []
            colors = []

            for cond in condition_order:
                cond_data = metric_data[metric_data['Condition'] == cond]['Value']
                if len(cond_data) > 0:
                    means.append(cond_data.mean())
                    stds.append(cond_data.std())
                    labels.append(cond)
                    colors.append(COLORS.get(cond.lower(), COLORS['neutral']))

            if means:
                x = np.arange(len(labels))
                bars = ax.bar(x, means, yerr=stds, capsize=5,
                             color=colors, edgecolor='black', alpha=0.8)

                # 연결선
                ax.plot(x, means, 'ko-', markersize=8, linewidth=2, alpha=0.6)

                ax.set_xticks(x)
                ax.set_xticklabels(labels, fontweight='bold')
                ax.set_ylabel('Value', fontweight='bold')
                ax.set_title(f'{metric.replace("_", " ").title()}', fontweight='bold')
                ax.grid(axis='y', alpha=0.3)

                # Fold change annotation
                if len(means) >= 2:
                    fc_drug = means[1] / means[0] if means[0] > 0 else np.nan
                    if pd.notna(fc_drug):
                        ax.annotate(f'Drug/Control: {fc_drug:.2f}x',
                                   xy=(0.5, max(means)*0.9),
                                   fontsize=10, fontweight='bold',
                                   ha='center')

        plt.suptitle('Activity Changes: Control → Drug → Washout\n'
                    '(Rate-based metrics)',
                    fontweight='bold', fontsize=14)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'condition_timeline.png', dpi=300, bbox_inches='tight')
        plt.close(fig)


# =============================================================================
# EXCEL CREATOR
# =============================================================================

class VariableDurationExcelCreator:
    """Excel 파일 생성"""

    def __init__(self, df: pd.DataFrame, ratio_analyzer: RatioAnalyzer,
                 output_path: Path):
        self.df = df
        self.ratio_analyzer = ratio_analyzer
        self.output_path = Path(output_path)

    @timer
    def create(self):
        """Excel 파일 생성"""
        print('\n[EXCEL] Creating Excel file...')

        with pd.ExcelWriter(self.output_path, engine='openpyxl') as writer:
            # Sheet 1: Normalized Data
            self.df.to_excel(writer, sheet_name='Normalized_Data', index=False)

            # Sheet 2: STIM/BASE Ratios
            if self.ratio_analyzer.stim_base_ratios is not None:
                self.ratio_analyzer.stim_base_ratios.to_excel(
                    writer, sheet_name='STIM_BASE_Ratios', index=False)

            # Sheet 3: Condition Ratios
            if self.ratio_analyzer.condition_ratios is not None:
                self.ratio_analyzer.condition_ratios.to_excel(
                    writer, sheet_name='Condition_Ratios', index=False)

            # Sheet 4: Summary
            if self.ratio_analyzer.summary is not None:
                self.ratio_analyzer.summary.to_excel(
                    writer, sheet_name='Summary', index=False)

            # Sheet 5: Duration Info
            duration_info = self.df.groupby(['Condition', 'BASE_STIM']).agg({
                'TIME_DURATION_SEC': ['mean', 'std', 'min', 'max', 'count']
            }).reset_index()
            duration_info.columns = ['Condition', 'BASE_STIM',
                                     'Duration_Mean', 'Duration_Std',
                                     'Duration_Min', 'Duration_Max', 'Count']
            duration_info.to_excel(writer, sheet_name='Duration_Info', index=False)

            # Sheet 6: Recommended Metrics
            recommended = pd.DataFrame({
                'Metric': ['spikes_per_min', 'bursts_per_min', 'mean_firing_rate_hz',
                          'burst_frequency_hz', 'burst_duration_avg_s',
                          'spikes_per_burst_avg'],
                'Type': ['Rate (normalized)', 'Rate (normalized)', 'Rate (original)',
                        'Rate (original)', 'Duration', 'Per-burst'],
                'Description': [
                    'Spikes per minute (from number_of_spikes / duration)',
                    'Bursts per minute (from number_of_bursts / duration)',
                    'Original mean firing rate in Hz',
                    'Original burst frequency in Hz',
                    'Average burst duration in seconds',
                    'Average spikes per burst'
                ],
                'Duration_Independent': ['Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'Yes'],
                'Recommended_for_Comparison': ['Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'Yes']
            })
            recommended.to_excel(writer, sheet_name='Recommended_Metrics', index=False)

        print(f'  ✓ Saved: {self.output_path.name}')


# =============================================================================
# DASHBOARD
# =============================================================================

class VariableDurationDashboard:
    """종합 대시보드 생성"""

    def __init__(self, df: pd.DataFrame, ratio_analyzer: RatioAnalyzer,
                 output_path: Path):
        self.df = df
        self.ratio_analyzer = ratio_analyzer
        self.output_path = Path(output_path)

    @timer
    def create(self):
        """대시보드 생성"""
        print('\n[DASHBOARD] Creating dashboard...')

        fig = plt.figure(figsize=(20, 16))
        gs = fig.add_gridspec(4, 4, hspace=0.35, wspace=0.3)

        # Row 1: Duration info
        ax1 = fig.add_subplot(gs[0, :2])
        self._plot_duration_summary(ax1)

        ax2 = fig.add_subplot(gs[0, 2:])
        self._plot_condition_summary(ax2)

        # Row 2: Rate metrics
        ax3 = fig.add_subplot(gs[1, :2])
        self._plot_rate_metrics(ax3)

        ax4 = fig.add_subplot(gs[1, 2:])
        self._plot_stim_base_summary(ax4)

        # Row 3: Condition comparison
        ax5 = fig.add_subplot(gs[2, :2])
        self._plot_drug_effect(ax5)

        ax6 = fig.add_subplot(gs[2, 2:])
        self._plot_fold_change_summary(ax6)

        # Row 4: Summary stats
        ax7 = fig.add_subplot(gs[3, :2])
        self._plot_key_findings(ax7)

        ax8 = fig.add_subplot(gs[3, 2:])
        self._plot_recommendations(ax8)

        # Title
        fig.suptitle('MEA Variable Duration Analysis Dashboard\n'
                    '(Duration-normalized metrics for cross-condition comparison)',
                    fontweight='bold', fontsize=16, y=0.98)

        plt.savefig(self.output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)

        print(f'  ✓ Dashboard saved: {self.output_path.name}')

    def _plot_duration_summary(self, ax):
        """Recording duration 요약"""
        if 'TIME_DURATION_SEC' not in self.df.columns:
            ax.text(0.5, 0.5, 'No duration data', ha='center', va='center',
                   transform=ax.transAxes)
            return

        if 'Condition' in self.df.columns:
            conditions = self.df['Condition'].unique()
            durations = []
            labels = []
            colors = []

            for cond in ['CONTROL', 'DRUG', 'WASHOUT']:
                cond_data = self.df[self.df['Condition'] == cond]['TIME_DURATION_SEC']
                if len(cond_data) > 0:
                    durations.append(cond_data.mean())
                    labels.append(f'{cond}\n({cond_data.mean():.0f}s)')
                    colors.append(COLORS.get(cond.lower(), COLORS['neutral']))

            if durations:
                ax.bar(range(len(durations)), durations, color=colors,
                      edgecolor='black', alpha=0.8)
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(labels, fontweight='bold')
        else:
            mean_dur = self.df['TIME_DURATION_SEC'].mean()
            ax.bar([0], [mean_dur], color=COLORS['neutral'], edgecolor='black')
            ax.set_xticks([0])
            ax.set_xticklabels([f'All\n({mean_dur:.0f}s)'])

        ax.set_ylabel('Duration (sec)', fontweight='bold')
        ax.set_title('Recording Duration by Condition', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    def _plot_condition_summary(self, ax):
        """Condition별 데이터 수"""
        if 'Condition' not in self.df.columns:
            ax.text(0.5, 0.5, 'No condition data', ha='center', va='center',
                   transform=ax.transAxes)
            return

        counts = self.df['Condition'].value_counts()
        colors = [COLORS.get(c.lower(), COLORS['neutral']) for c in counts.index]

        ax.pie(counts.values, labels=counts.index, colors=colors, autopct='%1.1f%%',
              explode=[0.02]*len(counts), shadow=True)
        ax.set_title('Data Distribution by Condition', fontweight='bold')

    def _plot_rate_metrics(self, ax):
        """Rate 기반 metric 평균"""
        rate_metrics = ['spikes_per_min', 'mean_firing_rate_hz', 'bursts_per_min']
        available = [m for m in rate_metrics if m in self.df['Metric'].unique()]

        if not available:
            ax.text(0.5, 0.5, 'No rate metrics', ha='center', va='center',
                   transform=ax.transAxes)
            return

        means = []
        stds = []
        for m in available:
            metric_data = self.df[self.df['Metric'] == m]['Value']
            means.append(metric_data.mean())
            stds.append(metric_data.std())

        x = np.arange(len(available))
        ax.bar(x, means, yerr=stds, capsize=5, color=COLORS['positive'],
              edgecolor='black', alpha=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels([m.replace('_', '\n') for m in available], fontsize=9)
        ax.set_ylabel('Value', fontweight='bold')
        ax.set_title('Rate-Based Metrics (All Data)', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    def _plot_stim_base_summary(self, ax):
        """STIM/BASE ratio 요약"""
        if self.ratio_analyzer.stim_base_ratios is None:
            ax.text(0.5, 0.5, 'No STIM/BASE data', ha='center', va='center',
                   transform=ax.transAxes)
            return

        ratios = self.ratio_analyzer.stim_base_ratios

        # Response direction 분포
        directions = ratios['Response_Direction'].value_counts()
        colors = {'increase': COLORS['positive'],
                 'decrease': COLORS['negative'],
                 'no_change': COLORS['neutral']}

        ax.bar(range(len(directions)), directions.values,
              color=[colors.get(d, COLORS['neutral']) for d in directions.index],
              edgecolor='black', alpha=0.8)
        ax.set_xticks(range(len(directions)))
        ax.set_xticklabels(directions.index, fontweight='bold')
        ax.set_ylabel('Count', fontweight='bold')
        ax.set_title('Light Response Direction\n(STIM/BASE)', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    def _plot_drug_effect(self, ax):
        """Drug 효과 요약"""
        if self.ratio_analyzer.condition_ratios is None:
            ax.text(0.5, 0.5, 'No drug effect data', ha='center', va='center',
                   transform=ax.transAxes)
            return

        cond_ratios = self.ratio_analyzer.condition_ratios
        drug_data = cond_ratios[cond_ratios['Comparison'] == 'Drug_vs_Control']

        if drug_data.empty:
            ax.text(0.5, 0.5, 'No Drug vs Control data', ha='center', va='center',
                   transform=ax.transAxes)
            return

        # Metric별 Drug/Control ratio
        rate_metrics = ['spikes_per_min', 'mean_firing_rate_hz', 'bursts_per_min']
        available = [m for m in rate_metrics if m in drug_data['Metric'].unique()]

        if not available:
            ax.text(0.5, 0.5, 'No rate metrics', ha='center', va='center',
                   transform=ax.transAxes)
            return

        ratios = []
        for m in available:
            metric_data = drug_data[drug_data['Metric'] == m]
            ratios.append(metric_data['Drug_Control_Ratio'].mean())

        x = np.arange(len(available))
        bars = ax.bar(x, ratios, color=COLORS['drug'], edgecolor='black', alpha=0.8)
        ax.axhline(1, color='black', linestyle='--', linewidth=2, label='No change')

        ax.set_xticks(x)
        ax.set_xticklabels([m.replace('_', '\n') for m in available], fontsize=9)
        ax.set_ylabel('Drug/Control Ratio', fontweight='bold')
        ax.set_title('Drug Effect\n(Ratio > 1: increase, < 1: decrease)', fontweight='bold')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

    def _plot_fold_change_summary(self, ax):
        """Fold change 요약 히트맵 (미니)"""
        if self.ratio_analyzer.stim_base_ratios is None:
            ax.text(0.5, 0.5, 'No fold change data', ha='center', va='center',
                   transform=ax.transAxes)
            return

        ratios = self.ratio_analyzer.stim_base_ratios

        # Condition × Metric 평균 FC
        if 'Condition' in ratios.columns:
            rate_metrics = ['spikes_per_min', 'mean_firing_rate_hz']
            available = [m for m in rate_metrics if m in ratios['Metric'].unique()]

            if available:
                pivot = ratios[ratios['Metric'].isin(available)].pivot_table(
                    index='Condition', columns='Metric', values='Log2_FC', aggfunc='mean')

                if not pivot.empty:
                    sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn', center=0,
                               cbar_kws={'label': 'Log2 FC'}, ax=ax)
                    ax.set_title('Light Response by Condition\n(Log2 Fold Change)',
                                fontweight='bold')
                    return

        ax.text(0.5, 0.5, 'Insufficient data for heatmap', ha='center', va='center',
               transform=ax.transAxes)

    def _plot_key_findings(self, ax):
        """주요 발견 사항"""
        ax.axis('off')

        findings = ['KEY FINDINGS', '='*40, '']

        # Duration 정보
        if 'TIME_DURATION_SEC' in self.df.columns:
            durations = self.df['TIME_DURATION_SEC'].unique()
            findings.append(f'Recording durations: {len(durations)} unique')
            findings.append(f'  Range: {min(durations):.0f}s - {max(durations):.0f}s')
            findings.append('')

        # STIM/BASE 결과
        if self.ratio_analyzer.stim_base_ratios is not None:
            ratios = self.ratio_analyzer.stim_base_ratios
            n_increase = (ratios['Response_Direction'] == 'increase').sum()
            n_decrease = (ratios['Response_Direction'] == 'decrease').sum()
            findings.append(f'Light Response:')
            findings.append(f'  Increase: {n_increase}')
            findings.append(f'  Decrease: {n_decrease}')
            findings.append('')

        # Drug 효과
        if self.ratio_analyzer.condition_ratios is not None:
            drug_data = self.ratio_analyzer.condition_ratios[
                self.ratio_analyzer.condition_ratios['Comparison'] == 'Drug_vs_Control']
            if not drug_data.empty:
                mean_ratio = drug_data['Drug_Control_Ratio'].mean()
                findings.append(f'Drug Effect:')
                findings.append(f'  Mean Drug/Control ratio: {mean_ratio:.2f}')

        ax.text(0.05, 0.95, '\n'.join(findings), transform=ax.transAxes,
               fontsize=11, verticalalignment='top', fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))

    def _plot_recommendations(self, ax):
        """권장 사항"""
        ax.axis('off')

        recommendations = [
            'RECOMMENDATIONS',
            '='*40,
            '',
            'For comparing different recording durations:',
            '',
            '1. Use RATE-BASED metrics:',
            '   - spikes_per_min (not number_of_spikes)',
            '   - bursts_per_min (not number_of_bursts)',
            '   - mean_firing_rate_hz (already rate)',
            '',
            '2. Use RATIO comparisons:',
            '   - STIM/BASE ratio for light response',
            '   - Drug/Control ratio for drug effect',
            '',
            '3. Duration-INDEPENDENT metrics:',
            '   - burst_duration_avg_s',
            '   - spikes_per_burst_avg',
            '   - isi_cv, ibi_cv',
        ]

        ax.text(0.05, 0.95, '\n'.join(recommendations), transform=ax.transAxes,
               fontsize=10, verticalalignment='top', fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.3))


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class VariableDurationAnalyzer:
    """
    Variable Recording Duration Analyzer

    다양한 측정 시간(recording duration)을 감안한 MEA 분석 파이프라인

    Usage:
        analyzer = VariableDurationAnalyzer(
            electrode_data_path=r"D:\\output\\electrode_all_long.parquet",
            output_dir=r"D:\\output\\variable_duration_analysis"
        )
        analyzer.run()
    """

    def __init__(self, electrode_data_path: str, output_dir: str,
                 config: Optional[VariableDurationConfig] = None):
        """
        Parameters:
        -----------
        electrode_data_path : str
            electrode_all_long.parquet 또는 .csv 경로
        output_dir : str
            출력 디렉토리
        config : VariableDurationConfig, optional
            분석 설정
        """
        self.electrode_data_path = Path(electrode_data_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.config = config or VariableDurationConfig()

        self.raw_data = None
        self.normalized_data = None
        self.ratio_analyzer = None

        self.performance = PerformanceMonitor()
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    def run(self):
        """전체 파이프라인 실행"""
        print('='*80)
        print('MEA VARIABLE DURATION ANALYZER')
        print('='*80)
        print(f'\nInput: {self.electrode_data_path}')
        print(f'Output: {self.output_dir}')
        print(f'Timestamp: {self.timestamp}')
        print(f'\nConfiguration:')
        print(f'  Normalize to per-minute: {self.config.normalize_to_per_min}')
        print(f'  Min recording duration: {self.config.min_recording_duration_sec}s')
        print('='*80)

        pipeline_start = time.time()

        # Stage 1: Load data
        stage_start = time.time()
        print('\n[STAGE 1] Loading data...')
        self._load_data()
        self.performance.record('Stage 1: Data Loading', time.time() - stage_start)

        if self.raw_data is None or self.raw_data.empty:
            print('❌ Failed to load data')
            return self

        # Stage 2: Normalize by duration
        stage_start = time.time()
        print('\n[STAGE 2] Normalizing by recording duration...')
        normalizer = DurationNormalizer(self.config)
        self.normalized_data = normalizer.normalize(self.raw_data)
        self.performance.record('Stage 2: Normalization', time.time() - stage_start)

        # Stage 3: Classify conditions
        stage_start = time.time()
        print('\n[STAGE 3] Classifying conditions...')
        classifier = ConditionClassifier(self.config)
        self.normalized_data = classifier.classify(self.normalized_data)
        self.performance.record('Stage 3: Classification', time.time() - stage_start)

        # Stage 4: Ratio analysis
        stage_start = time.time()
        print('\n[STAGE 4] Ratio analysis...')
        self.ratio_analyzer = RatioAnalyzer(self.normalized_data, self.output_dir)
        self.ratio_analyzer.analyze_stim_base_ratio()
        self.ratio_analyzer.analyze_condition_ratios()
        self.ratio_analyzer.create_summary()
        self.performance.record('Stage 4: Ratio Analysis', time.time() - stage_start)

        # Stage 5: Visualizations
        stage_start = time.time()
        print('\n[STAGE 5] Creating visualizations...')
        visualizer = VariableDurationVisualizer(
            self.normalized_data, self.ratio_analyzer, self.output_dir)
        visualizer.create_all()
        self.performance.record('Stage 5: Visualizations', time.time() - stage_start)

        # Stage 6: Excel
        stage_start = time.time()
        print('\n[STAGE 6] Creating Excel...')
        excel_path = self.output_dir / 'VARIABLE_DURATION_ANALYSIS.xlsx'
        excel_creator = VariableDurationExcelCreator(
            self.normalized_data, self.ratio_analyzer, excel_path)
        excel_creator.create()
        self.performance.record('Stage 6: Excel', time.time() - stage_start)

        # Stage 7: Dashboard
        stage_start = time.time()
        print('\n[STAGE 7] Creating dashboard...')
        dashboard_path = self.output_dir / 'VARIABLE_DURATION_DASHBOARD.png'
        dashboard = VariableDurationDashboard(
            self.normalized_data, self.ratio_analyzer, dashboard_path)
        dashboard.create()
        self.performance.record('Stage 7: Dashboard', time.time() - stage_start)

        # Save normalized data
        self.normalized_data.to_parquet(
            self.output_dir / 'normalized_data.parquet', index=False)
        self.normalized_data.to_csv(
            self.output_dir / 'normalized_data.csv', index=False)

        # Summary
        total_time = time.time() - pipeline_start
        self.performance.record('Total Pipeline', total_time)
        self.performance.print_summary()

        print('\n' + '='*80)
        print('🎉 VARIABLE DURATION ANALYSIS COMPLETE!')
        print('='*80)
        print(f'\nResults: {self.output_dir}')
        print(f'Total time: {total_time:.2f}s')
        print('\nKey outputs:')
        print('  - normalized_data.parquet: Duration-normalized data')
        print('  - VARIABLE_DURATION_ANALYSIS.xlsx: Full analysis results')
        print('  - VARIABLE_DURATION_DASHBOARD.png: Summary dashboard')
        print('  - ratio_analysis/: STIM/BASE and Condition ratio results')
        print('  - visualizations/: All plots')
        print('='*80)

        gc.collect()
        return self

    def _load_data(self):
        """데이터 로드"""
        if self.electrode_data_path.suffix == '.parquet':
            self.raw_data = pd.read_parquet(self.electrode_data_path)
        else:
            self.raw_data = pd.read_csv(self.electrode_data_path)

        print(f'  ✓ Loaded: {len(self.raw_data)} rows')
        print(f'  ✓ Electrodes: {self.raw_data["Electrode_ID"].nunique()}')
        print(f'  ✓ Metrics: {self.raw_data["Metric"].nunique()}')

        # Duration 정보 출력
        if 'TIME_DURATION_SEC' in self.raw_data.columns:
            durations = self.raw_data['TIME_DURATION_SEC'].unique()
            print(f'  ✓ Recording durations: {sorted(durations)} sec')


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Example usage
    analyzer = VariableDurationAnalyzer(
        electrode_data_path=r"D:\MyProjects\#4-2\output_electrode2\electrode_all_long.parquet",
        output_dir=r"D:\MyProjects\#4-2\output_electrode2\variable_duration_analysis",
        config=VariableDurationConfig(
            normalize_to_per_min=True,
            min_recording_duration_sec=30.0,
            control_conditions=['NONE', 'CONTROL', 'CTRL', 'VEH'],
            washout_conditions=['WASHOUT', 'WASH', 'WO']
        )
    )
    analyzer.run()
