"""
MEA Electrode Pooled Analyzer
==============================
High-score electrode의 데이터를 pooling하여 분석하는 파이프라인

입력: mea_electrode_analyzer_v3_clean의 electrode score 결과
출력: mea_full_pipeline_v32 / mea_optimized_pipeline_v2 스타일의 엑셀 및 시각화

주요 기능:
1. Electrode score 기반 top N electrode 선택
2. 선택된 electrode 데이터를 Well 단위로 pooling
3. Spontaneous, Light Response, Drug Effect, Burst 분석
4. Combined Excel 생성
5. Dashboard 시각화

Usage:
    from mea_electrode_pooled_analyzer import ElectrodePooledAnalyzer

    analyzer = ElectrodePooledAnalyzer(
        electrode_data_path=r"D:\\output\\electrode_all_long.parquet",
        scores_path=r"D:\\output\\electrode_scores\\electrode_response_scores.csv",
        output_dir=r"D:\\output\\pooled_analysis",
        top_n_per_well=3  # 각 well에서 상위 3개 electrode
    )
    analyzer.run()
"""

from pathlib import Path
import time
from functools import wraps
from typing import Optional, List
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
    'base': '#5DADE2',      # Sky blue
    'stim': '#EC7063',      # Coral red
    'positive': '#58D68D',  # Green
    'negative': '#EC7063',  # Red
    'neutral': '#85929E',   # Gray
    'BL': '#0066CC',        # Blue Light
    'GR': '#00AA00',        # Green
    'OR': '#FF8800',        # Orange
    'RD': '#DD0000',        # Red
}


# =============================================================================
# DATA POOLING
# =============================================================================

class ElectrodeDataPooler:
    """Top score electrode 데이터 pooling"""

    def __init__(self, electrode_data: pd.DataFrame, scores_df: pd.DataFrame):
        self.electrode_data = electrode_data
        self.scores_df = scores_df

    def get_top_electrodes(self, top_n_per_well: int = 3,
                           top_n_overall: Optional[int] = None) -> List[str]:
        """
        Top electrode ID 목록 가져오기

        Parameters:
        -----------
        top_n_per_well : int
            각 well에서 상위 n개 선택
        top_n_overall : int, optional
            전체 상위 n개 선택 (설정 시 top_n_per_well 무시)

        Returns:
        --------
        List[str]
            선택된 Electrode_ID 목록
        """
        if top_n_overall is not None:
            top_electrodes = self.scores_df.head(top_n_overall)['Electrode_ID'].tolist()
        else:
            top_electrodes = (
                self.scores_df.groupby('Well')
                .apply(lambda x: x.nlargest(top_n_per_well, 'Response_Score'))
                .reset_index(drop=True)['Electrode_ID'].tolist()
            )

        return top_electrodes

    @timer
    def pool_electrode_data(self, electrode_ids: List[str]) -> pd.DataFrame:
        """
        선택된 electrode의 데이터를 Well 단위로 pooling

        Parameters:
        -----------
        electrode_ids : List[str]
            Electrode_ID 목록

        Returns:
        --------
        pd.DataFrame
            Well 단위로 pooling된 데이터 (mea_auto_analyzer_v32 형식)
        """
        print(f"\n[POOLER] Pooling data from {len(electrode_ids)} electrodes...")

        # 선택된 electrode 데이터 필터링
        filtered = self.electrode_data[
            self.electrode_data['Electrode_ID'].isin(electrode_ids)
        ].copy()

        print(f"  ✓ Filtered: {len(filtered)} rows")

        if filtered.empty:
            return pd.DataFrame()

        # Well 단위로 집계 (평균)
        group_cols = ['Well', 'Metric', 'BASE_STIM']

        # 추가 그룹 컬럼 (있는 경우)
        for col in ['LIGHT_CODE', 'EXP_TYPE', 'DRUG', 'Plate_ID']:
            if col in filtered.columns:
                group_cols.append(col)

        pooled = filtered.groupby(group_cols).agg({
            'Value': ['mean', 'std', 'count']
        }).reset_index()

        # 컬럼명 평탄화
        pooled.columns = [
            '_'.join(col).strip('_') if isinstance(col, tuple) else col
            for col in pooled.columns
        ]

        # 컬럼명 정리
        pooled = pooled.rename(columns={
            'Value_mean': 'Value',
            'Value_std': 'Value_std',
            'Value_count': 'n_electrodes'
        })

        print(f"  ✓ Pooled: {len(pooled)} rows, {pooled['Well'].nunique()} wells")

        # 선택된 electrode 정보 추가
        pooled['Selected_Electrodes'] = ', '.join(electrode_ids[:10])
        if len(electrode_ids) > 10:
            pooled['Selected_Electrodes'] += f'... (+{len(electrode_ids)-10} more)'

        return pooled


