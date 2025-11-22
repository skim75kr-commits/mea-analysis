"""
MEA Drug Effect Analyzer
=========================
CONTROL 상태와 DRUG 투여 후의 Light Response 변화를 비교 분석

핵심 개념:
- Light Response (LR) = STIM - BASE (또는 STIM/BASE ratio)
- Drug Effect = LR_DRUG - LR_CONTROL (Light Response의 변화)

분석 흐름:
1. 동일한 top-score electrode 사용 (mea_electrode_analyzer_v3_clean에서 선정)
2. CONTROL 조건에서 Light Response 계산
3. DRUG 조건에서 Light Response 계산
4. 두 조건 간 차이 분석 및 통계 검정

입력 파일:
- electrode_all_long.parquet: 전체 electrode 데이터 (CONTROL + DRUG)
- electrode_response_scores.csv: electrode score (CONTROL 기준)

출력:
- Drug effect 분석 결과 (CSV, Excel)
- 비교 시각화
- 통계 검정 결과

Usage:
    from mea_drug_effect_analyzer import DrugEffectAnalyzer

    analyzer = DrugEffectAnalyzer(
        electrode_data_path=r"D:\\output\\electrode_all_long.parquet",
        scores_path=r"D:\\output\\electrode_scores\\electrode_response_scores.csv",
        output_dir=r"D:\\output\\drug_effect_analysis",
        top_n_per_well=3,
        control_label="CONTROL",  # EXP_TYPE 또는 DRUG 컬럼의 control 값
        drug_labels=["DRUG_A", "DRUG_B"]  # 비교할 drug 조건들
    )
    analyzer.run()
"""

from pathlib import Path
import time
from functools import wraps
from typing import Optional, List, Dict, Tuple, Union
from datetime import datetime
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
    'control': '#5DADE2',      # Sky blue
    'drug': '#EC7063',         # Coral red
    'base': '#85929E',         # Gray
    'stim': '#F4D03F',         # Yellow
    'positive': '#58D68D',     # Green
    'negative': '#E74C3C',     # Red
    'neutral': '#95A5A6',      # Gray
    'BL': '#0066CC',           # Blue Light
    'GR': '#00AA00',           # Green
    'OR': '#FF8800',           # Orange
    'RD': '#DD0000',           # Red
}


# =============================================================================
# LIGHT RESPONSE CALCULATOR
# =============================================================================

class LightResponseCalculator:
    """
    Light Response 계산기

    Light Response 정의:
    - Absolute: LR = STIM - BASE
    - Ratio: LR = STIM / BASE
    - Percent Change: LR = (STIM - BASE) / BASE * 100
    """

    def __init__(self, df: pd.DataFrame, electrode_ids: List[str],
                 score_map: Optional[Dict[str, float]] = None):
        self.df = df
        self.electrode_ids = electrode_ids
        # 개선: eps를 1e-3으로 상향하여 극단적 ratio 방지
        self.eps = 1e-3
        # 개선: BASE 값 최소 threshold
        self.min_base_threshold = 0.1
        # Score-weighted 계산을 위한 score map
        self.score_map = score_map or {}

    def calculate(self,
                  condition_col: str = 'EXP_TYPE',
                  condition_value: str = 'CONTROL',
                  metrics: Optional[List[str]] = None) -> pd.DataFrame:
        """
        특정 조건에서의 Light Response 계산

        Parameters:
        -----------
        condition_col : str
            조건을 구분하는 컬럼 (EXP_TYPE 또는 DRUG)
        condition_value : str
            해당 조건의 값 (예: 'CONTROL', 'DRUG_A')
        metrics : List[str], optional
            계산할 metric 목록

        Returns:
        --------
        pd.DataFrame
            Light Response 데이터
        """
        # 선택된 electrode 필터링
        filtered = self.df[self.df['Electrode_ID'].isin(self.electrode_ids)].copy()

        # 조건 필터링
        if condition_col in filtered.columns:
            filtered = filtered[filtered[condition_col] == condition_value]

        if filtered.empty:
            print(f"  ⚠ No data for condition: {condition_col}={condition_value}")
            return pd.DataFrame()

        # Metric 필터링
        if metrics is None:
            metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']

        available_metrics = [m for m in metrics if m in filtered['Metric'].unique()]

        if not available_metrics:
            print(f"  ⚠ No matching metrics found")
            return pd.DataFrame()

        results = []

        # Grouping keys
        group_keys = ['Electrode_ID', 'Well', 'Metric']
        if 'LIGHT_CODE' in filtered.columns:
            group_keys.append('LIGHT_CODE')

        # BASE와 STIM 분리
        base_df = filtered[filtered['BASE_STIM'] == 'BASE']
        stim_df = filtered[filtered['BASE_STIM'] == 'STIM']

        for metric in available_metrics:
            base_metric = base_df[base_df['Metric'] == metric]
            stim_metric = stim_df[stim_df['Metric'] == metric]

            # Group by electrode (and light_code if exists)
            merge_keys = ['Electrode_ID', 'Well']
            if 'LIGHT_CODE' in filtered.columns:
                merge_keys.append('LIGHT_CODE')

            base_grouped = base_metric.groupby(merge_keys)['Value'].mean().reset_index()
            base_grouped = base_grouped.rename(columns={'Value': 'BASE_Value'})

            stim_grouped = stim_metric.groupby(merge_keys)['Value'].mean().reset_index()
            stim_grouped = stim_grouped.rename(columns={'Value': 'STIM_Value'})

            # Merge BASE and STIM
            merged = base_grouped.merge(stim_grouped, on=merge_keys, how='inner')

            if merged.empty:
                continue

            # Calculate Light Response metrics
            merged['Metric'] = metric
            merged['Condition'] = condition_value

            # Absolute difference
            merged['LR_Absolute'] = merged['STIM_Value'] - merged['BASE_Value']

            # 개선: Ratio 계산 시 BASE 값 검증 및 clipping
            def calc_stable_ratio(row):
                base_val = row['BASE_Value']
                stim_val = row['STIM_Value']
                if base_val >= self.min_base_threshold:
                    ratio = (stim_val + self.eps) / (base_val + self.eps)
                else:
                    # BASE가 작으면 STIM 값 기반으로 판단
                    if stim_val > self.min_base_threshold:
                        ratio = stim_val / self.min_base_threshold
                    else:
                        ratio = 1.0
                # Ratio를 합리적인 범위로 제한 (0.01 ~ 100)
                return np.clip(ratio, 0.01, 100)

            merged['LR_Ratio'] = merged.apply(calc_stable_ratio, axis=1)

            # Percent change (with stable calculation)
            merged['LR_PctChange'] = ((merged['STIM_Value'] - merged['BASE_Value']) /
                                       (merged['BASE_Value'].clip(lower=self.min_base_threshold)) * 100)
            # Clip percent change to reasonable range
            merged['LR_PctChange'] = merged['LR_PctChange'].clip(-1000, 1000)

            # Log2 Fold Change (symmetric around 0)
            merged['LR_Log2FC'] = np.log2(merged['LR_Ratio'])

            # 개선: Score 추가 (available인 경우)
            if self.score_map:
                merged['Score'] = merged['Electrode_ID'].map(self.score_map).fillna(1.0)

            results.append(merged)

        if not results:
            return pd.DataFrame()

        result_df = pd.concat(results, ignore_index=True)
        return result_df


# =============================================================================
# DRUG EFFECT CALCULATOR
# =============================================================================

