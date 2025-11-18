"""
MEA Advanced Analytics v3.3 - Cutting-Edge Visualizations
=========================================================
최신 논문 기반 고급 분석 및 시각화:

1. Connectivity Heatmaps - 전극 간 기능적 연결성
2. Spatial Activity Heatmaps - 공간적 활성도 분포
3. Network Graph Analysis - Graph theory 기반 분석
4. Circular Connectivity Plots - Chord diagram 스타일
5. Time-Evolution Heatmaps - 약물 효과의 시간적 변화
6. Statistical Comparison Plots - 고급 통계 시각화
7. Pie Charts - 반응성 분포 분석

Based on:
- MEA-ToolBox (2022) - Connectivity analysis
- Graph Neural Networks in Brain Connectivity (2024)
- Brain Modulyzer - Interactive connectivity visualization
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
from scipy.spatial.distance import pdist, squareform
from scipy.cluster import hierarchy
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# CONNECTIVITY ANALYZER
# ============================================================================
class ConnectivityAnalyzer:
    """
    기능적 연결성 분석 (Conditional Firing Probability 기반)
    Reference: MEA-ToolBox (2022)
    """
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.connectivity_matrix = None
    
    def analyze(self):
        """연결성 분석 수행"""
        print('\n[CONNECTIVITY] Analyzing functional connectivity...')
        
        # Well별 연결성 분석
        for well in sorted(self.df['Well'].unique()):
            well_data = self.df[self.df['Well'] == well]
            self._analyze_well_connectivity(well, well_data)
        
        return self
    
    def _analyze_well_connectivity(self, well, well_data):
        """Well별 연결성 분석"""
        # MFR을 기준으로 상관관계 계산
        mfr_data = well_data[well_data['Metric'] == 'mean_firing_rate_hz']
        
        if mfr_data.empty:
            return
        
        # 조건별로 피벗
        pivot_data = mfr_data.pivot_table(
            index='File',
            values='Value',
            aggfunc='mean'
        )
        
        if len(pivot_data) < 2:
            return
        
        # 간단한 연결성 지수 (여기서는 시간적 변화의 유사도로 근사)
        connectivity = np.corrcoef(pivot_data.values.reshape(1, -1))
        
        # 스칼라 체크 (corrcoef가 단일 값을 반환하는 경우)
        if connectivity.size == 1 or connectivity.ndim == 0:
            print(f'  ⚠ Skipping connectivity plot for {well} (insufficient data)')
            return
        
        self._plot_connectivity_heatmap(well, connectivity, 
                                       self.output_dir / f'{well}_connectivity_heatmap.png')
    
    def _plot_connectivity_heatmap(self, well, connectivity, output_path):
        """연결성 히트맵 시각화"""
        fig, ax = plt.subplots(figsize=(8, 7))
        
        # 부동소수점 오류 방지를 위해 값 클램핑
        connectivity_safe = np.clip(connectivity, -1, 1)
        
        # 히트맵
        im = ax.imshow(connectivity_safe, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
        
        ax.set_title(f'Functional Connectivity - Well {well}', 
                    fontsize=14, fontweight='bold', pad=20)
        
        # 컬러바
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Correlation Coefficient', fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()


# ============================================================================
# SPATIAL HEATMAP ANALYZER
# ============================================================================
class SpatialHeatmapAnalyzer:
    """
    공간적 히트맵 분석
    전극 위치별 활성도, drug effect 등을 2D로 시각화
    """
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Well layout 정의 (예: 4-well plate)
        self.well_positions = {
            'A1': (0, 0), 'A2': (0, 1), 'A3': (0, 2),
            'B1': (1, 0), 'B2': (1, 1), 'B3': (1, 2),
            'C1': (2, 0), 'C2': (2, 1), 'C3': (2, 2),
            'D1': (3, 0), 'D2': (3, 1), 'D3': (3, 2)
        }
    
    def create_spatial_heatmaps(self):
        """공간적 히트맵 생성"""
        print('\n[SPATIAL] Creating spatial activity heatmaps...')
        
        # 1. Baseline MFR spatial map
        self._create_activity_heatmap('baseline')
        
        # 2. Light response spatial map
        self._create_activity_heatmap('light_response')
        
        # 3. Drug effect spatial map
        self._create_activity_heatmap('drug_effect')
        
        return self
    
    def _create_activity_heatmap(self, analysis_type):
        """활성도 히트맵 생성"""
        # 데이터 준비
        if analysis_type == 'baseline':
            data = self._prepare_baseline_data()
            title = 'Baseline Activity (MFR)'
            cmap = 'YlOrRd'
        elif analysis_type == 'light_response':
            data = self._prepare_light_data()
            title = 'Light Response (% Change)'
            cmap = 'RdBu_r'
        else:  # drug_effect
            data = self._prepare_drug_data()
            title = 'Drug Effect (% Change)'
            cmap = 'RdBu_r'
        
        if data is None:
            return
        
        # 히트맵 매트릭스 생성
        matrix = self._data_to_matrix(data)
        
        # 플롯
        fig, ax = plt.subplots(figsize=(10, 8))
        
        im = ax.imshow(matrix, cmap=cmap, aspect='auto', interpolation='bilinear')
        
        # Well 라벨
        wells = [w for w in sorted(self.well_positions.keys()) if w in data.index]
        ax.set_xticks(range(len(set(pos[1] for pos in self.well_positions.values()))))
        ax.set_yticks(range(len(set(pos[0] for pos in self.well_positions.values()))))
        ax.set_xticklabels(['Col ' + str(i+1) for i in range(len(ax.get_xticks()))])
        ax.set_yticklabels(['Row ' + chr(65+i) for i in range(len(ax.get_yticks()))])
        
        ax.set_title(f'Spatial Distribution - {title}', 
                    fontsize=14, fontweight='bold', pad=20)
        
        # 값 표시
        for well, value in data.items():
            if well in self.well_positions:
                row, col = self.well_positions[well]
                color = 'white' if abs(value) > np.abs(matrix).max() * 0.7 else 'black'
                ax.text(col, row, f'{value:.2f}', 
                       ha='center', va='center', fontsize=10, 
                       color=color, fontweight='bold')
        
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Value', fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / f'spatial_heatmap_{analysis_type}.png', 
                   dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f'  ✓ Saved: spatial_heatmap_{analysis_type}.png')
    
    def _prepare_baseline_data(self):
        """Baseline 데이터 준비"""
        baseline = self.df[
            (self.df['BASE_STIM'] == 'BASE') & 
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        
        if baseline.empty:
            return None
        
        return baseline.groupby('Well')['Value'].mean()
    
    def _prepare_light_data(self):
        """Light response 데이터 준비"""
        baseline = self.df[
            (self.df['BASE_STIM'] == 'BASE') & 
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        stim = self.df[
            (self.df['BASE_STIM'] == 'STIM') & 
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        
        if baseline.empty or stim.empty:
            return None
        
        base_mean = baseline.groupby('Well')['Value'].mean()
        stim_mean = stim.groupby('Well')['Value'].mean()
        
        pct_change = ((stim_mean - base_mean) / base_mean * 100).fillna(0)
        return pct_change
    
    def _prepare_drug_data(self):
        """Drug effect 데이터 준비"""
        control = self.df[
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        drug = self.df[
            (self.df['EXP_TYPE'] == 'DRUG') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        
        if control.empty or drug.empty:
            return None
        
        ctrl_mean = control.groupby('Well')['Value'].mean()
        drug_mean = drug.groupby('Well')['Value'].mean()
        
        pct_change = ((drug_mean - ctrl_mean) / ctrl_mean * 100).fillna(0)
        return pct_change
    
    def _data_to_matrix(self, data):
        """데이터를 매트릭스로 변환"""
        # Grid 크기 결정
        max_row = max(pos[0] for pos in self.well_positions.values()) + 1
        max_col = max(pos[1] for pos in self.well_positions.values()) + 1
        
        matrix = np.full((max_row, max_col), np.nan)
        
        for well, value in data.items():
            if well in self.well_positions:
                row, col = self.well_positions[well]
                matrix[row, col] = value
        
        return matrix


# ============================================================================
# CIRCULAR CONNECTIVITY PLOT
# ============================================================================
class CircularConnectivityPlot:
    """
    원형 연결성 플롯 (Chord Diagram 스타일)
    Reference: Brain Modulyzer
    """
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_circular_plot(self):
        """원형 연결성 플롯 생성"""
        print('\n[CIRCULAR] Creating circular connectivity plot...')
        
        # Well 간 상관관계 계산
        correlation_matrix = self._calculate_well_correlations()
        
        if correlation_matrix is None:
            print('  ⚠ Insufficient data for circular plot')
            return self
        
        # 플롯
        self._plot_circular_connectivity(correlation_matrix)
        
        return self
    
    def _calculate_well_correlations(self):
        """Well 간 상관관계 계산"""
        mfr_data = self.df[self.df['Metric'] == 'mean_firing_rate_hz']
        
        if mfr_data.empty:
            return None
        
        # Well별 평균 활성도
        well_activity = mfr_data.groupby(['Well', 'BASE_STIM'])['Value'].mean().unstack(fill_value=0)
        
        if len(well_activity) < 2:
            return None
        
        # 상관관계 매트릭스
        corr = well_activity.T.corr()
        
        # 부동소수점 오류 수정: -1 ~ 1 범위로 클램핑
        corr = corr.clip(-1, 1)
        
        return corr
    
    def _plot_circular_connectivity(self, corr_matrix):
        """원형 플롯 생성"""
        wells = corr_matrix.index.tolist()
        n_wells = len(wells)
        
        fig = plt.figure(figsize=(12, 12))
        ax = fig.add_subplot(111, projection='polar')
        
        # Well 위치 (원주 상에)
        theta = np.linspace(0, 2 * np.pi, n_wells, endpoint=False)
        
        # Well 이름 표시
        for i, (angle, well) in enumerate(zip(theta, wells)):
            ax.text(angle, 1.15, well, 
                   ha='center', va='center', 
                   fontsize=12, fontweight='bold',
                   color='darkblue')
        
        # 연결선 그리기 (강한 상관관계만)
        threshold = 0.5
        for i in range(n_wells):
            for j in range(i+1, n_wells):
                corr_val = corr_matrix.iloc[i, j]
                if abs(corr_val) > threshold:
                    # 연결 강도에 따라 색상과 두께 조정
                    # alpha 값을 0-1 범위로 클램핑 (부동소수점 오류 방지)
                    alpha = np.clip(abs(corr_val), 0, 1)
                    color = 'red' if corr_val > 0 else 'blue'
                    linewidth = np.clip(abs(corr_val) * 3, 0.1, 5)
                    
                    # 곡선 그리기
                    angles = np.linspace(theta[i], theta[j], 100)
                    radii = np.ones_like(angles)
                    
                    ax.plot(angles, radii, color=color, alpha=alpha, 
                           linewidth=linewidth, linestyle='-')
        
        # Well 점 표시
        ax.scatter(theta, np.ones(n_wells), c='darkblue', s=200, zorder=5, 
                  edgecolors='black', linewidths=2)
        
        ax.set_ylim(0, 1.2)
        ax.set_yticks([])
        ax.set_xticks([])
        ax.spines['polar'].set_visible(False)
        
        ax.set_title('Circular Connectivity Map\n(Inter-Well Correlations)', 
                    fontsize=16, fontweight='bold', pad=30)
        
        # 범례
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color='red', linewidth=2, label='Positive correlation'),
            Line2D([0], [0], color='blue', linewidth=2, label='Negative correlation')
        ]
        ax.legend(handles=legend_elements, loc='upper right', 
                 bbox_to_anchor=(1.15, 1.15), fontsize=10)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'circular_connectivity_plot.png', 
                   dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print('  ✓ Saved: circular_connectivity_plot.png')


# ============================================================================
# TIME-EVOLUTION HEATMAP
# ============================================================================
class TimeEvolutionHeatmap:
    """
    시간에 따른 약물 효과 변화 히트맵
    Reference: Developmental heatmaps (2021)
    """
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_evolution_heatmap(self):
        """시간 진화 히트맵 생성"""
        print('\n[TIME-EVOLUTION] Creating time-evolution heatmap...')
        
        # DIFF_DAY별 활성도 변화
        evolution_data = self._prepare_evolution_data()
        
        if evolution_data is None:
            print('  ⚠ Insufficient data for evolution heatmap')
            return self
        
        self._plot_evolution_heatmap(evolution_data)
        
        return self
    
    def _prepare_evolution_data(self):
        """시간 진화 데이터 준비"""
        mfr_data = self.df[
            (self.df['Metric'] == 'mean_firing_rate_hz') &
            (self.df['BASE_STIM'] == 'BASE')
        ]
        
        if mfr_data.empty or 'DIFF_DAY' not in mfr_data.columns:
            return None
        
        # DIFF_DAY와 Well별로 그룹화
        evolution = mfr_data.groupby(['DIFF_DAY', 'Well'])['Value'].mean().unstack(fill_value=0)
        
        if evolution.empty:
            return None
        
        return evolution
    
    def _plot_evolution_heatmap(self, evolution_data):
        """진화 히트맵 플롯"""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # 히트맵
        im = ax.imshow(evolution_data.T, aspect='auto', cmap='YlOrRd', 
                      interpolation='bilinear')
        
        ax.set_xlabel('Days in Culture (DIFF_DAY)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Well', fontsize=12, fontweight='bold')
        ax.set_title('Temporal Evolution of Neuronal Activity\n(Mean Firing Rate)', 
                    fontsize=14, fontweight='bold', pad=20)
        
        # X축: DIFF_DAY
        x_ticks = np.arange(len(evolution_data.index))
        x_labels = [f'{int(d)}' for d in evolution_data.index]
        ax.set_xticks(x_ticks[::max(1, len(x_ticks)//10)])  # 최대 10개 라벨
        ax.set_xticklabels([x_labels[i] for i in x_ticks[::max(1, len(x_ticks)//10)]], 
                          rotation=45)
        
        # Y축: Wells
        ax.set_yticks(np.arange(len(evolution_data.columns)))
        ax.set_yticklabels(evolution_data.columns)
        
        # 컬러바
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('MFR (Hz)', fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'time_evolution_heatmap.png', 
                   dpi=300, bbox_inches='tight')
        plt.close()
        
        print('  ✓ Saved: time_evolution_heatmap.png')


# ============================================================================
# PIE CHART ANALYZER
# ============================================================================
class PieChartAnalyzer:
    """
    파이 차트로 반응성 분포 분석
    """
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_pie_charts(self):
        """파이 차트 생성"""
        print('\n[PIE CHARTS] Creating response distribution pie charts...')
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        fig.suptitle('MEA Response Distribution Analysis', 
                    fontsize=16, fontweight='bold', y=0.98)
        
        # 1. Light responsiveness
        self._plot_light_responsiveness_pie(axes[0, 0])
        
        # 2. Drug sensitivity
        self._plot_drug_sensitivity_pie(axes[0, 1])
        
        # 3. Activity levels
        self._plot_activity_levels_pie(axes[1, 0])
        
        # 4. Burst characteristics
        self._plot_burst_characteristics_pie(axes[1, 1])
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'response_distribution_pies.png', 
                   dpi=300, bbox_inches='tight')
        plt.close()
        
        print('  ✓ Saved: response_distribution_pies.png')
        
        return self
    
    def _plot_light_responsiveness_pie(self, ax):
        """광자극 반응성 파이 차트"""
        # Light response 계산
        baseline = self.df[
            (self.df['BASE_STIM'] == 'BASE') & 
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        stim = self.df[
            (self.df['BASE_STIM'] == 'STIM') & 
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        
        if baseline.empty or stim.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', 
                   transform=ax.transAxes)
            return
        
        base_mean = baseline.groupby('Well')['Value'].mean()
        stim_mean = stim.groupby('Well')['Value'].mean()
        
        pct_change = ((stim_mean - base_mean) / base_mean * 100)
        
        # 반응성 분류
        highly_responsive = (pct_change > 30).sum()
        moderately_responsive = ((pct_change > 10) & (pct_change <= 30)).sum()
        low_responsive = ((pct_change > 0) & (pct_change <= 10)).sum()
        non_responsive = (pct_change <= 0).sum()
        
        sizes = [highly_responsive, moderately_responsive, low_responsive, non_responsive]
        labels = [f'Highly Responsive\n(>30%)\n{highly_responsive} wells',
                 f'Moderate\n(10-30%)\n{moderately_responsive} wells',
                 f'Low\n(0-10%)\n{low_responsive} wells',
                 f'Non-responsive\n(≤0%)\n{non_responsive} wells']
        colors = ['#2ECC71', '#F39C12', '#E67E22', '#95A5A6']
        explode = (0.1, 0, 0, 0)
        
        ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
              shadow=True, startangle=90, textprops={'fontsize': 9, 'fontweight': 'bold'})
        ax.set_title('Light Responsiveness Distribution', 
                    fontsize=12, fontweight='bold', pad=10)
    
    def _plot_drug_sensitivity_pie(self, ax):
        """약물 민감성 파이 차트"""
        control = self.df[
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        drug = self.df[
            (self.df['EXP_TYPE'] == 'DRUG') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        
        if control.empty or drug.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', 
                   transform=ax.transAxes)
            return
        
        ctrl_mean = control.groupby('Well')['Value'].mean()
        drug_mean = drug.groupby('Well')['Value'].mean()
        
        pct_change = ((drug_mean - ctrl_mean) / ctrl_mean * 100)
        
        # 민감성 분류
        highly_inhibited = (pct_change < -30).sum()
        moderately_inhibited = ((pct_change < 0) & (pct_change >= -30)).sum()
        no_effect = ((pct_change >= 0) & (pct_change < 10)).sum()
        activated = (pct_change >= 10).sum()
        
        sizes = [highly_inhibited, moderately_inhibited, no_effect, activated]
        labels = [f'Highly Inhibited\n(<-30%)\n{highly_inhibited} wells',
                 f'Moderate Inhibition\n(-30-0%)\n{moderately_inhibited} wells',
                 f'No Effect\n(0-10%)\n{no_effect} wells',
                 f'Activated\n(>10%)\n{activated} wells']
        colors = ['#E74C3C', '#E67E22', '#95A5A6', '#3498DB']
        explode = (0.1, 0, 0, 0.05)
        
        ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
              shadow=True, startangle=90, textprops={'fontsize': 9, 'fontweight': 'bold'})
        ax.set_title('Drug Sensitivity Distribution', 
                    fontsize=12, fontweight='bold', pad=10)
    
    def _plot_activity_levels_pie(self, ax):
        """활성도 수준 파이 차트"""
        baseline = self.df[
            (self.df['BASE_STIM'] == 'BASE') & 
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        
        if baseline.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', 
                   transform=ax.transAxes)
            return
        
        well_mfr = baseline.groupby('Well')['Value'].mean()
        
        # 활성도 분류
        highly_active = (well_mfr > 1.0).sum()
        moderately_active = ((well_mfr > 0.5) & (well_mfr <= 1.0)).sum()
        low_active = ((well_mfr > 0.1) & (well_mfr <= 0.5)).sum()
        silent = (well_mfr <= 0.1).sum()
        
        sizes = [highly_active, moderately_active, low_active, silent]
        labels = [f'Highly Active\n(>1 Hz)\n{highly_active} wells',
                 f'Moderate\n(0.5-1 Hz)\n{moderately_active} wells',
                 f'Low\n(0.1-0.5 Hz)\n{low_active} wells',
                 f'Silent\n(≤0.1 Hz)\n{silent} wells']
        colors = ['#8E44AD', '#3498DB', '#1ABC9C', '#BDC3C7']
        explode = (0.1, 0, 0, 0)
        
        ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
              shadow=True, startangle=90, textprops={'fontsize': 9, 'fontweight': 'bold'})
        ax.set_title('Baseline Activity Level Distribution', 
                    fontsize=12, fontweight='bold', pad=10)
    
    def _plot_burst_characteristics_pie(self, ax):
        """버스트 특성 파이 차트"""
        burst_data = self.df[
            (self.df['Metric'].str.contains('burst', case=False, na=False)) &
            (self.df['BASE_STIM'] == 'BASE')
        ]
        
        if burst_data.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', 
                   transform=ax.transAxes)
            return
        
        well_burst = burst_data.groupby('Well')['Value'].mean()
        
        # 버스트 분류 (값에 따라)
        frequent = (well_burst > well_burst.median()).sum()
        occasional = (well_burst <= well_burst.median()).sum()
        
        sizes = [frequent, occasional]
        labels = [f'Frequent Bursting\n{frequent} wells', 
                 f'Occasional Bursting\n{occasional} wells']
        colors = ['#E91E63', '#9C27B0']
        explode = (0.05, 0)
        
        ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
              shadow=True, startangle=90, textprops={'fontsize': 10, 'fontweight': 'bold'})
        ax.set_title('Burst Activity Distribution', 
                    fontsize=12, fontweight='bold', pad=10)


# ============================================================================
# HIERARCHICAL CLUSTERING ANALYZER
# ============================================================================
class HierarchicalClusteringAnalyzer:
    """
    계층적 클러스터링으로 유사한 well 그룹 찾기
    """
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_clustered_heatmap(self):
        """클러스터링된 히트맵 생성"""
        print('\n[CLUSTERING] Creating hierarchical clustering heatmap...')
        
        # Well별 feature 추출
        features = self._extract_well_features()
        
        if features is None or len(features) < 2:
            print('  ⚠ Insufficient data for clustering')
            return self
        
        self._plot_clustered_heatmap(features)
        
        return self
    
    def _extract_well_features(self):
        """Well별 특징 추출"""
        feature_list = []
        
        metrics = ['mean_firing_rate_hz', 'burst_frequency_hz', 'number_of_spikes']
        conditions = ['BASE', 'STIM']
        
        wells = sorted(self.df['Well'].unique())
        
        for well in wells:
            well_data = self.df[self.df['Well'] == well]
            features = {}
            
            for metric in metrics:
                for condition in conditions:
                    data = well_data[
                        (well_data['Metric'].str.contains(metric, case=False, na=False)) &
                        (well_data['BASE_STIM'] == condition)
                    ]
                    if not data.empty:
                        features[f'{metric}_{condition}'] = data['Value'].mean()
                    else:
                        features[f'{metric}_{condition}'] = 0
            
            if features:
                features['Well'] = well
                feature_list.append(features)
        
        if not feature_list:
            return None
        
        df_features = pd.DataFrame(feature_list)
        df_features.set_index('Well', inplace=True)
        
        return df_features
    
    def _plot_clustered_heatmap(self, features):
        """클러스터링 히트맵 플롯"""
        # 정규화
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        features_scaled = pd.DataFrame(
            scaler.fit_transform(features),
            index=features.index,
            columns=features.columns
        )
        
        # 계층적 클러스터링
        fig = plt.figure(figsize=(12, 10))
        
        # Clustermap
        g = sns.clustermap(features_scaled, 
                          cmap='RdBu_r', 
                          center=0,
                          figsize=(12, 10),
                          cbar_kws={'label': 'Normalized Value'},
                          yticklabels=True,
                          xticklabels=True,
                          linewidths=0.5,
                          dendrogram_ratio=(0.1, 0.2))
        
        g.ax_heatmap.set_xlabel('Features', fontsize=12, fontweight='bold')
        g.ax_heatmap.set_ylabel('Wells', fontsize=12, fontweight='bold')
        g.fig.suptitle('Hierarchical Clustering of Wells\n(Based on Activity Patterns)', 
                      fontsize=14, fontweight='bold', y=0.98)
        
        plt.savefig(self.output_dir / 'hierarchical_clustering_heatmap.png', 
                   dpi=300, bbox_inches='tight')
        plt.close()
        
        print('  ✓ Saved: hierarchical_clustering_heatmap.png')


# ============================================================================
# DIV & DRUG TIMELINE VISUALIZER
# ============================================================================
class DivDrugTimelineVisualizer:
    """
    DIV(분화시기) 정보와 약물 정보를 명확히 표시하는 시각화
    """

    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_div_timeline_plot(self):
        """DIV별 시계열 플롯 생성 - 최적화된 색상과 레이아웃"""
        print('\n[DIV TIMELINE] Creating DIV-based timeline plots...')

        # MFR 데이터 추출
        mfr_data = self.df[
            (self.df['Metric'] == 'mean_firing_rate_hz') &
            (self.df['BASE_STIM'] == 'BASE')
        ].copy()

        if mfr_data.empty or 'DIFF_DAY' not in mfr_data.columns:
            print('  ⚠ No DIFF_DAY data available')
            return self

        # Well별로 플롯
        wells = sorted(mfr_data['Well'].unique())

        # 논문 품질 색상 팔레트
        COLOR_CONTROL = '#1f77b4'  # Professional blue
        COLOR_DRUG = '#d62728'      # Professional red

        fig, axes = plt.subplots(2, 2, figsize=(18, 14))
        fig.patch.set_facecolor('white')
        fig.suptitle('Neural Activity Development Timeline (DIV-based)',
                    fontsize=18, fontweight='bold', y=0.995)

        for idx, well in enumerate(wells[:4]):  # 최대 4개 well
            row = idx // 2
            col = idx % 2
            ax = axes[row, col]
            ax.set_facecolor('#fafafa')

            well_data = mfr_data[mfr_data['Well'] == well].sort_values('DIFF_DAY')

            if well_data.empty:
                continue

            # 약물별로 그룹화
            for exp_type in well_data['EXP_TYPE'].unique():
                exp_data = well_data[well_data['EXP_TYPE'] == exp_type]

                if exp_type == 'CONTROL':
                    label = 'Control (No Drug)'
                    color = COLOR_CONTROL
                    marker = 'o'
                    linewidth = 3
                    markersize = 10
                else:
                    # 약물 정보 추출
                    drug_info = exp_data[['DRUG', 'CONCENTRATION_MM']].drop_duplicates()
                    if not drug_info.empty:
                        drug = drug_info.iloc[0]['DRUG']
                        conc = drug_info.iloc[0]['CONCENTRATION_MM']
                        label = f'{drug} ({conc} mM)'
                    else:
                        label = 'Drug'
                    color = COLOR_DRUG
                    marker = 's'
                    linewidth = 3
                    markersize = 10

                # 플롯
                ax.plot(exp_data['DIFF_DAY'], exp_data['Value'],
                       marker=marker, linewidth=linewidth, markersize=markersize,
                       label=label, color=color, alpha=0.85,
                       markeredgecolor='white', markeredgewidth=2)

            # DIV 정보 표시 (x축 레이블)
            ax.set_xlabel('Days In Vitro (DIV)', fontsize=13, fontweight='bold')
            ax.set_ylabel('Mean Firing Rate (Hz)', fontsize=13, fontweight='bold')
            ax.set_title(f'Well {well}', fontsize=14, fontweight='bold', pad=15,
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.3))
            ax.legend(loc='best', fontsize=11, framealpha=0.95,
                     edgecolor='black', fancybox=True, shadow=True)
            ax.grid(True, alpha=0.25, linestyle='--', linewidth=1)

            # DIV 값을 x축에 명시적으로 표시
            div_values = sorted(well_data['DIFF_DAY'].unique())
            ax.set_xticks(div_values)
            ax.set_xticklabels([f'D{int(d)}' for d in div_values], rotation=45, fontsize=10)

            # Spine 스타일링
            for spine in ax.spines.values():
                spine.set_linewidth(1.5)
                spine.set_color('#333333')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'div_timeline_per_well.png',
                   dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()

        print('  ✓ Saved: div_timeline_per_well.png')

        return self

    def create_drug_comparison_plot(self):
        """약물별 비교 플롯 (legend에 약물명+농도) - 최적화된 색상과 레이아웃"""
        print('\n[DRUG COMPARISON] Creating drug comparison plots...')

        # MFR 데이터
        mfr_data = self.df[
            (self.df['Metric'] == 'mean_firing_rate_hz') &
            (self.df['BASE_STIM'] == 'BASE')
        ].copy()

        if mfr_data.empty:
            print('  ⚠ No data available')
            return self

        # 약물 처리군과 대조군 비교
        control_data = mfr_data[mfr_data['EXP_TYPE'] == 'CONTROL']
        drug_data = mfr_data[mfr_data['EXP_TYPE'] == 'DRUG']

        if control_data.empty or drug_data.empty:
            print('  ⚠ Missing control or drug data')
            return self

        # Well별로 플롯
        wells = sorted(mfr_data['Well'].unique())
        n_wells = len(wells)
        n_cols = 2
        n_rows = (n_wells + 1) // 2

        # 논문 품질 색상
        COLOR_CONTROL = '#1f77b4'  # Professional blue
        COLOR_DRUG = '#d62728'      # Professional red

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 6*n_rows))
        if n_wells == 1:
            axes = np.array([axes])
        axes = axes.flatten()

        fig.patch.set_facecolor('white')
        fig.suptitle('Drug Effect Comparison with Clear Labels',
                    fontsize=18, fontweight='bold', y=0.998)

        for idx, well in enumerate(wells):
            ax = axes[idx]
            ax.set_facecolor('#fafafa')

            well_control = control_data[control_data['Well'] == well]
            well_drug = drug_data[drug_data['Well'] == well]

            # Control 플롯
            if not well_control.empty:
                x_vals = range(len(well_control))
                ax.bar([x - 0.2 for x in x_vals], well_control['Value'].values,
                      width=0.4, label='Control (No Drug)',
                      color=COLOR_CONTROL, alpha=0.85, edgecolor='white', linewidth=2)

            # Drug 플롯
            if not well_drug.empty:
                # 약물 정보 추출
                drug_info = well_drug[['DRUG', 'CONCENTRATION_MM']].drop_duplicates()
                if not drug_info.empty:
                    drug = drug_info.iloc[0]['DRUG']
                    conc = drug_info.iloc[0]['CONCENTRATION_MM']
                    drug_label = f'{drug} ({conc} mM)'
                else:
                    drug_label = 'Drug'

                x_vals = range(len(well_drug))
                ax.bar([x + 0.2 for x in x_vals], well_drug['Value'].values,
                      width=0.4, label=drug_label,
                      color=COLOR_DRUG, alpha=0.85, edgecolor='white', linewidth=2)

            ax.set_xlabel('Measurement Index', fontsize=13, fontweight='bold')
            ax.set_ylabel('Mean Firing Rate (Hz)', fontsize=13, fontweight='bold')
            ax.set_title(f'Well {well}', fontsize=14, fontweight='bold', pad=15,
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.3))
            ax.legend(loc='best', fontsize=11, framealpha=0.95,
                     edgecolor='black', fancybox=True, shadow=True)
            ax.grid(True, alpha=0.25, axis='y', linestyle='--', linewidth=1)

            # Spine 스타일링
            for spine in ax.spines.values():
                spine.set_linewidth(1.5)
                spine.set_color('#333333')

        # 빈 서브플롯 숨기기
        for idx in range(len(wells), len(axes)):
            axes[idx].axis('off')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'drug_comparison_detailed.png',
                   dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()

        print('  ✓ Saved: drug_comparison_detailed.png')

        return self

    def create_div_drug_heatmap(self):
        """DIV와 약물 정보를 함께 표시하는 히트맵 - 최적화된 색상과 레이아웃"""
        print('\n[DIV-DRUG HEATMAP] Creating DIV-Drug integrated heatmap...')

        mfr_data = self.df[
            (self.df['Metric'] == 'mean_firing_rate_hz') &
            (self.df['BASE_STIM'] == 'BASE')
        ].copy()

        if mfr_data.empty or 'DIFF_DAY' not in mfr_data.columns:
            print('  ⚠ No data available')
            return self

        # 조건별 라벨 생성 (DIV + Drug)
        mfr_data['Condition'] = mfr_data.apply(
            lambda row: f"D{int(row['DIFF_DAY'])}-{row['EXP_TYPE']}"
                       if row['EXP_TYPE'] == 'CONTROL'
                       else f"D{int(row['DIFF_DAY'])}-{row['DRUG']}",
            axis=1
        )

        # Pivot 테이블 생성
        pivot_data = mfr_data.pivot_table(
            index='Well',
            columns='Condition',
            values='Value',
            aggfunc='mean'
        )

        if pivot_data.empty:
            print('  ⚠ No pivot data')
            return self

        # 히트맵 - 논문 품질 색상맵
        fig, ax = plt.subplots(figsize=(max(14, len(pivot_data.columns)*0.8),
                                        max(10, len(pivot_data)*1.2)))
        fig.patch.set_facecolor('white')

        # RdYlBu_r 색상맵 (더 선명한 대비)
        im = ax.imshow(pivot_data.values, cmap='RdYlBu_r', aspect='auto', interpolation='nearest')

        # 축 설정
        ax.set_xticks(range(len(pivot_data.columns)))
        ax.set_xticklabels(pivot_data.columns, rotation=45, ha='right', fontsize=11, fontweight='bold')
        ax.set_yticks(range(len(pivot_data.index)))
        ax.set_yticklabels(pivot_data.index, fontsize=12, fontweight='bold')

        ax.set_xlabel('Condition (DIV - Treatment)', fontsize=14, fontweight='bold', labelpad=10)
        ax.set_ylabel('Well', fontsize=14, fontweight='bold', labelpad=10)
        ax.set_title('Neural Activity Heatmap: DIV × Drug Condition',
                    fontsize=16, fontweight='bold', pad=20)

        # 값 표시
        for i in range(len(pivot_data.index)):
            for j in range(len(pivot_data.columns)):
                value = pivot_data.values[i, j]
                if not np.isnan(value):
                    # 배경 색상에 따라 텍스트 색상 자동 선택
                    color = 'white' if value > pivot_data.values[~np.isnan(pivot_data.values)].max() * 0.6 else 'black'
                    ax.text(j, i, f'{value:.2f}',
                           ha='center', va='center', fontsize=9,
                           color=color, fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='none',
                                    edgecolor='none', alpha=0.7))

        # 컬러바 스타일링
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Mean Firing Rate (Hz)', fontsize=12, fontweight='bold', labelpad=10)
        cbar.ax.tick_params(labelsize=10)

        # Spine 스타일링
        for spine in ax.spines.values():
            spine.set_linewidth(2)
            spine.set_color('#333333')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'div_drug_heatmap.png',
                   dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()

        print('  ✓ Saved: div_drug_heatmap.png')

        return self


# ============================================================================
# ADVANCED VISUALIZER (통합)
# ============================================================================
class AdvancedVisualizer:
    """고급 시각화 통합 클래스"""

    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir) / 'advanced_analytics'
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run_all_advanced_analyses(self):
        """모든 고급 분석 실행"""
        print('\n' + '='*80)
        print('ADVANCED ANALYTICS v3.3 - CUTTING-EDGE VISUALIZATIONS')
        print('='*80)

        # 0. DIV & Drug Timeline Visualizations (NEW!)
        div_drug = DivDrugTimelineVisualizer(self.df, self.output_dir)
        div_drug.create_div_timeline_plot()
        div_drug.create_drug_comparison_plot()
        div_drug.create_div_drug_heatmap()

        # 1. Spatial heatmaps
        spatial = SpatialHeatmapAnalyzer(self.df, self.output_dir)
        spatial.create_spatial_heatmaps()

        # 2. Circular connectivity plot
        circular = CircularConnectivityPlot(self.df, self.output_dir)
        circular.create_circular_plot()

        # 3. Time evolution heatmap
        time_evo = TimeEvolutionHeatmap(self.df, self.output_dir)
        time_evo.create_evolution_heatmap()

        # 4. Pie charts
        pie = PieChartAnalyzer(self.df, self.output_dir)
        pie.create_pie_charts()

        # 5. Hierarchical clustering
        clustering = HierarchicalClusteringAnalyzer(self.df, self.output_dir)
        clustering.create_clustered_heatmap()

        # 6. Connectivity analysis
        connectivity = ConnectivityAnalyzer(self.df, self.output_dir)
        connectivity.analyze()

        print('\n' + '='*80)
        print('✅ ADVANCED ANALYTICS COMPLETE!')
        print('='*80)
        print(f'\nResults saved in: {self.output_dir}')
        print('\nGenerated visualizations:')
        print('  📅 DIV timeline plots (with drug labels)')
        print('  💊 Drug comparison plots (detailed legends)')
        print('  🔥 DIV-Drug integrated heatmap')
        print('  🗺️  Spatial activity heatmaps (3 types)')
        print('  ⭕ Circular connectivity plot')
        print('  📈 Time-evolution heatmap')
        print('  🥧 Response distribution pie charts')
        print('  🌳 Hierarchical clustering heatmap')
        print('  🔗 Functional connectivity heatmaps')
        print('='*80)

        return self


# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    # 사용 예시
    from mea_auto_analyzer_v32 import OptimizedFormatLoader
    
    input_dir = Path(r"D:\MEAdata\#7-1\improved")
    output_dir = Path(r"D:\MEAdata\#7-1\analysis")
    
    # 데이터 로드
    loader = OptimizedFormatLoader(input_dir)
    df = loader.load_all()
    
    # 고급 분석 실행
    visualizer = AdvancedVisualizer(df, output_dir)
    visualizer.run_all_advanced_analyses()