# =============================================================================
# SPONTANEOUS ANALYZER
# =============================================================================

class SpontaneousAnalyzerPooled:
    """Spontaneous activity 분석 (Baseline only)"""

    def __init__(self, df: pd.DataFrame, output_dir: Path):
        self.df = df
        self.output_dir = Path(output_dir) / '01_spontaneous'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_df = None
        self.summary = None

    @timer
    def analyze(self):
        """Baseline 데이터 분석"""
        print('\n[1] Spontaneous Analysis (Baseline Only)...')

        # Baseline만 필터링
        self.baseline_df = self.df[self.df['BASE_STIM'] == 'BASE'].copy()

        if self.baseline_df.empty:
            print('  ⚠ No baseline data')
            return self

        # Summary statistics
        self.summary = self.baseline_df.groupby(['Well', 'Metric']).agg({
            'Value': ['mean', 'std', 'min', 'max']
        }).reset_index()
        self.summary.columns = ['Well', 'Metric', 'Mean', 'Std', 'Min', 'Max']

        # Save
        self.baseline_df.to_csv(self.output_dir / 'spontaneous_baseline.csv', index=False)
        self.summary.to_csv(self.output_dir / 'spontaneous_summary.csv', index=False)

        print(f"  ✓ Analyzed {self.baseline_df['Well'].nunique()} wells")
        return self

    @timer
    def visualize(self):
        """시각화"""
        if self.baseline_df is None or self.baseline_df.empty:
            return self

        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
        available = [m for m in key_metrics if m in self.baseline_df['Metric'].unique()]

        if not available:
            return self

        # Well별 비교
        fig, axes = plt.subplots(1, len(available), figsize=(6*len(available), 6))
        if len(available) == 1:
            axes = [axes]

        for idx, metric in enumerate(available):
            ax = axes[idx]
            metric_data = self.baseline_df[self.baseline_df['Metric'] == metric]

            wells = sorted(metric_data['Well'].unique())
            well_means = metric_data.groupby('Well')['Value'].mean().reindex(wells)

            ax.bar(range(len(wells)), well_means.values, alpha=0.7,
                  edgecolor='black', color=COLORS['base'])
            ax.set_xticks(range(len(wells)))
            ax.set_xticklabels(wells, rotation=45, ha='right')
            ax.set_xlabel('Well', fontweight='bold')
            ax.set_ylabel('Mean Value', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}\n(Baseline)',
                        fontweight='bold')
            ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'spontaneous_by_well.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

        print('  ✓ Spontaneous visualizations complete')
        return self


# =============================================================================
# LIGHT RESPONSE ANALYZER
# =============================================================================

