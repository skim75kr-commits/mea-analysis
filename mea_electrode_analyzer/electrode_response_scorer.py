"""
Electrode Response Scorer
--------------------------
개별 electrode의 BASE vs STIM 비율을 계산하여 light response score를 생성하고
순위를 매기는 독립적인 분석 도구

주요 기능:
- Electrode별 STIM/BASE ratio 계산
- 복수 metric의 가중 평균으로 composite score 생성
- Well별, 전체 순위 계산
- 시각화: well별 bargraph, 상위 electrode, 분포, 히트맵

Usage:
    from electrode_response_scorer import ElectrodeResponseScorer
    import pandas as pd

    # 데이터 로드
    df = pd.read_csv('electrode_all_long.csv')

    # Scorer 실행
    scorer = ElectrodeResponseScorer(df, output_dir='./results')
    scorer.calculate_scores().create_visualizations()

    # 결과 접근
    scores_df = scorer.scores_df
    print(scores_df.head(10))
"""

from pathlib import Path
import time
from functools import wraps
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns


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


# Color scheme
COLORS = {
    'base': '#5DADE2',      # Sky blue
    'stim': '#EC7063',      # Coral red
    'positive': '#58D68D',  # Green
    'negative': '#EC7063',  # Red
    'neutral': '#85929E',   # Gray
}


# =============================================================================
# ELECTRODE RESPONSE SCORER
# =============================================================================

class ElectrodeResponseScorer:
    """
    Electrode별 Light Response Score 계산 및 순위 매기기

    각 electrode에서 BASE 대비 STIM의 비율(ratio)을 계산하여
    light response가 높은 electrode를 식별합니다.

    Parameters:
    -----------
    df_all : pd.DataFrame
        전체 electrode 데이터 (long-format)
        필수 컬럼: Electrode_ID, Well, BASE_STIM, Metric, Value
    output_dir : str or Path
        결과 저장 경로

    Attributes:
    -----------
    scores_df : pd.DataFrame
        계산된 score 데이터프레임
        컬럼: Electrode_ID, Well, LIGHT_CODE, Response_Score,
              {metric}_ratio, {metric}_base, {metric}_stim,
              Rank_in_Well, Rank_Overall

    Examples:
    ---------
    >>> scorer = ElectrodeResponseScorer(df_all, './output')
    >>> scorer.calculate_scores().create_visualizations()
    >>> top_10 = scorer.scores_df.head(10)
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
        metrics_weights : dict, optional
            각 metric의 가중치. 기본값:
            {
                'number_of_spikes': 0.4,
                'mean_firing_rate_hz': 0.3,
                'burst_frequency_hz': 0.3
            }

        Returns:
        --------
        self : ElectrodeResponseScorer
            메서드 체이닝을 위해 self 반환
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

        # Electrode별로 처리
        for electrode_id in self.df_all['Electrode_ID'].unique():
            electrode_data = self.df_all[self.df_all['Electrode_ID'] == electrode_id]

            # Well, LIGHT_CODE 정보
            well = electrode_data['Well'].iloc[0]
            light_code = electrode_data['LIGHT_CODE'].iloc[0] if 'LIGHT_CODE' in electrode_data.columns else 'UNKNOWN'

            metric_ratios = {}
            metric_base_vals = {}
            metric_stim_vals = {}

            # 각 metric별 BASE/STIM ratio 계산
            for metric in available_metrics:
                metric_data = electrode_data[electrode_data['Metric'] == metric]

                base_data = metric_data[metric_data['BASE_STIM'] == 'BASE']
                stim_data = metric_data[metric_data['BASE_STIM'] == 'STIM']

                if not base_data.empty and not stim_data.empty:
                    base_val = base_data['Value'].mean()
                    stim_val = stim_data['Value'].mean()

                    # Ratio 계산 (STIM / BASE)
                    eps = 1e-6
                    ratio = (stim_val + eps) / (base_val + eps)

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
        """
        Score 시각화 생성

        생성되는 시각화:
        1. Well별 electrode score bargraph
        2. 전체 상위 30개 electrode
        3. Score 분포 (histogram + boxplot)
        4. Metric ratios 히트맵

        Returns:
        --------
        self : ElectrodeResponseScorer
            메서드 체이닝을 위해 self 반환
        """
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
        """Well별 electrode score bargraph"""
        wells = sorted(self.scores_df['Well'].unique())

        for well in wells:
            well_data = self.scores_df[self.scores_df['Well'] == well].copy()
            well_data = well_data.sort_values('Response_Score', ascending=False)

            if well_data.empty:
                continue

            fig, ax = plt.subplots(figsize=(max(12, len(well_data)*0.5), 6))

            x_pos = np.arange(len(well_data))

            # Color gradient (높은 score = 진한 초록색)
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
            ax.set_title(f'Electrode Light Response Scores - Well {well}\n'
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

    def get_top_electrodes(self, n: int = 10, by_well: bool = False):
        """
        상위 electrode 가져오기

        Parameters:
        -----------
        n : int
            가져올 electrode 개수
        by_well : bool
            True면 각 well별 상위 n개, False면 전체 상위 n개

        Returns:
        --------
        pd.DataFrame
            상위 electrode 데이터
        """
        if self.scores_df is None or self.scores_df.empty:
            return pd.DataFrame()

        if by_well:
            return (self.scores_df.groupby('Well')
                    .apply(lambda x: x.nlargest(n, 'Response_Score'))
                    .reset_index(drop=True))
        else:
            return self.scores_df.head(n)


# =============================================================================
# STANDALONE USAGE
# =============================================================================

if __name__ == "__main__":
    """
    독립 실행 예시
    """
    import sys

    if len(sys.argv) < 2:
        print("Usage: python electrode_response_scorer.py <input_csv_or_parquet> [output_dir]")
        print("\nExample:")
        print("  python electrode_response_scorer.py electrode_all_long.csv ./results")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else './electrode_scores_output'

    print("="*80)
    print("ELECTRODE RESPONSE SCORER")
    print("="*80)
    print(f"Input: {input_file}")
    print(f"Output: {output_dir}")
    print("="*80)

    # 데이터 로드
    print("\nLoading data...")
    if input_file.endswith('.parquet'):
        df_all = pd.read_parquet(input_file)
    else:
        df_all = pd.read_csv(input_file)

    print(f"  ✓ Loaded {len(df_all)} rows")
    print(f"  ✓ Electrodes: {df_all['Electrode_ID'].nunique()}")
    print(f"  ✓ Wells: {df_all['Well'].nunique()}")

    # Scorer 실행
    scorer = ElectrodeResponseScorer(df_all, output_dir)
    scorer.calculate_scores().create_visualizations()

    # 상위 10개 출력
    print("\n" + "="*80)
    print("TOP 10 ELECTRODES")
    print("="*80)
    top10 = scorer.get_top_electrodes(10)
    print(top10[['Rank_Overall', 'Electrode_ID', 'Well', 'Response_Score']].to_string(index=False))

    print("\n" + "="*80)
    print("✓ COMPLETE!")
    print("="*80)
    print(f"Results saved to: {output_dir}")