class DrugEffectCalculator:
    """
    Drug Effect 계산기

    Drug Effect = Light Response (DRUG) - Light Response (CONTROL)

    분석 수준:
    1. Electrode level: 개별 electrode의 drug effect
    2. Well level: Well 단위 평균
    3. Overall: 전체 평균
    """

    def __init__(self, control_lr: pd.DataFrame, drug_lr: pd.DataFrame):
        """
        Parameters:
        -----------
        control_lr : pd.DataFrame
            CONTROL 조건의 Light Response
        drug_lr : pd.DataFrame
            DRUG 조건의 Light Response
        """
        self.control_lr = control_lr
        self.drug_lr = drug_lr
        self.drug_effect = None

    @timer
    def calculate(self) -> pd.DataFrame:
        """Drug Effect 계산"""
        print("\n[DRUG EFFECT] Calculating drug effects...")

        if self.control_lr.empty or self.drug_lr.empty:
            print("  ⚠ Missing control or drug data")
            return pd.DataFrame()

        # Merge keys
        merge_keys = ['Electrode_ID', 'Well', 'Metric']
        if 'LIGHT_CODE' in self.control_lr.columns and 'LIGHT_CODE' in self.drug_lr.columns:
            merge_keys.append('LIGHT_CODE')

        # Rename columns for clarity
        control = self.control_lr.copy()
        drug = self.drug_lr.copy()

        control_cols = {
            'BASE_Value': 'CTRL_BASE',
            'STIM_Value': 'CTRL_STIM',
            'LR_Absolute': 'CTRL_LR_Abs',
            'LR_Ratio': 'CTRL_LR_Ratio',
            'LR_PctChange': 'CTRL_LR_Pct',
            'LR_Log2FC': 'CTRL_LR_Log2FC'
        }

        drug_cols = {
            'BASE_Value': 'DRUG_BASE',
            'STIM_Value': 'DRUG_STIM',
            'LR_Absolute': 'DRUG_LR_Abs',
            'LR_Ratio': 'DRUG_LR_Ratio',
            'LR_PctChange': 'DRUG_LR_Pct',
            'LR_Log2FC': 'DRUG_LR_Log2FC',
            'Condition': 'Drug_Condition'
        }

        control = control.rename(columns=control_cols)
        drug = drug.rename(columns=drug_cols)

        # Keep only necessary columns
        control_keep = merge_keys + list(control_cols.values())
        drug_keep = merge_keys + list(drug_cols.values())

        control = control[[c for c in control_keep if c in control.columns]]
        drug = drug[[c for c in drug_keep if c in drug.columns]]

        # Merge control and drug
        merged = control.merge(drug, on=merge_keys, how='inner')

        if merged.empty:
            print("  ⚠ No matching electrode data between CONTROL and DRUG")
            return pd.DataFrame()

        # Calculate Drug Effects
        # 1. Absolute change in Light Response
        merged['DrugEffect_LR_Abs'] = merged['DRUG_LR_Abs'] - merged['CTRL_LR_Abs']

        # 2. Ratio of Light Response ratios
        merged['DrugEffect_LR_Ratio'] = merged['DRUG_LR_Ratio'] / merged['CTRL_LR_Ratio']

        # 3. Change in percent change
        merged['DrugEffect_LR_Pct'] = merged['DRUG_LR_Pct'] - merged['CTRL_LR_Pct']

        # 4. Change in Log2 Fold Change
        merged['DrugEffect_Log2FC'] = merged['DRUG_LR_Log2FC'] - merged['CTRL_LR_Log2FC']

        # 5. Drug effect direction
        merged['DrugEffect_Direction'] = np.where(
            merged['DrugEffect_LR_Abs'] > 0, 'Enhanced',
            np.where(merged['DrugEffect_LR_Abs'] < 0, 'Suppressed', 'No Change')
        )

        # 6. Baseline change (drug effect on spontaneous activity)
        # 개선: eps를 1e-3으로 통일, 안정적인 계산
        eps = 1e-3
        min_threshold = 0.1
        merged['Baseline_Change'] = merged['DRUG_BASE'] - merged['CTRL_BASE']
        merged['Baseline_Change_Pct'] = ((merged['DRUG_BASE'] - merged['CTRL_BASE']) /
                                          (merged['CTRL_BASE'].clip(lower=min_threshold)) * 100)
        # Clip to reasonable range
        merged['Baseline_Change_Pct'] = merged['Baseline_Change_Pct'].clip(-1000, 1000)

        # 7. Drug effect magnitude (absolute value for ranking)
        merged['DrugEffect_Magnitude'] = merged['DrugEffect_LR_Abs'].abs()

        # 8. Effect significance threshold (>20% change considered significant)
        merged['Is_Significant_Effect'] = merged['DrugEffect_Magnitude'] > (merged['CTRL_LR_Abs'].abs() * 0.2)

        self.drug_effect = merged

        print(f"  ✓ Calculated drug effects for {len(merged)} electrode-metric pairs")
        print(f"  ✓ Enhanced: {(merged['DrugEffect_Direction'] == 'Enhanced').sum()}")
        print(f"  ✓ Suppressed: {(merged['DrugEffect_Direction'] == 'Suppressed').sum()}")
        print(f"  ✓ No Change: {(merged['DrugEffect_Direction'] == 'No Change').sum()}")

        return merged


# =============================================================================
# STATISTICAL ANALYZER
# =============================================================================

class DrugEffectStatistics:
    """
    Drug Effect 통계 분석

    검정 방법:
    - Paired t-test: CONTROL vs DRUG (동일 electrode)
    - Wilcoxon signed-rank test: 비모수 대안
    - Effect size: Cohen's d
    """

    def __init__(self, drug_effect_df: pd.DataFrame):
        self.drug_effect = drug_effect_df
        self.stats_results = None

    @timer
    def run_tests(self) -> pd.DataFrame:
        """통계 검정 실행"""
        print("\n[STATISTICS] Running statistical tests...")

        if self.drug_effect.empty:
            print("  ⚠ No data for statistical analysis")
            return pd.DataFrame()

        results = []

        # Group by metric (and optionally LIGHT_CODE)
        group_cols = ['Metric']
        if 'LIGHT_CODE' in self.drug_effect.columns:
            group_cols.append('LIGHT_CODE')

        for group_vals, group_df in self.drug_effect.groupby(group_cols):
            if isinstance(group_vals, str):
                group_vals = (group_vals,)

            result = {col: val for col, val in zip(group_cols, group_vals)}
            result['N'] = len(group_df)

            # Light Response comparison (CTRL vs DRUG)
            ctrl_lr = group_df['CTRL_LR_Abs'].values
            drug_lr = group_df['DRUG_LR_Abs'].values

            if len(ctrl_lr) >= 3 and len(drug_lr) >= 3:
                # Paired t-test
                try:
                    t_stat, p_ttest = stats.ttest_rel(ctrl_lr, drug_lr)
                    result['t_statistic'] = t_stat
                    result['p_value_ttest'] = p_ttest
                except:
                    result['t_statistic'] = np.nan
                    result['p_value_ttest'] = np.nan

                # Wilcoxon signed-rank test
                try:
                    w_stat, p_wilcox = stats.wilcoxon(ctrl_lr, drug_lr)
                    result['w_statistic'] = w_stat
                    result['p_value_wilcoxon'] = p_wilcox
                except:
                    result['w_statistic'] = np.nan
                    result['p_value_wilcoxon'] = np.nan

                # Effect size (Cohen's d for paired samples)
                diff = drug_lr - ctrl_lr
                result['mean_diff'] = np.mean(diff)
                result['std_diff'] = np.std(diff, ddof=1)

                if result['std_diff'] > 0:
                    result['cohens_d'] = result['mean_diff'] / result['std_diff']
                else:
                    result['cohens_d'] = np.nan

                # Descriptive stats
                result['CTRL_LR_mean'] = np.mean(ctrl_lr)
                result['CTRL_LR_std'] = np.std(ctrl_lr, ddof=1)
                result['DRUG_LR_mean'] = np.mean(drug_lr)
                result['DRUG_LR_std'] = np.std(drug_lr, ddof=1)

                # Direction summary
                result['n_enhanced'] = (diff > 0).sum()
                result['n_suppressed'] = (diff < 0).sum()
                result['pct_enhanced'] = (diff > 0).mean() * 100

            else:
                result['t_statistic'] = np.nan
                result['p_value_ttest'] = np.nan
                result['note'] = 'Insufficient data (N<3)'

            results.append(result)

        self.stats_results = pd.DataFrame(results)

        # Add significance markers
        if 'p_value_ttest' in self.stats_results.columns:
            self.stats_results['significance'] = self.stats_results['p_value_ttest'].apply(
                lambda p: '***' if p < 0.001 else ('**' if p < 0.01 else ('*' if p < 0.05 else 'ns'))
            )

        print(f"  ✓ Completed {len(results)} statistical tests")

        return self.stats_results


# =============================================================================
# VISUALIZER
# =============================================================================