class LightResponseAnalyzerPooled:
    """Light Response 분석"""

    def __init__(self, df: pd.DataFrame, output_dir: Path):
        self.df = df
        self.output_dir = Path(output_dir) / '02_light_response'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.response_df = None
        self.summary = None

    @timer
    def analyze(self):
        """Light response 분석"""
        print('\n[2] Light Response Analysis...')

        if 'BASE_STIM' not in self.df.columns:
            print('  ⚠ No BASE_STIM column')
            return self

        base = self.df[self.df['BASE_STIM'] == 'BASE']
        stim = self.df[self.df['BASE_STIM'] == 'STIM']

        if base.empty or stim.empty:
            print('  ⚠ Missing BASE or STIM data')
            return self

        # Response 계산
        responses = []

        for well in self.df['Well'].unique():
            for metric in self.df['Metric'].unique():
                base_val = base[(base['Well'] == well) & (base['Metric'] == metric)]['Value'].mean()
                stim_val = stim[(stim['Well'] == well) & (stim['Metric'] == metric)]['Value'].mean()

                if pd.notna(base_val) and pd.notna(stim_val):
                    response = stim_val - base_val
                    pct_change = (response / (base_val + 1e-6)) * 100
                    fold_change = (stim_val + 1e-6) / (base_val + 1e-6)

                    light_code = self.df[self.df['Well'] == well]['LIGHT_CODE'].iloc[0] if 'LIGHT_CODE' in self.df.columns else 'UNKNOWN'

                    responses.append({
                        'Well': well,
                        'Metric': metric,
                        'LIGHT_CODE': light_code,
                        'BASE': base_val,
                        'STIM': stim_val,
                        'Response': response,
                        'Pct_Change': pct_change,
                        'Fold_Change': fold_change
                    })

        self.response_df = pd.DataFrame(responses)

        if not self.response_df.empty:
            self.response_df.to_csv(self.output_dir / 'light_response.csv', index=False)

            # Summary by light code
            if 'LIGHT_CODE' in self.response_df.columns:
                self.summary = self.response_df.groupby(['LIGHT_CODE', 'Metric']).agg({
                    'Response': ['mean', 'std'],
                    'Fold_Change': ['mean', 'std']
                }).reset_index()
                self.summary.columns = ['LIGHT_CODE', 'Metric', 'Response_Mean', 'Response_Std',
                                        'FoldChange_Mean', 'FoldChange_Std']
                self.summary.to_csv(self.output_dir / 'light_response_summary.csv', index=False)

        print(f"  ✓ Analyzed {len(responses)} responses")
        return self

    @timer
    def visualize(self):
        """시각화"""
        if self.response_df is None or self.response_df.empty:
            return self

        # 1. BASE vs STIM comparison
        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
        available = [m for m in key_metrics if m in self.response_df['Metric'].unique()]

        if available:
            fig, axes = plt.subplots(1, len(available), figsize=(6*len(available), 6))
            if len(available) == 1:
                axes = [axes]

            for idx, metric in enumerate(available):
                ax = axes[idx]
                metric_data = self.response_df[self.response_df['Metric'] == metric]

                if 'LIGHT_CODE' in metric_data.columns:
                    light_codes = sorted(metric_data['LIGHT_CODE'].unique())

                    for i, lc in enumerate(light_codes):
                        lc_data = metric_data[metric_data['LIGHT_CODE'] == lc]
                        x = [i - 0.2, i + 0.2]
                        y = [lc_data['BASE'].mean(), lc_data['STIM'].mean()]

                        ax.bar(x, y, width=0.35, alpha=0.8,
                              color=[COLORS['base'], COLORS['stim']],
                              edgecolor='black')

                    ax.set_xticks(range(len(light_codes)))
                    ax.set_xticklabels(light_codes, rotation=45, ha='right')
                    ax.set_xlabel('Light Code', fontweight='bold')
                else:
                    ax.bar([0, 1], [metric_data['BASE'].mean(), metric_data['STIM'].mean()],
                          width=0.6, alpha=0.8,
                          color=[COLORS['base'], COLORS['stim']],
                          edgecolor='black')
                    ax.set_xticks([0, 1])
                    ax.set_xticklabels(['BASE', 'STIM'])

                ax.set_ylabel('Mean Value', fontweight='bold')
                ax.set_title(f'{metric.replace("_", " ").title()}\nBASE vs STIM',
                            fontweight='bold')
                ax.grid(axis='y', alpha=0.3)
                ax.legend(['BASE', 'STIM'], loc='upper right')

            plt.tight_layout()
            plt.savefig(self.output_dir / 'light_response_comparison.png', dpi=300, bbox_inches='tight')
            plt.close(fig)

        # 2. Response heatmap
        if 'LIGHT_CODE' in self.response_df.columns and available:
            pivot = self.response_df[self.response_df['Metric'].isin(available)].pivot_table(
                index='LIGHT_CODE', columns='Metric', values='Fold_Change', aggfunc='mean')

            if not pivot.empty:
                fig, ax = plt.subplots(figsize=(10, 6))
                sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn', center=1,
                           cbar_kws={'label': 'Fold Change'}, ax=ax)
                ax.set_title('Light Response Fold Change\n(LIGHT_CODE × Metric)',
                            fontweight='bold', fontsize=12)
                plt.tight_layout()
                plt.savefig(self.output_dir / 'light_response_heatmap.png', dpi=300, bbox_inches='tight')
                plt.close(fig)

        print('  ✓ Light response visualizations complete')
        return self


# =============================================================================
# BURST ANALYZER
# =============================================================================

class BurstAnalyzerPooled:
    """Burst 분석"""

    def __init__(self, df: pd.DataFrame, output_dir: Path):
        self.df = df
        self.output_dir = Path(output_dir) / '03_burst_analysis'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.burst_df = None
        self.summary = None

    @timer
    def analyze(self):
        """Burst metrics 분석"""
        print('\n[3] Burst Analysis...')

        # Burst 관련 metric 필터링
        burst_mask = self.df['Metric'].str.contains('burst', case=False, na=False)
        self.burst_df = self.df[burst_mask].copy()

        if self.burst_df.empty:
            print('  ⚠ No burst metrics found')
            return self

        # Summary
        group_cols = ['Well', 'Metric', 'BASE_STIM']
        if 'LIGHT_CODE' in self.burst_df.columns:
            group_cols.insert(1, 'LIGHT_CODE')

        self.summary = self.burst_df.groupby(group_cols).agg({
            'Value': ['mean', 'std', 'count']
        }).reset_index()
        self.summary.columns = group_cols + ['Mean', 'Std', 'Count']

        # Save
        self.burst_df.to_csv(self.output_dir / 'burst_data.csv', index=False)
        self.summary.to_csv(self.output_dir / 'burst_summary.csv', index=False)

        print(f"  ✓ Found {len(self.burst_df['Metric'].unique())} burst metrics")
        return self

    @timer
    def visualize(self):
        """시각화"""
        if self.burst_df is None or self.burst_df.empty:
            return self

        # Key burst metrics
        burst_metrics = ['burst_frequency_hz', 'burst_duration_avg_s',
                        'spikes_per_burst_avg', 'inter_burst_interval_avg_s']
        available = [m for m in burst_metrics if m in self.burst_df['Metric'].unique()]

        if not available:
            return self

        # Well comparison
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        axes = axes.flatten()

        for idx, metric in enumerate(available[:4]):
            ax = axes[idx]
            metric_data = self.burst_df[self.burst_df['Metric'] == metric]

            well_means = metric_data.groupby('Well')['Value'].mean().sort_values(ascending=False)

            ax.bar(range(len(well_means)), well_means.values, alpha=0.7,
                  edgecolor='black', color=COLORS['positive'])
            ax.set_xticks(range(len(well_means)))
            ax.set_xticklabels(well_means.index, rotation=45, ha='right')
            ax.set_ylabel('Mean Value', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}', fontweight='bold')
            ax.grid(axis='y', alpha=0.3)

        for idx in range(len(available), 4):
            axes[idx].set_visible(False)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'burst_by_well.png', dpi=300, bbox_inches='tight')
        plt.close(fig)

        print('  ✓ Burst visualizations complete')
        return self


# =============================================================================
# COMBINED EXCEL CREATOR
# =============================================================================