class DrugEffectVisualizer:
    """Drug Effect 시각화"""

    def __init__(self, control_lr: pd.DataFrame, drug_lr: pd.DataFrame,
                 drug_effect: pd.DataFrame, stats_results: pd.DataFrame,
                 output_dir: Path):
        self.control_lr = control_lr
        self.drug_lr = drug_lr
        self.drug_effect = drug_effect
        self.stats_results = stats_results
        self.output_dir = Path(output_dir) / 'visualizations'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @timer
    def create_all(self):
        """모든 시각화 생성"""
        print("\n[VIZ] Creating visualizations...")

        funcs = [
            self.plot_lr_comparison_overview,
            self.plot_paired_lr_by_electrode,
            self.plot_drug_effect_distribution,
            self.plot_drug_effect_by_light_code,
            self.plot_baseline_change,
            self.plot_effect_direction_summary,
            self.plot_statistical_summary,
            self.plot_heatmap_comparison,
        ]

        for func in funcs:
            try:
                func()
            except Exception as e:
                print(f"  ⚠ {func.__name__}: {e}")

        # Per-color 개별 시각화
        self._create_per_color_plots()

        print("  ✓ All visualizations complete")

    def _create_per_color_plots(self):
        """LIGHT_CODE별 개별 시각화"""
        if self.drug_effect.empty or 'LIGHT_CODE' not in self.drug_effect.columns:
            return

        per_color_dir = self.output_dir / 'per_color'
        per_color_dir.mkdir(parents=True, exist_ok=True)

        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
        available = [m for m in key_metrics if m in self.drug_effect['Metric'].unique()]
        if not available:
            available = list(self.drug_effect['Metric'].unique()[:3])

        for lc in self.drug_effect['LIGHT_CODE'].unique():
            lc_data = self.drug_effect[self.drug_effect['LIGHT_CODE'] == lc]

            if lc_data.empty:
                continue

            # Per-color comparison plot
            n_metrics = len(available)
            fig, axes = plt.subplots(1, n_metrics, figsize=(5*n_metrics, 5))
            if n_metrics == 1:
                axes = [axes]

            for idx, metric in enumerate(available):
                ax = axes[idx]
                metric_df = lc_data[lc_data['Metric'] == metric]

                if metric_df.empty:
                    ax.text(0.5, 0.5, 'No data', ha='center', va='center')
                    continue

                # Box plot: CTRL vs DRUG
                ctrl_lr = metric_df['CTRL_LR_Abs'].values
                drug_lr = metric_df['DRUG_LR_Abs'].values

                bp = ax.boxplot([ctrl_lr, drug_lr], labels=['CONTROL', 'DRUG'],
                               patch_artist=True, showmeans=True)
                bp['boxes'][0].set_facecolor('#5DADE2')
                bp['boxes'][1].set_facecolor('#EC7063')

                ax.set_ylabel('Light Response', fontweight='bold')
                ax.set_title(f'{metric.replace("_", " ").title()}', fontweight='bold')
                ax.grid(axis='y', alpha=0.3)

            plt.suptitle(f'Drug Effect on Light Response - {lc}',
                        fontweight='bold', fontsize=14)
            plt.tight_layout()
            plt.savefig(per_color_dir / f'drug_effect_{lc}.png', dpi=300, bbox_inches='tight')
            plt.close(fig)

        print(f"  ✓ Per-color plots: {per_color_dir}")

    def plot_lr_comparison_overview(self):
        """Light Response 비교 개요 (CONTROL vs DRUG)"""
        if self.drug_effect.empty:
            return

        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
        available = [m for m in key_metrics if m in self.drug_effect['Metric'].unique()]

        if not available:
            available = self.drug_effect['Metric'].unique()[:3]

        n_metrics = len(available)
        fig, axes = plt.subplots(2, n_metrics, figsize=(6*n_metrics, 12))

        for idx, metric in enumerate(available):
            metric_df = self.drug_effect[self.drug_effect['Metric'] == metric]

            # Row 1: BASE and STIM comparison
            ax1 = axes[0, idx] if n_metrics > 1 else axes[0]

            # Grouped bar chart: BASE (CTRL, DRUG), STIM (CTRL, DRUG)
            x = np.arange(2)
            width = 0.35

            ctrl_vals = [metric_df['CTRL_BASE'].mean(), metric_df['CTRL_STIM'].mean()]
            drug_vals = [metric_df['DRUG_BASE'].mean(), metric_df['DRUG_STIM'].mean()]
            ctrl_errs = [metric_df['CTRL_BASE'].std(), metric_df['CTRL_STIM'].std()]
            drug_errs = [metric_df['DRUG_BASE'].std(), metric_df['DRUG_STIM'].std()]

            ax1.bar(x - width/2, ctrl_vals, width, yerr=ctrl_errs, capsize=5,
                   label='CONTROL', color=COLORS['control'], edgecolor='black', alpha=0.8)
            ax1.bar(x + width/2, drug_vals, width, yerr=drug_errs, capsize=5,
                   label='DRUG', color=COLORS['drug'], edgecolor='black', alpha=0.8)

            ax1.set_xticks(x)
            ax1.set_xticklabels(['BASE', 'STIM'], fontweight='bold')
            ax1.set_ylabel('Mean Value', fontweight='bold')
            ax1.set_title(f'{metric.replace("_", " ").title()}', fontweight='bold', fontsize=12)
            ax1.legend()
            ax1.grid(axis='y', alpha=0.3)

            # Row 2: Light Response comparison
            ax2 = axes[1, idx] if n_metrics > 1 else axes[1]

            ctrl_lr = metric_df['CTRL_LR_Abs'].values
            drug_lr = metric_df['DRUG_LR_Abs'].values

            # Box plot
            bp = ax2.boxplot([ctrl_lr, drug_lr], labels=['CONTROL', 'DRUG'],
                            patch_artist=True, showmeans=True,
                            meanprops=dict(marker='D', markerfacecolor='white', markeredgecolor='black'))

            bp['boxes'][0].set_facecolor(COLORS['control'])
            bp['boxes'][1].set_facecolor(COLORS['drug'])

            for box in bp['boxes']:
                box.set_alpha(0.7)

            ax2.set_ylabel('Light Response\n(STIM - BASE)', fontweight='bold')
            ax2.set_title(f'Light Response Comparison', fontweight='bold')
            ax2.grid(axis='y', alpha=0.3)

            # Add p-value if available
            if self.stats_results is not None and not self.stats_results.empty:
                stat_row = self.stats_results[self.stats_results['Metric'] == metric]
                if not stat_row.empty and 'p_value_ttest' in stat_row.columns:
                    p_val = stat_row['p_value_ttest'].values[0]
                    sig = stat_row['significance'].values[0] if 'significance' in stat_row.columns else ''
                    ax2.text(0.5, 0.95, f'p={p_val:.4f} {sig}',
                            transform=ax2.transAxes, ha='center', va='top',
                            fontsize=10, fontweight='bold',
                            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.suptitle('CONTROL vs DRUG: Light Response Comparison',
                    fontweight='bold', fontsize=14, y=0.98)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'lr_comparison_overview.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_paired_lr_by_electrode(self):
        """Electrode별 paired Light Response 비교"""
        if self.drug_effect.empty:
            return

        # 주요 metric 선택
        metric = 'number_of_spikes'
        if metric not in self.drug_effect['Metric'].unique():
            metric = self.drug_effect['Metric'].iloc[0]

        metric_df = self.drug_effect[self.drug_effect['Metric'] == metric].copy()
        metric_df = metric_df.sort_values('CTRL_LR_Abs', ascending=False)

        # 상위 20개 electrode
        top_n = min(20, len(metric_df))
        metric_df = metric_df.head(top_n)

        fig, ax = plt.subplots(figsize=(14, 8))

        x = np.arange(len(metric_df))
        width = 0.35

        ax.bar(x - width/2, metric_df['CTRL_LR_Abs'], width,
              label='CONTROL', color=COLORS['control'], edgecolor='black', alpha=0.8)
        ax.bar(x + width/2, metric_df['DRUG_LR_Abs'], width,
              label='DRUG', color=COLORS['drug'], edgecolor='black', alpha=0.8)

        ax.set_xticks(x)
        ax.set_xticklabels(metric_df['Electrode_ID'], rotation=90, ha='center', fontsize=9)
        ax.set_xlabel('Electrode ID', fontweight='bold')
        ax.set_ylabel('Light Response (STIM - BASE)', fontweight='bold')
        ax.set_title(f'Paired Light Response by Electrode\n{metric.replace("_", " ").title()} (Top {top_n})',
                    fontweight='bold', fontsize=12)
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'paired_lr_by_electrode.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_drug_effect_distribution(self):
        """Drug Effect 분포 (히스토그램)"""
        if self.drug_effect.empty:
            return

        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
        available = [m for m in key_metrics if m in self.drug_effect['Metric'].unique()]

        if not available:
            available = self.drug_effect['Metric'].unique()[:3]

        n_metrics = len(available)
        fig, axes = plt.subplots(1, n_metrics, figsize=(6*n_metrics, 5))
        if n_metrics == 1:
            axes = [axes]

        for idx, metric in enumerate(available):
            ax = axes[idx]
            metric_df = self.drug_effect[self.drug_effect['Metric'] == metric]

            values = metric_df['DrugEffect_LR_Abs'].dropna()

            # Histogram
            n, bins, patches = ax.hist(values, bins=20, edgecolor='black', alpha=0.7)

            # Color by sign
            for patch, left, right in zip(patches, bins[:-1], bins[1:]):
                if right <= 0:
                    patch.set_facecolor(COLORS['negative'])
                elif left >= 0:
                    patch.set_facecolor(COLORS['positive'])
                else:
                    patch.set_facecolor(COLORS['neutral'])

            # Mean line
            mean_val = values.mean()
            ax.axvline(mean_val, color='red', linestyle='--', linewidth=2,
                      label=f'Mean: {mean_val:.2f}')
            ax.axvline(0, color='black', linestyle='-', linewidth=1)

            ax.set_xlabel('Drug Effect\n(DRUG_LR - CTRL_LR)', fontweight='bold')
            ax.set_ylabel('Frequency', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}', fontweight='bold')
            ax.legend()
            ax.grid(alpha=0.3)

        plt.suptitle('Drug Effect Distribution\n(Positive = Enhanced, Negative = Suppressed)',
                    fontweight='bold', fontsize=12)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'drug_effect_distribution.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_drug_effect_by_light_code(self):
        """Light Code별 Drug Effect"""
        if self.drug_effect.empty or 'LIGHT_CODE' not in self.drug_effect.columns:
            return

        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz']
        available = [m for m in key_metrics if m in self.drug_effect['Metric'].unique()]

        if not available:
            available = [self.drug_effect['Metric'].iloc[0]]

        n_metrics = len(available)
        fig, axes = plt.subplots(2, n_metrics, figsize=(7*n_metrics, 12))

        for idx, metric in enumerate(available):
            metric_df = self.drug_effect[self.drug_effect['Metric'] == metric]
            light_codes = sorted(metric_df['LIGHT_CODE'].unique())

            # Row 1: CTRL vs DRUG Light Response by Light Code
            ax1 = axes[0, idx] if n_metrics > 1 else axes[0]

            x = np.arange(len(light_codes))
            width = 0.35

            ctrl_means = [metric_df[metric_df['LIGHT_CODE'] == lc]['CTRL_LR_Abs'].mean()
                         for lc in light_codes]
            drug_means = [metric_df[metric_df['LIGHT_CODE'] == lc]['DRUG_LR_Abs'].mean()
                         for lc in light_codes]
            ctrl_stds = [metric_df[metric_df['LIGHT_CODE'] == lc]['CTRL_LR_Abs'].std()
                        for lc in light_codes]
            drug_stds = [metric_df[metric_df['LIGHT_CODE'] == lc]['DRUG_LR_Abs'].std()
                        for lc in light_codes]

            ax1.bar(x - width/2, ctrl_means, width, yerr=ctrl_stds, capsize=5,
                   label='CONTROL', color=COLORS['control'], edgecolor='black', alpha=0.8)
            ax1.bar(x + width/2, drug_means, width, yerr=drug_stds, capsize=5,
                   label='DRUG', color=COLORS['drug'], edgecolor='black', alpha=0.8)

            ax1.set_xticks(x)
            ax1.set_xticklabels(light_codes, fontweight='bold')
            ax1.set_xlabel('Light Code', fontweight='bold')
            ax1.set_ylabel('Light Response', fontweight='bold')
            ax1.set_title(f'{metric.replace("_", " ").title()}\nCTRL vs DRUG by Light Code',
                         fontweight='bold')
            ax1.legend()
            ax1.grid(axis='y', alpha=0.3)
            ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

            # Row 2: Drug Effect by Light Code
            ax2 = axes[1, idx] if n_metrics > 1 else axes[1]

            effect_means = [metric_df[metric_df['LIGHT_CODE'] == lc]['DrugEffect_LR_Abs'].mean()
                           for lc in light_codes]
            effect_stds = [metric_df[metric_df['LIGHT_CODE'] == lc]['DrugEffect_LR_Abs'].std()
                          for lc in light_codes]

            colors = [COLORS.get(lc, COLORS['neutral']) for lc in light_codes]

            bars = ax2.bar(x, effect_means, yerr=effect_stds, capsize=5,
                          color=colors, edgecolor='black', alpha=0.8)

            ax2.set_xticks(x)
            ax2.set_xticklabels(light_codes, fontweight='bold')
            ax2.set_xlabel('Light Code', fontweight='bold')
            ax2.set_ylabel('Drug Effect\n(DRUG_LR - CTRL_LR)', fontweight='bold')
            ax2.set_title(f'Drug Effect by Light Code', fontweight='bold')
            ax2.grid(axis='y', alpha=0.3)
            ax2.axhline(y=0, color='black', linestyle='-', linewidth=1)

            # Add value labels
            for i, (mean, std) in enumerate(zip(effect_means, effect_stds)):
                ax2.text(i, mean + std + 0.5, f'{mean:.1f}', ha='center', fontsize=9, fontweight='bold')

        plt.suptitle('Drug Effect Analysis by Light Code', fontweight='bold', fontsize=14, y=0.98)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'drug_effect_by_light_code.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_baseline_change(self):
        """Baseline (spontaneous activity) 변화"""
        if self.drug_effect.empty:
            return

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Plot 1: Baseline change by metric
        ax1 = axes[0]

        metrics = self.drug_effect['Metric'].unique()
        baseline_changes = [self.drug_effect[self.drug_effect['Metric'] == m]['Baseline_Change'].mean()
                           for m in metrics]
        baseline_stds = [self.drug_effect[self.drug_effect['Metric'] == m]['Baseline_Change'].std()
                        for m in metrics]

        colors = [COLORS['positive'] if v > 0 else COLORS['negative'] for v in baseline_changes]

        ax1.bar(range(len(metrics)), baseline_changes, yerr=baseline_stds, capsize=5,
               color=colors, edgecolor='black', alpha=0.8)
        ax1.set_xticks(range(len(metrics)))
        ax1.set_xticklabels([m.replace('_', '\n') for m in metrics], fontsize=9)
        ax1.set_xlabel('Metric', fontweight='bold')
        ax1.set_ylabel('Baseline Change\n(DRUG_BASE - CTRL_BASE)', fontweight='bold')
        ax1.set_title('Drug Effect on Baseline Activity', fontweight='bold')
        ax1.grid(axis='y', alpha=0.3)
        ax1.axhline(y=0, color='black', linestyle='-', linewidth=1)

        # Plot 2: Baseline vs Light Response change scatter
        ax2 = axes[1]

        metric = 'number_of_spikes'
        if metric not in self.drug_effect['Metric'].unique():
            metric = self.drug_effect['Metric'].iloc[0]

        metric_df = self.drug_effect[self.drug_effect['Metric'] == metric]

        ax2.scatter(metric_df['Baseline_Change'], metric_df['DrugEffect_LR_Abs'],
                   alpha=0.6, s=60, edgecolor='black', c=COLORS['drug'])

        # Add regression line
        if len(metric_df) > 2:
            z = np.polyfit(metric_df['Baseline_Change'], metric_df['DrugEffect_LR_Abs'], 1)
            p = np.poly1d(z)
            x_line = np.linspace(metric_df['Baseline_Change'].min(), metric_df['Baseline_Change'].max(), 100)
            ax2.plot(x_line, p(x_line), 'r--', linewidth=2, label=f'Trend (slope={z[0]:.2f})')

            # Correlation
            corr, p_val = stats.pearsonr(metric_df['Baseline_Change'], metric_df['DrugEffect_LR_Abs'])
            ax2.text(0.05, 0.95, f'r = {corr:.3f}\np = {p_val:.4f}',
                    transform=ax2.transAxes, fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
        ax2.set_xlabel('Baseline Change', fontweight='bold')
        ax2.set_ylabel('Drug Effect on Light Response', fontweight='bold')
        ax2.set_title(f'Baseline vs Light Response Change\n({metric})', fontweight='bold')
        ax2.legend()
        ax2.grid(alpha=0.3)

        plt.suptitle('Drug Effect on Spontaneous Activity', fontweight='bold', fontsize=14, y=0.98)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'baseline_change.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_effect_direction_summary(self):
        """Drug Effect 방향 요약 (Enhanced/Suppressed)"""
        if self.drug_effect.empty:
            return

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Plot 1: Pie chart by metric
        ax1 = axes[0]

        direction_counts = self.drug_effect['DrugEffect_Direction'].value_counts()
        colors = [COLORS['positive'] if d == 'Enhanced' else
                 (COLORS['negative'] if d == 'Suppressed' else COLORS['neutral'])
                 for d in direction_counts.index]

        wedges, texts, autotexts = ax1.pie(direction_counts.values, labels=direction_counts.index,
                                           autopct='%1.1f%%', colors=colors, startangle=90,
                                           explode=[0.05]*len(direction_counts))

        for autotext in autotexts:
            autotext.set_fontweight('bold')

        ax1.set_title('Overall Drug Effect Direction', fontweight='bold', fontsize=12)

        # Plot 2: Stacked bar by metric
        ax2 = axes[1]

        metrics = self.drug_effect['Metric'].unique()
        enhanced = []
        suppressed = []
        no_change = []

        for metric in metrics:
            metric_df = self.drug_effect[self.drug_effect['Metric'] == metric]
            total = len(metric_df)
            enhanced.append((metric_df['DrugEffect_Direction'] == 'Enhanced').sum() / total * 100)
            suppressed.append((metric_df['DrugEffect_Direction'] == 'Suppressed').sum() / total * 100)
            no_change.append((metric_df['DrugEffect_Direction'] == 'No Change').sum() / total * 100)

        x = np.arange(len(metrics))
        width = 0.6

        ax2.bar(x, enhanced, width, label='Enhanced', color=COLORS['positive'], edgecolor='black')
        ax2.bar(x, suppressed, width, bottom=enhanced, label='Suppressed', color=COLORS['negative'], edgecolor='black')
        ax2.bar(x, no_change, width, bottom=[e+s for e, s in zip(enhanced, suppressed)],
               label='No Change', color=COLORS['neutral'], edgecolor='black')

        ax2.set_xticks(x)
        ax2.set_xticklabels([m.replace('_', '\n') for m in metrics], fontsize=9)
        ax2.set_xlabel('Metric', fontweight='bold')
        ax2.set_ylabel('Percentage (%)', fontweight='bold')
        ax2.set_title('Drug Effect Direction by Metric', fontweight='bold')
        ax2.legend(loc='upper right')
        ax2.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'effect_direction_summary.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_statistical_summary(self):
        """통계 결과 요약"""
        if self.stats_results is None or self.stats_results.empty:
            return

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Plot 1: P-values by metric
        ax1 = axes[0]

        if 'p_value_ttest' in self.stats_results.columns:
            metrics = self.stats_results['Metric'].values
            p_values = self.stats_results['p_value_ttest'].values

            # -log10 transform for visualization
            neg_log_p = -np.log10(p_values + 1e-10)

            colors = ['green' if p < 0.05 else 'gray' for p in p_values]

            ax1.barh(range(len(metrics)), neg_log_p, color=colors, edgecolor='black', alpha=0.7)
            ax1.axvline(x=-np.log10(0.05), color='red', linestyle='--', linewidth=2, label='p=0.05')
            ax1.axvline(x=-np.log10(0.01), color='orange', linestyle='--', linewidth=2, label='p=0.01')

            ax1.set_yticks(range(len(metrics)))
            ax1.set_yticklabels([m.replace('_', ' ').title() for m in metrics], fontsize=10)
            ax1.set_xlabel('-log10(p-value)', fontweight='bold')
            ax1.set_title('Statistical Significance\n(Paired t-test: CTRL vs DRUG)', fontweight='bold')
            ax1.legend()
            ax1.grid(axis='x', alpha=0.3)

        # Plot 2: Effect sizes
        ax2 = axes[1]

        if 'cohens_d' in self.stats_results.columns:
            metrics = self.stats_results['Metric'].values
            effect_sizes = self.stats_results['cohens_d'].values

            colors = [COLORS['positive'] if d > 0 else COLORS['negative'] for d in effect_sizes]

            ax2.barh(range(len(metrics)), effect_sizes, color=colors, edgecolor='black', alpha=0.7)
            ax2.axvline(x=0, color='black', linestyle='-', linewidth=1)
            ax2.axvline(x=0.2, color='gray', linestyle=':', linewidth=1, label='Small (0.2)')
            ax2.axvline(x=0.5, color='gray', linestyle='--', linewidth=1, label='Medium (0.5)')
            ax2.axvline(x=0.8, color='gray', linestyle='-', linewidth=1, label='Large (0.8)')
            ax2.axvline(x=-0.2, color='gray', linestyle=':', linewidth=1)
            ax2.axvline(x=-0.5, color='gray', linestyle='--', linewidth=1)
            ax2.axvline(x=-0.8, color='gray', linestyle='-', linewidth=1)

            ax2.set_yticks(range(len(metrics)))
            ax2.set_yticklabels([m.replace('_', ' ').title() for m in metrics], fontsize=10)
            ax2.set_xlabel("Cohen's d (Effect Size)", fontweight='bold')
            ax2.set_title('Effect Size\n(Positive = DRUG > CTRL)', fontweight='bold')
            ax2.legend(loc='lower right', fontsize=8)
            ax2.grid(axis='x', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'statistical_summary.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    def plot_heatmap_comparison(self):
        """Heatmap 비교 (CTRL vs DRUG)"""
        if self.drug_effect.empty:
            return

        fig, axes = plt.subplots(1, 3, figsize=(18, 8))

        # Pivot data for heatmaps
        # Using Electrode_ID as index, Metric as columns

        # Heatmap 1: CTRL Light Response
        ax1 = axes[0]
        pivot_ctrl = self.drug_effect.pivot_table(
            index='Electrode_ID', columns='Metric', values='CTRL_LR_Abs', aggfunc='mean')

        if not pivot_ctrl.empty:
            # Z-score normalization
            pivot_ctrl_norm = (pivot_ctrl - pivot_ctrl.mean()) / pivot_ctrl.std()
            sns.heatmap(pivot_ctrl_norm, cmap='RdYlGn', center=0, ax=ax1,
                       cbar_kws={'label': 'Z-score'}, annot=False)
            ax1.set_title('CONTROL Light Response\n(Z-score)', fontweight='bold')
            ax1.set_xlabel('Metric', fontweight='bold')
            ax1.set_ylabel('Electrode', fontweight='bold')
            plt.setp(ax1.get_xticklabels(), rotation=45, ha='right', fontsize=8)
            plt.setp(ax1.get_yticklabels(), fontsize=7)

        # Heatmap 2: DRUG Light Response
        ax2 = axes[1]
        pivot_drug = self.drug_effect.pivot_table(
            index='Electrode_ID', columns='Metric', values='DRUG_LR_Abs', aggfunc='mean')

        if not pivot_drug.empty:
            pivot_drug_norm = (pivot_drug - pivot_drug.mean()) / pivot_drug.std()
            sns.heatmap(pivot_drug_norm, cmap='RdYlGn', center=0, ax=ax2,
                       cbar_kws={'label': 'Z-score'}, annot=False)
            ax2.set_title('DRUG Light Response\n(Z-score)', fontweight='bold')
            ax2.set_xlabel('Metric', fontweight='bold')
            ax2.set_ylabel('Electrode', fontweight='bold')
            plt.setp(ax2.get_xticklabels(), rotation=45, ha='right', fontsize=8)
            plt.setp(ax2.get_yticklabels(), fontsize=7)

        # Heatmap 3: Drug Effect
        ax3 = axes[2]
        pivot_effect = self.drug_effect.pivot_table(
            index='Electrode_ID', columns='Metric', values='DrugEffect_LR_Abs', aggfunc='mean')

        if not pivot_effect.empty:
            sns.heatmap(pivot_effect, cmap='RdBu_r', center=0, ax=ax3,
                       cbar_kws={'label': 'Drug Effect'}, annot=False)
            ax3.set_title('Drug Effect\n(DRUG_LR - CTRL_LR)', fontweight='bold')
            ax3.set_xlabel('Metric', fontweight='bold')
            ax3.set_ylabel('Electrode', fontweight='bold')
            plt.setp(ax3.get_xticklabels(), rotation=45, ha='right', fontsize=8)
            plt.setp(ax3.get_yticklabels(), fontsize=7)

        plt.suptitle('Light Response Heatmap Comparison', fontweight='bold', fontsize=14, y=0.98)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'heatmap_comparison.png', dpi=300, bbox_inches='tight')
        plt.close(fig)


# =============================================================================
# EXCEL EXPORTER
# =============================================================================

class DrugEffectExcelExporter:
    """Drug Effect 분석 결과 Excel 출력"""

    def __init__(self, control_lr: pd.DataFrame, drug_lr: pd.DataFrame,
                 drug_effect: pd.DataFrame, stats_results: pd.DataFrame,
                 selected_electrodes: List[str], output_path: Path):
        self.control_lr = control_lr
        self.drug_lr = drug_lr
        self.drug_effect = drug_effect
        self.stats_results = stats_results
        self.selected_electrodes = selected_electrodes
        self.output_path = Path(output_path)

    @timer
    def create(self):
        """Excel 파일 생성"""
        print("\n[EXCEL] Creating drug effect Excel report...")

        with pd.ExcelWriter(self.output_path, engine='openpyxl') as writer:

            # Sheet 1: Summary
            summary_data = self._create_summary()
            summary_data.to_excel(writer, sheet_name='Summary', index=False)

            # Sheet 2: Drug Effect (main results)
            if not self.drug_effect.empty:
                self.drug_effect.to_excel(writer, sheet_name='Drug_Effect', index=False)

            # Sheet 3: Statistical Results
            if self.stats_results is not None and not self.stats_results.empty:
                self.stats_results.to_excel(writer, sheet_name='Statistics', index=False)

            # Sheet 4: CONTROL Light Response
            if not self.control_lr.empty:
                self.control_lr.to_excel(writer, sheet_name='CTRL_LightResponse', index=False)

            # Sheet 5: DRUG Light Response
            if not self.drug_lr.empty:
                self.drug_lr.to_excel(writer, sheet_name='DRUG_LightResponse', index=False)

            # Sheet 6: Selected Electrodes
            electrode_df = pd.DataFrame({
                'Electrode_ID': self.selected_electrodes,
                'Order': range(1, len(self.selected_electrodes) + 1)
            })
            electrode_df.to_excel(writer, sheet_name='Selected_Electrodes', index=False)

            # Sheet 7: Pivot by Metric (Drug Effect)
            if not self.drug_effect.empty:
                pivot = self.drug_effect.pivot_table(
                    index='Electrode_ID', columns='Metric',
                    values='DrugEffect_LR_Abs', aggfunc='mean')
                pivot.to_excel(writer, sheet_name='Pivot_DrugEffect')

            # Sheet 8: Effect Direction Summary
            if not self.drug_effect.empty:
                direction_summary = self._create_direction_summary()
                direction_summary.to_excel(writer, sheet_name='Direction_Summary', index=False)

            # Sheet 9: Per Well Summary (개선: Well별 요약 추가)
            if not self.drug_effect.empty:
                per_well_summary = self._create_per_well_summary()
                per_well_summary.to_excel(writer, sheet_name='Per_Well_Summary', index=False)

            # Sheet 10: Per Color Summary (LIGHT_CODE별 요약)
            if not self.drug_effect.empty and 'LIGHT_CODE' in self.drug_effect.columns:
                per_color_summary = self._create_per_color_summary()
                per_color_summary.to_excel(writer, sheet_name='Per_Color_Summary', index=False)

        # 개선: Per-well, Per-color CSV 파일 출력
        self._save_per_well_csv()
        self._save_per_color_csv()

        print(f"  ✓ Saved: {self.output_path.name}")

    def _save_per_well_csv(self):
        """Per-well CSV 파일 저장"""
        if self.drug_effect.empty:
            return

        per_well_dir = self.output_path.parent / 'per_well'
        per_well_dir.mkdir(parents=True, exist_ok=True)

        for well in self.drug_effect['Well'].unique():
            well_data = self.drug_effect[self.drug_effect['Well'] == well]
            well_data.to_csv(per_well_dir / f'drug_effect_{well}.csv', index=False)

        print(f"  ✓ Per-well CSV: {per_well_dir}")

    def _save_per_color_csv(self):
        """Per-color (LIGHT_CODE별) CSV 파일 저장"""
        if self.drug_effect.empty:
            return

        if 'LIGHT_CODE' not in self.drug_effect.columns:
            return

        per_color_dir = self.output_path.parent / 'per_color'
        per_color_dir.mkdir(parents=True, exist_ok=True)

        for lc in self.drug_effect['LIGHT_CODE'].unique():
            lc_data = self.drug_effect[self.drug_effect['LIGHT_CODE'] == lc]
            lc_data.to_csv(per_color_dir / f'drug_effect_{lc}.csv', index=False)

            # Per-color summary
            summary = lc_data.groupby('Metric').agg({
                'DrugEffect_LR_Abs': ['mean', 'std', 'count'],
                'CTRL_LR_Abs': 'mean',
                'DRUG_LR_Abs': 'mean',
                'DrugEffect_Direction': lambda x: (x == 'Enhanced').sum()
            }).reset_index()
            summary.columns = ['Metric', 'DrugEffect_Mean', 'DrugEffect_Std', 'N',
                              'CTRL_LR_Mean', 'DRUG_LR_Mean', 'N_Enhanced']
            summary.to_csv(per_color_dir / f'drug_effect_summary_{lc}.csv', index=False)

        print(f"  ✓ Per-color CSV: {per_color_dir}")

    def _create_per_well_summary(self) -> pd.DataFrame:
        """Well별 요약 테이블"""
        results = []

        for well in self.drug_effect['Well'].unique():
            well_df = self.drug_effect[self.drug_effect['Well'] == well]

            result = {
                'Well': well,
                'N_Electrodes': well_df['Electrode_ID'].nunique(),
                'N_Enhanced': (well_df['DrugEffect_Direction'] == 'Enhanced').sum(),
                'N_Suppressed': (well_df['DrugEffect_Direction'] == 'Suppressed').sum(),
                'Pct_Enhanced': (well_df['DrugEffect_Direction'] == 'Enhanced').mean() * 100,
                'Mean_DrugEffect': well_df['DrugEffect_LR_Abs'].mean(),
                'Mean_Baseline_Change': well_df['Baseline_Change'].mean(),
                'Mean_CTRL_LR': well_df['CTRL_LR_Abs'].mean(),
                'Mean_DRUG_LR': well_df['DRUG_LR_Abs'].mean(),
            }
            results.append(result)

        return pd.DataFrame(results).sort_values('Well')

    def _create_per_color_summary(self) -> pd.DataFrame:
        """LIGHT_CODE별 요약 테이블"""
        results = []

        for lc in self.drug_effect['LIGHT_CODE'].unique():
            lc_df = self.drug_effect[self.drug_effect['LIGHT_CODE'] == lc]

            for metric in lc_df['Metric'].unique():
                metric_df = lc_df[lc_df['Metric'] == metric]

                result = {
                    'LIGHT_CODE': lc,
                    'Metric': metric,
                    'N_Electrodes': metric_df['Electrode_ID'].nunique(),
                    'CTRL_LR_Mean': metric_df['CTRL_LR_Abs'].mean(),
                    'CTRL_LR_Std': metric_df['CTRL_LR_Abs'].std(),
                    'DRUG_LR_Mean': metric_df['DRUG_LR_Abs'].mean(),
                    'DRUG_LR_Std': metric_df['DRUG_LR_Abs'].std(),
                    'DrugEffect_Mean': metric_df['DrugEffect_LR_Abs'].mean(),
                    'DrugEffect_Std': metric_df['DrugEffect_LR_Abs'].std(),
                    'N_Enhanced': (metric_df['DrugEffect_Direction'] == 'Enhanced').sum(),
                    'N_Suppressed': (metric_df['DrugEffect_Direction'] == 'Suppressed').sum(),
                    'Pct_Enhanced': (metric_df['DrugEffect_Direction'] == 'Enhanced').mean() * 100,
                }
                results.append(result)

        return pd.DataFrame(results).sort_values(['LIGHT_CODE', 'Metric'])

    def _create_summary(self) -> pd.DataFrame:
        """요약 테이블 생성"""
        summary = []

        summary.append({'Item': 'Analysis Type', 'Value': 'Drug Effect on Light Response'})
        summary.append({'Item': 'Total Electrodes', 'Value': len(self.selected_electrodes)})

        if not self.drug_effect.empty:
            summary.append({'Item': 'Total Data Points', 'Value': len(self.drug_effect)})
            summary.append({'Item': 'Metrics Analyzed', 'Value': self.drug_effect['Metric'].nunique()})

            # Direction counts
            if 'DrugEffect_Direction' in self.drug_effect.columns:
                direction_counts = self.drug_effect['DrugEffect_Direction'].value_counts()
                for direction, count in direction_counts.items():
                    summary.append({'Item': f'N {direction}', 'Value': count})

        if self.stats_results is not None and not self.stats_results.empty:
            sig_count = (self.stats_results['p_value_ttest'] < 0.05).sum()
            summary.append({'Item': 'Significant Results (p<0.05)', 'Value': sig_count})

        return pd.DataFrame(summary)

    def _create_direction_summary(self) -> pd.DataFrame:
        """방향 요약 테이블"""
        results = []

        for metric in self.drug_effect['Metric'].unique():
            metric_df = self.drug_effect[self.drug_effect['Metric'] == metric]

            result = {
                'Metric': metric,
                'N_Total': len(metric_df),
                'N_Enhanced': (metric_df['DrugEffect_Direction'] == 'Enhanced').sum(),
                'N_Suppressed': (metric_df['DrugEffect_Direction'] == 'Suppressed').sum(),
                'N_NoChange': (metric_df['DrugEffect_Direction'] == 'No Change').sum(),
                'Pct_Enhanced': (metric_df['DrugEffect_Direction'] == 'Enhanced').mean() * 100,
                'Mean_DrugEffect': metric_df['DrugEffect_LR_Abs'].mean(),
                'Std_DrugEffect': metric_df['DrugEffect_LR_Abs'].std(),
            }
            results.append(result)

        return pd.DataFrame(results)


# =============================================================================
# DASHBOARD
# =============================================================================

class DrugEffectDashboard:
    """Drug Effect 분석 대시보드"""

    def __init__(self, control_lr: pd.DataFrame, drug_lr: pd.DataFrame,
                 drug_effect: pd.DataFrame, stats_results: pd.DataFrame,
                 selected_electrodes: List[str], output_path: Path):
        self.control_lr = control_lr
        self.drug_lr = drug_lr
        self.drug_effect = drug_effect
        self.stats_results = stats_results
        self.selected_electrodes = selected_electrodes
        self.output_path = Path(output_path)

    @timer
    def create(self):
        """대시보드 생성"""
        print("\n[DASHBOARD] Creating drug effect dashboard...")

        fig = plt.figure(figsize=(20, 16))
        gs = fig.add_gridspec(4, 4, hspace=0.35, wspace=0.3)

        # Row 1: Overview
        ax1 = fig.add_subplot(gs[0, :2])
        self._plot_lr_comparison(ax1)

        ax2 = fig.add_subplot(gs[0, 2:])
        self._plot_direction_pie(ax2)

        # Row 2: By Metric
        ax3 = fig.add_subplot(gs[1, :2])
        self._plot_drug_effect_bars(ax3)

        ax4 = fig.add_subplot(gs[1, 2:])
        self._plot_baseline_change(ax4)

        # Row 3: By Light Code
        ax5 = fig.add_subplot(gs[2, :2])
        self._plot_by_light_code(ax5)

        ax6 = fig.add_subplot(gs[2, 2:])
        self._plot_statistics(ax6)

        # Row 4: Details
        ax7 = fig.add_subplot(gs[3, :2])
        self._plot_electrode_scatter(ax7)

        ax8 = fig.add_subplot(gs[3, 2:])
        self._plot_summary_text(ax8)

        fig.suptitle(f'Drug Effect Analysis Dashboard\n'
                    f'({len(self.selected_electrodes)} High-Score Electrodes)',
                    fontweight='bold', fontsize=16, y=0.98)

        plt.savefig(self.output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)

        print(f"  ✓ Dashboard saved: {self.output_path.name}")

    def _plot_lr_comparison(self, ax):
        """Light Response 비교"""
        if self.drug_effect.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center')
            return

        metric = 'number_of_spikes'
        if metric not in self.drug_effect['Metric'].unique():
            metric = self.drug_effect['Metric'].iloc[0]

        metric_df = self.drug_effect[self.drug_effect['Metric'] == metric]

        ctrl_lr = metric_df['CTRL_LR_Abs'].values
        drug_lr = metric_df['DRUG_LR_Abs'].values

        bp = ax.boxplot([ctrl_lr, drug_lr], labels=['CONTROL', 'DRUG'],
                       patch_artist=True, showmeans=True)

        bp['boxes'][0].set_facecolor(COLORS['control'])
        bp['boxes'][1].set_facecolor(COLORS['drug'])

        ax.set_ylabel('Light Response', fontweight='bold')
        ax.set_title(f'{metric.replace("_", " ").title()}: CTRL vs DRUG', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    def _plot_direction_pie(self, ax):
        """방향 파이 차트"""
        if self.drug_effect.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center')
            return

        direction_counts = self.drug_effect['DrugEffect_Direction'].value_counts()
        colors = [COLORS['positive'] if d == 'Enhanced' else
                 (COLORS['negative'] if d == 'Suppressed' else COLORS['neutral'])
                 for d in direction_counts.index]

        ax.pie(direction_counts.values, labels=direction_counts.index,
              autopct='%1.1f%%', colors=colors, startangle=90)
        ax.set_title('Drug Effect Direction', fontweight='bold')

    def _plot_drug_effect_bars(self, ax):
        """Metric별 Drug Effect"""
        if self.drug_effect.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center')
            return

        metrics = self.drug_effect['Metric'].unique()[:4]
        means = [self.drug_effect[self.drug_effect['Metric'] == m]['DrugEffect_LR_Abs'].mean() for m in metrics]
        stds = [self.drug_effect[self.drug_effect['Metric'] == m]['DrugEffect_LR_Abs'].std() for m in metrics]

        colors = [COLORS['positive'] if m > 0 else COLORS['negative'] for m in means]

        ax.bar(range(len(metrics)), means, yerr=stds, capsize=5,
              color=colors, edgecolor='black', alpha=0.8)
        ax.set_xticks(range(len(metrics)))
        ax.set_xticklabels([m.replace('_', '\n')[:15] for m in metrics], fontsize=9)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
        ax.set_ylabel('Drug Effect', fontweight='bold')
        ax.set_title('Drug Effect by Metric', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    def _plot_baseline_change(self, ax):
        """Baseline 변화"""
        if self.drug_effect.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center')
            return

        metric = 'number_of_spikes'
        if metric not in self.drug_effect['Metric'].unique():
            metric = self.drug_effect['Metric'].iloc[0]

        metric_df = self.drug_effect[self.drug_effect['Metric'] == metric]

        x = [0, 1]
        y = [metric_df['CTRL_BASE'].mean(), metric_df['DRUG_BASE'].mean()]
        yerr = [metric_df['CTRL_BASE'].std(), metric_df['DRUG_BASE'].std()]

        ax.bar(x, y, yerr=yerr, capsize=5, width=0.6,
              color=[COLORS['control'], COLORS['drug']], edgecolor='black', alpha=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(['CTRL BASE', 'DRUG BASE'], fontweight='bold')
        ax.set_ylabel('Baseline Activity', fontweight='bold')
        ax.set_title('Baseline Change (Spontaneous)', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    def _plot_by_light_code(self, ax):
        """Light Code별 분석"""
        if self.drug_effect.empty or 'LIGHT_CODE' not in self.drug_effect.columns:
            ax.text(0.5, 0.5, 'No LIGHT_CODE data', ha='center', va='center')
            return

        metric = 'number_of_spikes'
        if metric not in self.drug_effect['Metric'].unique():
            metric = self.drug_effect['Metric'].iloc[0]

        metric_df = self.drug_effect[self.drug_effect['Metric'] == metric]
        light_codes = sorted(metric_df['LIGHT_CODE'].unique())

        x = np.arange(len(light_codes))
        width = 0.35

        ctrl = [metric_df[metric_df['LIGHT_CODE'] == lc]['CTRL_LR_Abs'].mean() for lc in light_codes]
        drug = [metric_df[metric_df['LIGHT_CODE'] == lc]['DRUG_LR_Abs'].mean() for lc in light_codes]

        ax.bar(x - width/2, ctrl, width, label='CONTROL', color=COLORS['control'], edgecolor='black')
        ax.bar(x + width/2, drug, width, label='DRUG', color=COLORS['drug'], edgecolor='black')

        ax.set_xticks(x)
        ax.set_xticklabels(light_codes, fontweight='bold')
        ax.set_xlabel('Light Code', fontweight='bold')
        ax.set_ylabel('Light Response', fontweight='bold')
        ax.set_title('CTRL vs DRUG by Light Code', fontweight='bold')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

    def _plot_statistics(self, ax):
        """통계 결과"""
        if self.stats_results is None or self.stats_results.empty:
            ax.text(0.5, 0.5, 'No statistics', ha='center', va='center')
            ax.set_title('Statistical Results', fontweight='bold')
            return

        if 'p_value_ttest' in self.stats_results.columns:
            metrics = self.stats_results['Metric'].values[:5]
            p_values = self.stats_results['p_value_ttest'].values[:5]

            neg_log_p = -np.log10(p_values + 1e-10)
            colors = ['green' if p < 0.05 else 'gray' for p in p_values]

            ax.barh(range(len(metrics)), neg_log_p, color=colors, edgecolor='black', alpha=0.7)
            ax.axvline(x=-np.log10(0.05), color='red', linestyle='--', linewidth=2)

            ax.set_yticks(range(len(metrics)))
            ax.set_yticklabels([m[:20] for m in metrics], fontsize=9)
            ax.set_xlabel('-log10(p)', fontweight='bold')
            ax.set_title('Statistical Significance', fontweight='bold')
            ax.grid(axis='x', alpha=0.3)

    def _plot_electrode_scatter(self, ax):
        """Electrode 산점도"""
        if self.drug_effect.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center')
            return

        metric = 'number_of_spikes'
        if metric not in self.drug_effect['Metric'].unique():
            metric = self.drug_effect['Metric'].iloc[0]

        metric_df = self.drug_effect[self.drug_effect['Metric'] == metric]

        ax.scatter(metric_df['CTRL_LR_Abs'], metric_df['DRUG_LR_Abs'],
                  alpha=0.6, s=50, edgecolor='black', c=COLORS['drug'])

        # Identity line
        max_val = max(metric_df['CTRL_LR_Abs'].max(), metric_df['DRUG_LR_Abs'].max())
        min_val = min(metric_df['CTRL_LR_Abs'].min(), metric_df['DRUG_LR_Abs'].min())
        ax.plot([min_val, max_val], [min_val, max_val], 'k--', alpha=0.5, label='y=x')

        ax.set_xlabel('CTRL Light Response', fontweight='bold')
        ax.set_ylabel('DRUG Light Response', fontweight='bold')
        ax.set_title('CTRL vs DRUG (per Electrode)', fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)

    def _plot_summary_text(self, ax):
        """요약 텍스트"""
        ax.axis('off')

        lines = [
            f"Electrodes Analyzed: {len(self.selected_electrodes)}",
            f"Data Points: {len(self.drug_effect)}",
            "",
        ]

        if not self.drug_effect.empty:
            direction_counts = self.drug_effect['DrugEffect_Direction'].value_counts()
            lines.append("Drug Effect Direction:")
            for direction, count in direction_counts.items():
                pct = count / len(self.drug_effect) * 100
                lines.append(f"  {direction}: {count} ({pct:.1f}%)")

            lines.append("")
            lines.append("Mean Drug Effects:")
            for metric in self.drug_effect['Metric'].unique()[:3]:
                mean_eff = self.drug_effect[self.drug_effect['Metric'] == metric]['DrugEffect_LR_Abs'].mean()
                lines.append(f"  {metric[:25]}: {mean_eff:.2f}")

        if self.stats_results is not None and not self.stats_results.empty:
            lines.append("")
            sig_count = (self.stats_results['p_value_ttest'] < 0.05).sum()
            lines.append(f"Significant (p<0.05): {sig_count}/{len(self.stats_results)}")

        ax.text(0.1, 0.95, '\n'.join(lines), transform=ax.transAxes,
               fontsize=11, verticalalignment='top', fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.3))
        ax.set_title('Summary', fontweight='bold')


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class DrugEffectAnalyzer:
    """
    Drug Effect 분석 파이프라인

    CONTROL 상태와 DRUG 투여 후의 Light Response 변화 분석

    Usage:
        analyzer = DrugEffectAnalyzer(
            electrode_data_path=r"D:\\output\\electrode_all_long.parquet",
            scores_path=r"D:\\output\\electrode_scores\\electrode_response_scores.csv",
            output_dir=r"D:\\output\\drug_effect_analysis",
            top_n_per_well=3,
            control_label="CONTROL",
            drug_labels=["DRUG_A"]
        )
        analyzer.run()
    """

    def __init__(self,
                 electrode_data_path: str,
                 scores_path: str,
                 output_dir: str,
                 top_n_per_well: int = 3,
                 top_n_overall: Optional[int] = None,
                 control_label: str = "CONTROL",
                 drug_labels: Optional[List[str]] = None,
                 condition_column: str = "EXP_TYPE",
                 metrics: Optional[List[str]] = None):
        """
        Parameters:
        -----------
        electrode_data_path : str
            전체 electrode 데이터 경로 (CONTROL + DRUG 포함)
        scores_path : str
            electrode score 파일 경로 (CONTROL 기준으로 산출됨)
        output_dir : str
            출력 디렉토리
        top_n_per_well : int
            Well당 상위 n개 electrode 선택
        top_n_overall : int, optional
            전체 상위 n개 선택 (설정 시 top_n_per_well 무시)
        control_label : str
            CONTROL 조건의 라벨 (예: "CONTROL", "VEH", "DMSO")
        drug_labels : List[str], optional
            DRUG 조건의 라벨들 (예: ["DRUG_A", "DRUG_B"])
        condition_column : str
            조건을 구분하는 컬럼 (예: "EXP_TYPE", "DRUG")
        metrics : List[str], optional
            분석할 metric 목록
        """
        self.electrode_data_path = Path(electrode_data_path)
        self.scores_path = Path(scores_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.top_n_per_well = top_n_per_well
        self.top_n_overall = top_n_overall
        self.control_label = control_label
        self.drug_labels = drug_labels or []
        self.condition_column = condition_column
        self.metrics = metrics or ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']

        # Data holders
        self.electrode_data = None
        self.scores_df = None
        self.selected_electrodes = []
        self.control_lr = None
        self.drug_lr_dict = {}  # {drug_label: drug_lr_df}
        self.drug_effect_dict = {}  # {drug_label: drug_effect_df}
        self.stats_dict = {}  # {drug_label: stats_df}

        self.performance = PerformanceMonitor()
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    def run(self):
        """전체 파이프라인 실행"""
        print('='*80)
        print('MEA DRUG EFFECT ANALYZER')
        print('='*80)
        print(f'\nElectrode Data: {self.electrode_data_path}')
        print(f'Scores: {self.scores_path}')
        print(f'Output: {self.output_dir}')
        print(f'Condition Column: {self.condition_column}')
        print(f'CONTROL Label: {self.control_label}')
        print(f'DRUG Labels: {self.drug_labels}')
        print(f'Selection: Top {self.top_n_overall or self.top_n_per_well} '
              f'{"overall" if self.top_n_overall else "per well"}')
        print(f'Timestamp: {self.timestamp}')
        print('='*80)

        pipeline_start = time.time()

        # Stage 1: Load data
        stage_start = time.time()
        print('\n[STAGE 1] Loading data...')
        self._load_data()
        self.performance.record('Stage 1: Data Loading', time.time() - stage_start)

        if self.electrode_data is None or self.scores_df is None:
            print('❌ Failed to load data')
            return self

        # Auto-detect drug labels if not specified
        if not self.drug_labels:
            self._auto_detect_drug_labels()

        if not self.drug_labels:
            print('❌ No DRUG conditions found')
            return self

        # Stage 2: Select electrodes
        stage_start = time.time()
        print('\n[STAGE 2] Selecting top electrodes...')
        self._select_electrodes()
        self.performance.record('Stage 2: Electrode Selection', time.time() - stage_start)

        # Stage 3: Calculate Light Response
        stage_start = time.time()
        print('\n[STAGE 3] Calculating Light Responses...')
        self._calculate_light_responses()
        self.performance.record('Stage 3: Light Response', time.time() - stage_start)

        # Stage 4: Calculate Drug Effects (for each drug)
        stage_start = time.time()
        print('\n[STAGE 4] Calculating Drug Effects...')
        self._calculate_drug_effects()
        self.performance.record('Stage 4: Drug Effects', time.time() - stage_start)

        # Stage 5: Statistical Analysis
        stage_start = time.time()
        print('\n[STAGE 5] Running Statistical Analysis...')
        self._run_statistics()
        self.performance.record('Stage 5: Statistics', time.time() - stage_start)

        # Stage 6: Visualizations (for each drug)
        stage_start = time.time()
        print('\n[STAGE 6] Creating Visualizations...')
        self._create_visualizations()
        self.performance.record('Stage 6: Visualizations', time.time() - stage_start)

        # Stage 7: Excel Reports
        stage_start = time.time()
        print('\n[STAGE 7] Creating Excel Reports...')
        self._create_excel_reports()
        self.performance.record('Stage 7: Excel Reports', time.time() - stage_start)

        # Stage 8: Dashboards
        stage_start = time.time()
        print('\n[STAGE 8] Creating Dashboards...')
        self._create_dashboards()
        self.performance.record('Stage 8: Dashboards', time.time() - stage_start)

        # Summary
        total_time = time.time() - pipeline_start
        self.performance.record('Total Pipeline', total_time)
        self.performance.print_summary()

        # Save selected electrodes
        self._save_selected_electrodes()

        print('\n' + '='*80)
        print('🎉 DRUG EFFECT ANALYSIS COMPLETE!')
        print('='*80)
        print(f'\nSelected Electrodes: {len(self.selected_electrodes)}')
        print(f'CONTROL: {self.control_label}')
        print(f'DRUG Conditions Analyzed: {", ".join(self.drug_labels)}')
        print(f'Results: {self.output_dir}')
        print(f'Total time: {total_time:.2f}s')
        print('='*80)

        gc.collect()
        return self

    def _load_data(self):
        """데이터 로드"""
        # Electrode data
        if self.electrode_data_path.suffix == '.parquet':
            self.electrode_data = pd.read_parquet(self.electrode_data_path)
        else:
            self.electrode_data = pd.read_csv(self.electrode_data_path)
        print(f"  ✓ Electrode data: {len(self.electrode_data)} rows")

        # Scores
        self.scores_df = pd.read_csv(self.scores_path)
        print(f"  ✓ Scores: {len(self.scores_df)} electrodes")

        # Check condition column
        if self.condition_column not in self.electrode_data.columns:
            print(f"  ⚠ Column '{self.condition_column}' not found. Available: {list(self.electrode_data.columns)}")
            # Try alternative columns
            for alt in ['EXP_TYPE', 'DRUG', 'Condition', 'Treatment']:
                if alt in self.electrode_data.columns:
                    self.condition_column = alt
                    print(f"  ✓ Using alternative column: {self.condition_column}")
                    break

    def _auto_detect_drug_labels(self):
        """DRUG 라벨 자동 감지"""
        if self.condition_column not in self.electrode_data.columns:
            return

        all_conditions = self.electrode_data[self.condition_column].unique()
        self.drug_labels = [c for c in all_conditions if c != self.control_label]

        print(f"  ✓ Auto-detected conditions: {all_conditions.tolist()}")
        print(f"  ✓ CONTROL: {self.control_label}")
        print(f"  ✓ DRUG: {self.drug_labels}")

    def _select_electrodes(self):
        """Top electrode 선택"""
        if self.top_n_overall is not None:
            self.selected_electrodes = self.scores_df.head(self.top_n_overall)['Electrode_ID'].tolist()
        else:
            self.selected_electrodes = (
                self.scores_df.groupby('Well')
                .apply(lambda x: x.nlargest(self.top_n_per_well, 'Response_Score'))
                .reset_index(drop=True)['Electrode_ID'].tolist()
            )

        print(f"  ✓ Selected: {len(self.selected_electrodes)} electrodes")

    def _calculate_light_responses(self):
        """Light Response 계산 (CONTROL 및 각 DRUG)"""
        # 개선: Score map 생성하여 LightResponseCalculator에 전달
        score_map = dict(zip(self.scores_df['Electrode_ID'], self.scores_df['Response_Score']))

        lr_calc = LightResponseCalculator(
            self.electrode_data,
            self.selected_electrodes,
            score_map=score_map  # Score-weighted 계산 지원
        )

        # CONTROL Light Response
        self.control_lr = lr_calc.calculate(
            condition_col=self.condition_column,
            condition_value=self.control_label,
            metrics=self.metrics
        )
        print(f"  ✓ CONTROL LR: {len(self.control_lr)} records")

        # DRUG Light Responses
        for drug_label in self.drug_labels:
            drug_lr = lr_calc.calculate(
                condition_col=self.condition_column,
                condition_value=drug_label,
                metrics=self.metrics
            )
            self.drug_lr_dict[drug_label] = drug_lr
            print(f"  ✓ {drug_label} LR: {len(drug_lr)} records")

    def _calculate_drug_effects(self):
        """Drug Effect 계산"""
        for drug_label, drug_lr in self.drug_lr_dict.items():
            print(f"\n  Processing: {drug_label}")

            calculator = DrugEffectCalculator(self.control_lr, drug_lr)
            drug_effect = calculator.calculate()

            self.drug_effect_dict[drug_label] = drug_effect

    def _run_statistics(self):
        """통계 분석"""
        for drug_label, drug_effect in self.drug_effect_dict.items():
            print(f"\n  Statistics for: {drug_label}")

            stats_analyzer = DrugEffectStatistics(drug_effect)
            stats_results = stats_analyzer.run_tests()

            self.stats_dict[drug_label] = stats_results

    def _create_visualizations(self):
        """시각화 생성"""
        for drug_label in self.drug_labels:
            print(f"\n  Visualizations for: {drug_label}")

            drug_output = self.output_dir / drug_label
            drug_output.mkdir(parents=True, exist_ok=True)

            visualizer = DrugEffectVisualizer(
                control_lr=self.control_lr,
                drug_lr=self.drug_lr_dict.get(drug_label, pd.DataFrame()),
                drug_effect=self.drug_effect_dict.get(drug_label, pd.DataFrame()),
                stats_results=self.stats_dict.get(drug_label),
                output_dir=drug_output
            )
            visualizer.create_all()

    def _create_excel_reports(self):
        """Excel 리포트 생성"""
        for drug_label in self.drug_labels:
            print(f"\n  Excel for: {drug_label}")

            drug_output = self.output_dir / drug_label
            excel_path = drug_output / f'DRUG_EFFECT_{drug_label}.xlsx'

            exporter = DrugEffectExcelExporter(
                control_lr=self.control_lr,
                drug_lr=self.drug_lr_dict.get(drug_label, pd.DataFrame()),
                drug_effect=self.drug_effect_dict.get(drug_label, pd.DataFrame()),
                stats_results=self.stats_dict.get(drug_label),
                selected_electrodes=self.selected_electrodes,
                output_path=excel_path
            )
            exporter.create()

    def _create_dashboards(self):
        """대시보드 생성"""
        for drug_label in self.drug_labels:
            print(f"\n  Dashboard for: {drug_label}")

            drug_output = self.output_dir / drug_label
            dashboard_path = drug_output / f'DRUG_EFFECT_DASHBOARD_{drug_label}.png'

            dashboard = DrugEffectDashboard(
                control_lr=self.control_lr,
                drug_lr=self.drug_lr_dict.get(drug_label, pd.DataFrame()),
                drug_effect=self.drug_effect_dict.get(drug_label, pd.DataFrame()),
                stats_results=self.stats_dict.get(drug_label),
                selected_electrodes=self.selected_electrodes,
                output_path=dashboard_path
            )
            dashboard.create()

    def _save_selected_electrodes(self):
        """선택된 electrode 목록 저장"""
        selected_df = pd.DataFrame({
            'Electrode_ID': self.selected_electrodes
        })
        selected_df = selected_df.merge(
            self.scores_df[['Electrode_ID', 'Well', 'Response_Score']],
            on='Electrode_ID', how='left'
        )
        selected_df.to_csv(self.output_dir / 'selected_electrodes.csv', index=False)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Example usage
    analyzer = DrugEffectAnalyzer(
        electrode_data_path=r"D:\MyProjects\#4-2\output_electrode2\electrode_all_long.parquet",
        scores_path=r"D:\MyProjects\#4-2\output_electrode2\electrode_scores\electrode_response_scores.csv",
        output_dir=r"D:\MyProjects\#4-2\output_electrode2\drug_effect_analysis",
        top_n_per_well=3,
        control_label="CONTROL",  # 데이터에 맞게 수정
        drug_labels=None,  # None이면 자동 감지
        condition_column="EXP_TYPE",  # 또는 "DRUG"
        metrics=['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
    )
    analyzer.run()