class CombinedExcelCreator:
    """Combined Excel 생성"""

    def __init__(self, df: pd.DataFrame, pooled_df: pd.DataFrame,
                 selected_electrodes: List[str], output_path: Path):
        self.df = df
        self.pooled_df = pooled_df
        self.selected_electrodes = selected_electrodes
        self.output_path = Path(output_path)

    @timer
    def create(self):
        """Excel 파일 생성"""
        print('\n[EXCEL] Creating combined Excel...')

        with pd.ExcelWriter(self.output_path, engine='openpyxl') as writer:
            # Sheet 1: Pooled Summary
            self.pooled_df.to_excel(writer, sheet_name='Pooled_Summary', index=False)

            # Sheet 2: Selected Electrodes
            electrode_info = pd.DataFrame({
                'Electrode_ID': self.selected_electrodes,
                'Selection_Order': range(1, len(self.selected_electrodes) + 1)
            })
            electrode_info.to_excel(writer, sheet_name='Selected_Electrodes', index=False)

            # Sheet 3: Raw Data (샘플)
            if len(self.df) > 10000:
                self.df.head(10000).to_excel(writer, sheet_name='Raw_Data_Sample', index=False)
            else:
                self.df.to_excel(writer, sheet_name='Raw_Data', index=False)

            # Sheet 4: Pivot by Metric
            pivot = self.pooled_df.pivot_table(
                index='Well', columns='Metric', values='Value', aggfunc='mean')
            pivot.to_excel(writer, sheet_name='Pivot_by_Metric')

        print(f"  ✓ Saved: {self.output_path.name}")


# =============================================================================
# DASHBOARD
# =============================================================================

class PooledDashboard:
    """Pooled analysis dashboard"""

    def __init__(self, df: pd.DataFrame, pooled_df: pd.DataFrame,
                 selected_electrodes: List[str], scores_df: pd.DataFrame,
                 output_path: Path):
        self.df = df
        self.pooled_df = pooled_df
        self.selected_electrodes = selected_electrodes
        self.scores_df = scores_df
        self.output_path = Path(output_path)

    @timer
    def create(self):
        """Dashboard 생성"""
        print('\n[DASHBOARD] Creating pooled analysis dashboard...')

        fig = plt.figure(figsize=(20, 16))
        gs = fig.add_gridspec(4, 4, hspace=0.35, wspace=0.3)

        # Row 1: Selected electrodes info
        ax1 = fig.add_subplot(gs[0, :2])
        self._plot_selected_scores(ax1)

        ax2 = fig.add_subplot(gs[0, 2:])
        self._plot_electrode_distribution(ax2)

        # Row 2: Spontaneous
        ax3 = fig.add_subplot(gs[1, :2])
        self._plot_spontaneous(ax3)

        ax4 = fig.add_subplot(gs[1, 2:])
        self._plot_base_stim_comparison(ax4)

        # Row 3: Light response
        ax5 = fig.add_subplot(gs[2, :2])
        self._plot_light_response(ax5)

        ax6 = fig.add_subplot(gs[2, 2:])
        self._plot_fold_change_heatmap(ax6)

        # Row 4: Burst
        ax7 = fig.add_subplot(gs[3, :2])
        self._plot_burst_metrics(ax7)

        ax8 = fig.add_subplot(gs[3, 2:])
        self._plot_summary_stats(ax8)

        fig.suptitle(f'MEA Pooled Analysis Dashboard\n'
                    f'({len(self.selected_electrodes)} High-Score Electrodes)',
                    fontweight='bold', fontsize=16, y=0.98)

        plt.savefig(self.output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)

        print(f"  ✓ Dashboard saved: {self.output_path.name}")

    def _plot_selected_scores(self, ax):
        """선택된 electrode의 score"""
        selected_scores = self.scores_df[
            self.scores_df['Electrode_ID'].isin(self.selected_electrodes)
        ].head(15)

        if selected_scores.empty:
            ax.text(0.5, 0.5, 'No score data', ha='center', va='center')
            return

        y_pos = np.arange(len(selected_scores))
        ax.barh(y_pos, selected_scores['Response_Score'].values,
               color=COLORS['positive'], edgecolor='black', alpha=0.8)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(selected_scores['Electrode_ID'].values, fontsize=9)
        ax.set_xlabel('Response Score', fontweight='bold')
        ax.set_title('Top Selected Electrodes (by Score)', fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

    def _plot_electrode_distribution(self, ax):
        """선택된 electrode의 Well 분포"""
        well_counts = pd.Series(self.selected_electrodes).str.extract(r'^([A-D][1-6])')[0].value_counts()

        ax.bar(range(len(well_counts)), well_counts.values,
              color=COLORS['neutral'], edgecolor='black', alpha=0.7)
        ax.set_xticks(range(len(well_counts)))
        ax.set_xticklabels(well_counts.index, rotation=45, ha='right')
        ax.set_xlabel('Well', fontweight='bold')
        ax.set_ylabel('Count', fontweight='bold')
        ax.set_title('Selected Electrodes per Well', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    def _plot_spontaneous(self, ax):
        """Spontaneous activity"""
        baseline = self.pooled_df[self.pooled_df['BASE_STIM'] == 'BASE']
        spike_data = baseline[baseline['Metric'].str.contains('spike', case=False, na=False)]

        if spike_data.empty:
            ax.text(0.5, 0.5, 'No spike data', ha='center', va='center')
            return

        well_means = spike_data.groupby('Well')['Value'].mean().sort_values(ascending=False)

        ax.bar(range(len(well_means)), well_means.values,
              color=COLORS['base'], edgecolor='black', alpha=0.7)
        ax.set_xticks(range(len(well_means)))
        ax.set_xticklabels(well_means.index, rotation=45, ha='right', fontsize=9)
        ax.set_xlabel('Well', fontweight='bold')
        ax.set_ylabel('Mean Spikes', fontweight='bold')
        ax.set_title('Spontaneous Activity (Baseline)', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    def _plot_base_stim_comparison(self, ax):
        """BASE vs STIM comparison"""
        spike_metric = None
        for m in ['number_of_spikes', 'mean_firing_rate_hz']:
            if m in self.pooled_df['Metric'].unique():
                spike_metric = m
                break

        if spike_metric is None:
            ax.text(0.5, 0.5, 'No metric data', ha='center', va='center')
            return

        metric_data = self.pooled_df[self.pooled_df['Metric'] == spike_metric]
        base_mean = metric_data[metric_data['BASE_STIM'] == 'BASE']['Value'].mean()
        stim_mean = metric_data[metric_data['BASE_STIM'] == 'STIM']['Value'].mean()

        ax.bar([0, 1], [base_mean, stim_mean], width=0.6,
              color=[COLORS['base'], COLORS['stim']], edgecolor='black', alpha=0.8)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['BASE', 'STIM'], fontweight='bold')
        ax.set_ylabel('Mean Value', fontweight='bold')
        ax.set_title(f'{spike_metric.replace("_", " ").title()}\nBASE vs STIM', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    def _plot_light_response(self, ax):
        """Light response by light code"""
        if 'LIGHT_CODE' not in self.pooled_df.columns:
            ax.text(0.5, 0.5, 'No LIGHT_CODE', ha='center', va='center')
            return

        stim_data = self.pooled_df[self.pooled_df['BASE_STIM'] == 'STIM']
        spike_data = stim_data[stim_data['Metric'].str.contains('spike', case=False, na=False)]

        if spike_data.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center')
            return

        light_means = spike_data.groupby('LIGHT_CODE')['Value'].mean().sort_index()
        colors_list = [COLORS.get(lc, COLORS['neutral']) for lc in light_means.index]

        ax.bar(range(len(light_means)), light_means.values,
              color=colors_list, edgecolor='black', alpha=0.8)
        ax.set_xticks(range(len(light_means)))
        ax.set_xticklabels(light_means.index, fontweight='bold')
        ax.set_xlabel('Light Code', fontweight='bold')
        ax.set_ylabel('Mean Spikes (STIM)', fontweight='bold')
        ax.set_title('Light Response by Light Code', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    def _plot_fold_change_heatmap(self, ax):
        """Fold change mini heatmap"""
        if 'LIGHT_CODE' not in self.pooled_df.columns:
            ax.text(0.5, 0.5, 'No LIGHT_CODE', ha='center', va='center')
            return

        # Calculate fold change
        key_metrics = ['number_of_spikes', 'mean_firing_rate_hz', 'burst_frequency_hz']
        available = [m for m in key_metrics if m in self.pooled_df['Metric'].unique()]

        if not available:
            ax.text(0.5, 0.5, 'No metrics', ha='center', va='center')
            return

        fc_data = []
        for lc in self.pooled_df['LIGHT_CODE'].unique():
            for m in available:
                base = self.pooled_df[(self.pooled_df['LIGHT_CODE'] == lc) &
                                      (self.pooled_df['Metric'] == m) &
                                      (self.pooled_df['BASE_STIM'] == 'BASE')]['Value'].mean()
                stim = self.pooled_df[(self.pooled_df['LIGHT_CODE'] == lc) &
                                      (self.pooled_df['Metric'] == m) &
                                      (self.pooled_df['BASE_STIM'] == 'STIM')]['Value'].mean()
                if pd.notna(base) and pd.notna(stim) and base > 0:
                    fc_data.append({'LIGHT_CODE': lc, 'Metric': m, 'FC': stim/base})

        if not fc_data:
            ax.text(0.5, 0.5, 'No fold change', ha='center', va='center')
            return

        fc_df = pd.DataFrame(fc_data)
        pivot = fc_df.pivot(index='LIGHT_CODE', columns='Metric', values='FC')

        sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn', center=1,
                   cbar_kws={'label': 'Fold Change'}, ax=ax, annot_kws={'size': 9})
        ax.set_title('Fold Change (STIM/BASE)', fontweight='bold')

    def _plot_burst_metrics(self, ax):
        """Burst metrics"""
        burst_data = self.pooled_df[self.pooled_df['Metric'].str.contains('burst', case=False, na=False)]

        if burst_data.empty:
            ax.text(0.5, 0.5, 'No burst data', ha='center', va='center')
            return

        metric_counts = burst_data['Metric'].value_counts().head(5)

        ax.barh(range(len(metric_counts)), metric_counts.values,
               color=COLORS['stim'], edgecolor='black', alpha=0.7)
        ax.set_yticks(range(len(metric_counts)))
        ax.set_yticklabels([m.replace('_', ' ').title()[:25] for m in metric_counts.index], fontsize=9)
        ax.set_xlabel('Data Points', fontweight='bold')
        ax.set_title('Available Burst Metrics', fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

    def _plot_summary_stats(self, ax):
        """Summary statistics text"""
        ax.axis('off')

        stats_text = [
            f"Total Electrodes Selected: {len(self.selected_electrodes)}",
            f"Wells Covered: {self.pooled_df['Well'].nunique() if 'Well' in self.pooled_df.columns else 'N/A'}",
            f"Metrics Analyzed: {self.pooled_df['Metric'].nunique() if 'Metric' in self.pooled_df.columns else 'N/A'}",
            f"Data Points: {len(self.pooled_df)}",
            "",
            "Top 5 Electrodes:",
        ]

        for i, eid in enumerate(self.selected_electrodes[:5]):
            score = self.scores_df[self.scores_df['Electrode_ID'] == eid]['Response_Score'].values
            score_str = f"{score[0]:.2f}" if len(score) > 0 else "N/A"
            stats_text.append(f"  {i+1}. {eid}: {score_str}")

        ax.text(0.1, 0.9, '\n'.join(stats_text),
               transform=ax.transAxes, fontsize=11, verticalalignment='top',
               fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.3))
        ax.set_title('Summary Statistics', fontweight='bold')


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class ElectrodePooledAnalyzer:
    """
    High-score electrode pooled analysis pipeline

    Usage:
        analyzer = ElectrodePooledAnalyzer(
            electrode_data_path=r"D:\\output\\electrode_all_long.parquet",
            scores_path=r"D:\\output\\electrode_scores\\electrode_response_scores.csv",
            output_dir=r"D:\\output\\pooled_analysis",
            top_n_per_well=3
        )
        analyzer.run()
    """

    def __init__(self, electrode_data_path: str, scores_path: str,
                 output_dir: str, top_n_per_well: int = 3,
                 top_n_overall: Optional[int] = None):
        """
        Parameters:
        -----------
        electrode_data_path : str
            electrode_all_long.parquet 또는 .csv 경로
        scores_path : str
            electrode_response_scores.csv 경로
        output_dir : str
            출력 디렉토리
        top_n_per_well : int
            각 well에서 상위 n개 electrode 선택 (default: 3)
        top_n_overall : int, optional
            전체 상위 n개 선택 (설정 시 top_n_per_well 무시)
        """
        self.electrode_data_path = Path(electrode_data_path)
        self.scores_path = Path(scores_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.top_n_per_well = top_n_per_well
        self.top_n_overall = top_n_overall

        self.electrode_data = None
        self.scores_df = None
        self.pooled_df = None
        self.selected_electrodes = []

        self.performance = PerformanceMonitor()
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    def run(self):
        """전체 파이프라인 실행"""
        print('='*80)
        print('MEA ELECTRODE POOLED ANALYZER')
        print('='*80)
        print(f'\nElectrode Data: {self.electrode_data_path}')
        print(f'Scores: {self.scores_path}')
        print(f'Output: {self.output_dir}')
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

        # Stage 2: Pool data
        stage_start = time.time()
        print('\n[STAGE 2] Pooling top electrode data...')
        self._pool_data()
        self.performance.record('Stage 2: Data Pooling', time.time() - stage_start)

        if self.pooled_df is None or self.pooled_df.empty:
            print('❌ No pooled data')
            return self

        # Stage 3: Analyses
        stage_start = time.time()
        print('\n[STAGE 3] Running analyses...')

        # Spontaneous
        spont = SpontaneousAnalyzerPooled(self.pooled_df, self.output_dir)
        spont.analyze().visualize()

        # Light response
        light = LightResponseAnalyzerPooled(self.pooled_df, self.output_dir)
        light.analyze().visualize()

        # Burst
        burst = BurstAnalyzerPooled(self.pooled_df, self.output_dir)
        burst.analyze().visualize()

        self.performance.record('Stage 3: Analyses', time.time() - stage_start)

        # Stage 4: Excel
        stage_start = time.time()
        print('\n[STAGE 4] Creating Excel...')
        excel_path = self.output_dir / 'POOLED_ANALYSIS.xlsx'
        excel_creator = CombinedExcelCreator(
            self.electrode_data, self.pooled_df,
            self.selected_electrodes, excel_path
        )
        excel_creator.create()
        self.performance.record('Stage 4: Excel', time.time() - stage_start)

        # Stage 5: Dashboard
        stage_start = time.time()
        print('\n[STAGE 5] Creating dashboard...')
        dashboard_path = self.output_dir / 'POOLED_DASHBOARD.png'
        dashboard = PooledDashboard(
            self.electrode_data, self.pooled_df,
            self.selected_electrodes, self.scores_df,
            dashboard_path
        )
        dashboard.create()
        self.performance.record('Stage 5: Dashboard', time.time() - stage_start)

        # Summary
        total_time = time.time() - pipeline_start
        self.performance.record('Total Pipeline', total_time)
        self.performance.print_summary()

        # Save selected electrodes list
        selected_df = pd.DataFrame({
            'Electrode_ID': self.selected_electrodes
        })
        selected_df = selected_df.merge(self.scores_df[['Electrode_ID', 'Well', 'Response_Score']],
                                        on='Electrode_ID', how='left')
        selected_df.to_csv(self.output_dir / 'selected_electrodes.csv', index=False)

        print('\n' + '='*80)
        print('🎉 POOLED ANALYSIS COMPLETE!')
        print('='*80)
        print(f'\nSelected Electrodes: {len(self.selected_electrodes)}')
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

    def _pool_data(self):
        """데이터 pooling"""
        pooler = ElectrodeDataPooler(self.electrode_data, self.scores_df)

        # Get top electrodes
        self.selected_electrodes = pooler.get_top_electrodes(
            top_n_per_well=self.top_n_per_well,
            top_n_overall=self.top_n_overall
        )
        print(f"  ✓ Selected: {len(self.selected_electrodes)} electrodes")

        # Pool data
        self.pooled_df = pooler.pool_electrode_data(self.selected_electrodes)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Example usage
    analyzer = ElectrodePooledAnalyzer(
        electrode_data_path=r"D:\MyProjects\#4-2\output_electrode2\electrode_all_long.parquet",
        scores_path=r"D:\MyProjects\#4-2\output_electrode2\electrode_scores\electrode_response_scores.csv",
        output_dir=r"D:\MyProjects\#4-2\output_electrode2\pooled_analysis",
        top_n_per_well=3  # 각 well에서 상위 3개
    )
    analyzer.run()
