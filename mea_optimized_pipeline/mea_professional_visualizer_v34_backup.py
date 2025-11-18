"""
MEA Professional Visualizer v3.4 - Nature/Cell/Science Style
============================================================
최신 high-tier journal 디자인 트렌드 반영:

Based on:
- Nature Cell Biology (2025) - Figure design checklist
- PLOS Computational Biology - Ten Simple Rules for Better Figures
- Data Visualization Best Practices 2024-2025

Key Improvements:
1. Minimal & Clean Design - 불필요한 요소 제거
2. Colorblind-Friendly Palettes - 접근성 향상
3. Professional Typography - 가독성 최적화
4. Statistical Rigor - Error bars & significance
5. Publication-Ready - Vector graphics, high DPI
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# 글로벌 스타일 설정
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
plt.rcParams['pdf.fonttype'] = 42  # TrueType fonts for PDF
plt.rcParams['ps.fonttype'] = 42
plt.rcParams['svg.fonttype'] = 'none'  # Text as text in SVG


# ============================================================================
# COLOR PALETTES - Colorblind-Friendly
# ============================================================================
class ScientificPalette:
    """
    과학 논문용 색상 팔레트 (Colorblind-safe)
    Based on ColorBrewer, Wong 2011, and Nature guidelines
    """
    
    # Categorical colors (최대 8개 구분 가능, colorblind-safe)
    CATEGORICAL = [
        '#0173B2',  # Blue
        '#DE8F05',  # Orange  
        '#029E73',  # Green
        '#CC78BC',  # Purple
        '#CA9161',  # Brown
        '#949494',  # Gray
        '#ECE133',  # Yellow
        '#56B4E9',  # Sky blue
    ]
    
    # Sequential (단일 변수 강도)
    SEQUENTIAL_BLUE = ['#EFF3FF', '#BDD7E7', '#6BAED6', '#3182BD', '#08519C']
    SEQUENTIAL_RED = ['#FEE5D9', '#FCAE91', '#FB6A4A', '#DE2D26', '#A50F15']
    
    # Diverging (양극성 데이터)
    DIVERGING_BLUE_RED = ['#2166AC', '#67A9CF', '#F7F7F7', '#F4A582', '#B2182B']
    DIVERGING_PURPLE_ORANGE = ['#7F3B08', '#B35806', '#F7F7F7', '#542788', '#2D004B']
    
    # Conditions (실험 조건별)
    CONDITIONS = {
        'BASE': '#0173B2',      # Blue
        'STIM': '#CC78BC',      # Purple
        'CONTROL': '#029E73',   # Green
        'DRUG': '#DE8F05',      # Orange
    }
    
    # Statistical significance
    SIGNIFICANCE = {
        'ns': '#949494',        # Gray
        'significant': '#DE2D26'  # Red
    }


# ============================================================================
# PROFESSIONAL PLOT STYLE
# ============================================================================
def set_professional_style():
    """Nature/Cell/Science 스타일 설정"""
    
    # Clean, minimal style
    sns.set_style("ticks", {
        'axes.edgecolor': '0.15',
        'axes.linewidth': 1.0,
        'xtick.direction': 'out',
        'ytick.direction': 'out',
        'xtick.major.size': 4,
        'ytick.major.size': 4,
        'xtick.major.width': 1.0,
        'ytick.major.width': 1.0,
        'grid.linewidth': 0.5,
        'grid.color': '0.9',
        'axes.facecolor': 'white',
        'figure.facecolor': 'white',
    })
    
    # Typography
    plt.rcParams.update({
        'font.size': 9,
        'axes.labelsize': 10,
        'axes.titlesize': 11,
        'xtick.labelsize': 8,
        'ytick.labelsize': 8,
        'legend.fontsize': 8,
        'figure.titlesize': 12,
    })


def remove_chartjunk(ax):
    """불필요한 시각 요소 제거 (Tufte's principle)"""
    # Top and right spines 제거
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Grid 최소화
    ax.grid(False)
    
    # Tick 방향 외부로
    ax.tick_params(direction='out', length=4, width=1)
    
    return ax


# ============================================================================
# ENHANCED PER-WELL ANALYZER
# ============================================================================
class ProfessionalPerWellAnalyzer:
    """전문가급 Per-Well 분석 및 시각화"""
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir) / '00_per_well_professional'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.palette = ScientificPalette()
        
        set_professional_style()
    
    def analyze_well(self, well):
        """Well별 전문가급 분석"""
        print(f'\n[PROFESSIONAL] Analyzing {well}...')
        
        well_data = self.df[self.df['Well'] == well]
        
        if well_data.empty:
            print(f'  ⚠ No data for {well}')
            return
        
        # Create professional figure
        self._create_professional_figure(well, well_data)
    
    def _create_professional_figure(self, well, well_data):
        """전문가급 figure 생성"""
        fig = plt.figure(figsize=(8.5, 6))  # Nature single column width
        
        # GridSpec for better layout control
        gs = fig.add_gridspec(2, 3, hspace=0.4, wspace=0.4,
                             left=0.1, right=0.95, top=0.92, bottom=0.08)
        
        # Axes
        ax1 = fig.add_subplot(gs[0, 0])  # MFR
        ax2 = fig.add_subplot(gs[0, 1])  # Light Response
        ax3 = fig.add_subplot(gs[0, 2])  # Drug Effect
        ax4 = fig.add_subplot(gs[1, 0])  # Burst Frequency
        ax5 = fig.add_subplot(gs[1, 1])  # Total Spikes
        ax6 = fig.add_subplot(gs[1, 2])  # Active Electrodes
        
        axes = [ax1, ax2, ax3, ax4, ax5, ax6]
        
        # 1. Mean Firing Rate (BASE vs STIM)
        self._plot_mfr_comparison(ax1, well_data)
        
        # 2. Light Response
        self._plot_light_response(ax2, well_data)
        
        # 3. Drug Effect
        self._plot_drug_effect(ax3, well_data)
        
        # 4. Burst Frequency
        self._plot_burst_comparison(ax4, well_data)
        
        # 5. Total Spikes
        self._plot_spikes_comparison(ax5, well_data)
        
        # 6. Active Electrodes
        self._plot_electrodes_comparison(ax6, well_data)
        
        # Remove chartjunk from all axes
        for ax in axes:
            remove_chartjunk(ax)
        
        # Overall title
        fig.suptitle(f'Well {well} - Comprehensive Analysis', 
                    fontweight='bold', fontsize=12, y=0.98)
        
        # Save
        output_path = self.output_dir / f'{well}_professional.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.savefig(output_path.with_suffix('.pdf'), bbox_inches='tight')  # PDF for vector
        plt.close()
        
        print(f'  ✓ Saved: {well}_professional.png (+ PDF)')
    
    def _plot_mfr_comparison(self, ax, well_data):
        """MFR 비교 (BASE vs STIM) with statistics"""
        mfr_data = well_data[well_data['Metric'] == 'mean_firing_rate_hz']
        
        base_data = mfr_data[mfr_data['BASE_STIM'] == 'BASE']['Value'].values
        stim_data = mfr_data[mfr_data['BASE_STIM'] == 'STIM']['Value'].values
        
        if len(base_data) == 0 or len(stim_data) == 0:
            return
        
        # Calculate statistics
        base_mean = base_data.mean()
        base_sem = stats.sem(base_data) if len(base_data) > 1 else 0
        stim_mean = stim_data.mean()
        stim_sem = stats.sem(stim_data) if len(stim_data) > 1 else 0
        
        # Plot with error bars
        positions = [0, 1]
        means = [base_mean, stim_mean]
        sems = [base_sem, stim_sem]
        colors = [self.palette.CONDITIONS['BASE'], self.palette.CONDITIONS['STIM']]
        
        bars = ax.bar(positions, means, yerr=sems, 
                     color=colors, alpha=0.85, 
                     capsize=4, error_kw={'linewidth': 1.5, 'ecolor': '0.3'})
        
        # Labels
        ax.set_xticks(positions)
        ax.set_xticklabels(['Baseline', 'Light'])
        ax.set_ylabel('MFR (Hz)', fontweight='bold')
        ax.set_title('Mean Firing Rate', fontsize=10, pad=8)
        
        # Add individual data points
        if len(base_data) > 1:
            ax.scatter([0]*len(base_data), base_data, 
                      s=20, c='0.3', alpha=0.5, zorder=3)
        if len(stim_data) > 1:
            ax.scatter([1]*len(stim_data), stim_data,
                      s=20, c='0.3', alpha=0.5, zorder=3)
        
        # Statistical significance
        if len(base_data) > 1 and len(stim_data) > 1:
            t_stat, p_val = stats.ttest_ind(base_data, stim_data)
            if p_val < 0.05:
                y_max = max(means) + max(sems) * 1.2
                ax.plot([0, 1], [y_max, y_max], 'k-', linewidth=1)
                sig_text = '***' if p_val < 0.001 else ('**' if p_val < 0.01 else '*')
                ax.text(0.5, y_max, sig_text, ha='center', va='bottom', fontsize=10)
    
    def _plot_light_response(self, ax, well_data):
        """Light response analysis"""
        mfr_data = well_data[well_data['Metric'] == 'mean_firing_rate_hz']
        
        baseline = mfr_data[
            (mfr_data['BASE_STIM'] == 'BASE') & 
            (mfr_data['EXP_TYPE'] == 'CONTROL')
        ]['Value'].mean()
        
        stim = mfr_data[
            (mfr_data['BASE_STIM'] == 'STIM') & 
            (mfr_data['EXP_TYPE'] == 'CONTROL')
        ]['Value'].mean()
        
        means = [baseline, stim]
        colors = [self.palette.CONDITIONS['CONTROL'], self.palette.CONDITIONS['STIM']]
        
        bars = ax.bar([0, 1], means, color=colors, alpha=0.85)
        
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['Baseline', 'Light'])
        ax.set_ylabel('MFR (Hz)', fontweight='bold')
        ax.set_title('Light Response', fontsize=10, pad=8)
        
        # % change annotation
        if baseline > 0:
            pct_change = ((stim - baseline) / baseline) * 100
            ax.text(0.5, max(means) * 1.05, f'{pct_change:+.1f}%',
                   ha='center', fontsize=8, color='0.3')
    
    def _plot_drug_effect(self, ax, well_data):
        """Drug effect analysis"""
        mfr_data = well_data[well_data['Metric'] == 'mean_firing_rate_hz']
        
        control = mfr_data[mfr_data['EXP_TYPE'] == 'CONTROL']['Value'].mean()
        drug = mfr_data[mfr_data['EXP_TYPE'] == 'DRUG']['Value'].mean()
        
        means = [control, drug]
        colors = [self.palette.CONDITIONS['CONTROL'], self.palette.CONDITIONS['DRUG']]
        
        bars = ax.bar([0, 1], means, color=colors, alpha=0.85)
        
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['Control', 'Drug'])
        ax.set_ylabel('MFR (Hz)', fontweight='bold')
        ax.set_title('Drug Effect', fontsize=10, pad=8)
        
        # % change
        if control > 0:
            pct_change = ((drug - control) / control) * 100
            color = self.palette.SIGNIFICANCE['significant'] if abs(pct_change) > 20 else self.palette.SIGNIFICANCE['ns']
            ax.text(0.5, max(means) * 1.05, f'{pct_change:+.1f}%',
                   ha='center', fontsize=8, color=color, fontweight='bold')
    
    def _plot_burst_comparison(self, ax, well_data):
        """Burst frequency comparison"""
        burst_data = well_data[well_data['Metric'] == 'burst_frequency_hz']
        
        base_mean = burst_data[burst_data['BASE_STIM'] == 'BASE']['Value'].mean()
        stim_mean = burst_data[burst_data['BASE_STIM'] == 'STIM']['Value'].mean()
        
        means = [base_mean, stim_mean]
        colors = [self.palette.CONDITIONS['BASE'], self.palette.CONDITIONS['STIM']]
        
        ax.bar([0, 1], means, color=colors, alpha=0.85)
        
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['Baseline', 'Light'])
        ax.set_ylabel('Burst Freq (Hz)', fontweight='bold')
        ax.set_title('Burst Frequency', fontsize=10, pad=8)
    
    def _plot_spikes_comparison(self, ax, well_data):
        """Total spikes comparison"""
        spike_data = well_data[well_data['Metric'] == 'number_of_spikes']
        
        base_mean = spike_data[spike_data['BASE_STIM'] == 'BASE']['Value'].mean()
        stim_mean = spike_data[spike_data['BASE_STIM'] == 'STIM']['Value'].mean()
        
        means = [base_mean, stim_mean]
        colors = [self.palette.CONDITIONS['BASE'], self.palette.CONDITIONS['STIM']]
        
        ax.bar([0, 1], means, color=colors, alpha=0.85)
        
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['Baseline', 'Light'])
        ax.set_ylabel('Spike Count', fontweight='bold')
        ax.set_title('Total Spikes', fontsize=10, pad=8)
        
        # Scientific notation if large numbers
        if max(means) > 10000:
            ax.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
    
    def _plot_electrodes_comparison(self, ax, well_data):
        """Active electrodes comparison"""
        elec_data = well_data[well_data['Metric'] == 'number_of_active_electrodes']
        
        base_mean = elec_data[elec_data['BASE_STIM'] == 'BASE']['Value'].mean()
        stim_mean = elec_data[elec_data['BASE_STIM'] == 'STIM']['Value'].mean()
        
        means = [base_mean, stim_mean]
        colors = [self.palette.CONDITIONS['BASE'], self.palette.CONDITIONS['STIM']]
        
        ax.bar([0, 1], means, color=colors, alpha=0.85)
        
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['Baseline', 'Light'])
        ax.set_ylabel('Active Electrodes', fontweight='bold')
        ax.set_title('Active Electrodes', fontsize=10, pad=8)
        
        # Integer y-axis
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))


# ============================================================================
# ENHANCED SPATIAL HEATMAP
# ============================================================================
class ProfessionalSpatialHeatmap:
    """전문가급 Spatial Heatmap"""
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir) / 'spatial_heatmaps_professional'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.palette = ScientificPalette()
        
        set_professional_style()
        
        # Well layout
        self.well_positions = {
            'A1': (0, 0), 'A3': (0, 2),
            'B1': (1, 0), 'B3': (1, 2)
        }
    
    def create_all_heatmaps(self):
        """모든 heatmap 생성"""
        print('\n[SPATIAL HEATMAP] Creating professional spatial heatmaps...')
        
        self._create_baseline_heatmap()
        self._create_light_response_heatmap()
        self._create_drug_effect_heatmap()
        
        print('  ✓ All professional spatial heatmaps created')
    
    def _create_baseline_heatmap(self):
        """Baseline activity heatmap"""
        baseline = self.df[
            (self.df['BASE_STIM'] == 'BASE') & 
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        
        if baseline.empty:
            return
        
        data = baseline.groupby('Well')['Value'].mean()
        self._plot_heatmap(data, 'Baseline Activity (MFR)',
                          'spatial_heatmap_baseline_pro.png',
                          cmap='YlOrRd', vmin=0)
    
    def _create_light_response_heatmap(self):
        """Light response heatmap"""
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
            return
        
        base_mean = baseline.groupby('Well')['Value'].mean()
        stim_mean = stim.groupby('Well')['Value'].mean()
        
        pct_change = ((stim_mean - base_mean) / base_mean * 100).fillna(0)
        
        self._plot_heatmap(pct_change, 'Light Response (% Change)',
                          'spatial_heatmap_light_response_pro.png',
                          cmap='RdBu_r', center=0)
    
    def _create_drug_effect_heatmap(self):
        """Drug effect heatmap"""
        control = self.df[
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        drug = self.df[
            (self.df['EXP_TYPE'] == 'DRUG') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        
        if control.empty or drug.empty:
            return
        
        ctrl_mean = control.groupby('Well')['Value'].mean()
        drug_mean = drug.groupby('Well')['Value'].mean()
        
        pct_change = ((drug_mean - ctrl_mean) / ctrl_mean * 100).fillna(0)
        
        self._plot_heatmap(pct_change, 'Drug Effect (% Change)',
                          'spatial_heatmap_drug_effect_pro.png',
                          cmap='RdBu_r', center=0)
    
    def _plot_heatmap(self, data, title, filename, cmap='YlOrRd', vmin=None, center=None):
        """Professional heatmap plotting"""
        # Create matrix
        max_row = max(pos[0] for pos in self.well_positions.values()) + 1
        max_col = max(pos[1] for pos in self.well_positions.values()) + 1
        
        matrix = np.full((max_row, max_col), np.nan)
        
        for well, value in data.items():
            if well in self.well_positions:
                row, col = self.well_positions[well]
                matrix[row, col] = value
        
        # Plot
        fig, ax = plt.subplots(figsize=(6, 5))
        
        # Heatmap with clean style
        if center is not None:
            vmax = max(abs(np.nanmin(matrix)), abs(np.nanmax(matrix)))
            im = ax.imshow(matrix, cmap=cmap, aspect='auto', 
                          interpolation='bilinear',
                          vmin=-vmax, vmax=vmax)
        else:
            im = ax.imshow(matrix, cmap=cmap, aspect='auto',
                          interpolation='bilinear',
                          vmin=vmin)
        
        # Annotations
        for well, value in data.items():
            if well in self.well_positions:
                row, col = self.well_positions[well]
                text_color = 'white' if abs(value) > (np.nanmax(np.abs(matrix)) * 0.6) else 'black'
                ax.text(col, row, f'{value:.2f}', 
                       ha='center', va='center',
                       fontsize=10, fontweight='bold',
                       color=text_color)
        
        # Labels
        ax.set_xticks([0, 2])
        ax.set_xticklabels(['Col 1', 'Col 3'])
        ax.set_yticks([0, 1])
        ax.set_yticklabels(['Row A', 'Row B'])
        
        ax.set_title(title, fontweight='bold', fontsize=11, pad=12)
        
        # Colorbar
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.tick_params(labelsize=8)
        cbar.outline.set_linewidth(0.5)
        
        # Clean style
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(length=0)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / filename, dpi=300, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.savefig(self.output_dir / filename.replace('.png', '.pdf'), bbox_inches='tight')
        plt.close()


# ============================================================================
# ENHANCED DASHBOARD
# ============================================================================
class ProfessionalDashboard:
    """전문가급 종합 대시보드"""
    
    def __init__(self, df, output_path):
        self.df = df
        self.output_path = Path(output_path)
        self.palette = ScientificPalette()
        
        set_professional_style()
    
    def create(self):
        """대시보드 생성"""
        print('\n[DASHBOARD] Creating professional master dashboard...')
        
        fig = plt.figure(figsize=(12, 10))
        gs = fig.add_gridspec(3, 3, hspace=0.4, wspace=0.4,
                             left=0.08, right=0.96, top=0.94, bottom=0.06)
        
        # Create all subplots
        axes = []
        for i in range(3):
            for j in range(3):
                axes.append(fig.add_subplot(gs[i, j]))
        
        # Plot each panel
        self._plot_spontaneous_mfr(axes[0])
        self._plot_drug_effect_mfr(axes[1])
        self._plot_spontaneous_burst(axes[2])
        
        self._plot_light_response_overall(axes[3])
        self._plot_light_response_perwell(axes[4])
        self._plot_light_response_burst(axes[5])
        
        self._plot_light_modulation(axes[6])
        self._plot_burst_drug_effect(axes[7])
        self._plot_drug_comparison(axes[8])
        
        # Clean all axes
        for ax in axes:
            remove_chartjunk(ax)
        
        # Title
        fig.suptitle('MEA Comprehensive Analysis Dashboard',
                    fontweight='bold', fontsize=14, y=0.98)
        
        # Save
        plt.savefig(self.output_path, dpi=300, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.savefig(self.output_path.with_suffix('.pdf'), bbox_inches='tight')
        plt.close()
        
        print(f'  ✓ Saved: {self.output_path.name} (+ PDF)')
    
    def _plot_spontaneous_mfr(self, ax):
        """Spontaneous MFR by well"""
        baseline = self.df[
            (self.df['BASE_STIM'] == 'BASE') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        
        if baseline.empty:
            return
        
        well_mfr = baseline.groupby('Well')['Value'].mean().sort_index()
        
        ax.bar(range(len(well_mfr)), well_mfr.values,
              color=self.palette.CATEGORICAL[0], alpha=0.85)
        
        ax.set_xticks(range(len(well_mfr)))
        ax.set_xticklabels(well_mfr.index, rotation=0)
        ax.set_ylabel('MFR (Hz)', fontweight='bold')
        ax.set_title('Spontaneous Activity\n(Baseline MFR)', fontsize=9)
    
    def _plot_drug_effect_mfr(self, ax):
        """Drug effect on MFR"""
        control = self.df[
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        drug = self.df[
            (self.df['EXP_TYPE'] == 'DRUG') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ]
        
        if control.empty or drug.empty:
            return
        
        ctrl_mean = control.groupby('Well')['Value'].mean()
        drug_mean = drug.groupby('Well')['Value'].mean()
        
        pct_change = ((drug_mean - ctrl_mean) / ctrl_mean * 100)
        
        colors = [self.palette.CONDITIONS['DRUG'] if x < 0 
                 else self.palette.CONDITIONS['CONTROL'] 
                 for x in pct_change.values]
        
        ax.bar(range(len(pct_change)), pct_change.values,
              color=colors, alpha=0.85)
        
        ax.axhline(y=0, color='0.3', linestyle='--', linewidth=0.8)
        ax.set_xticks(range(len(pct_change)))
        ax.set_xticklabels(pct_change.index, rotation=0)
        ax.set_ylabel('% Change', fontweight='bold')
        ax.set_title('Drug Effect\n(% Change in MFR)', fontsize=9)
    
    def _plot_spontaneous_burst(self, ax):
        """Spontaneous burst activity"""
        burst = self.df[
            (self.df['BASE_STIM'] == 'BASE') &
            (self.df['Metric'] == 'burst_frequency_hz')
        ]
        
        if burst.empty:
            return
        
        well_burst = burst.groupby('Well')['Value'].mean().sort_index()
        
        ax.bar(range(len(well_burst)), well_burst.values,
              color=self.palette.CATEGORICAL[2], alpha=0.85)
        
        ax.set_xticks(range(len(well_burst)))
        ax.set_xticklabels(well_burst.index, rotation=0)
        ax.set_ylabel('Burst Freq (Hz)', fontweight='bold')
        ax.set_title('Spontaneous Activity\n(Baseline Burst)', fontsize=9)
    
    def _plot_light_response_overall(self, ax):
        """Overall light response"""
        mfr = self.df[self.df['Metric'] == 'mean_firing_rate_hz']
        
        baseline = mfr[
            (mfr['BASE_STIM'] == 'BASE') &
            (mfr['EXP_TYPE'] == 'CONTROL')
        ]['Value'].mean()
        
        stim = mfr[
            (mfr['BASE_STIM'] == 'STIM') &
            (mfr['EXP_TYPE'] == 'CONTROL')
        ]['Value'].mean()
        
        response = stim - baseline
        
        ax.bar([0], [response],
              color=self.palette.CONDITIONS['STIM'], alpha=0.85)
        
        ax.set_xticks([0])
        ax.set_xticklabels(['Blue Light'])
        ax.set_ylabel('MFR Response (Hz)', fontweight='bold')
        ax.set_title('Light Response\n(Overall)', fontsize=9)
        ax.axhline(y=0, color='0.3', linestyle='--', linewidth=0.8)
    
    def _plot_light_response_perwell(self, ax):
        """Per-well light response"""
        mfr = self.df[self.df['Metric'] == 'mean_firing_rate_hz']
        
        baseline = mfr[
            (mfr['BASE_STIM'] == 'BASE') &
            (mfr['EXP_TYPE'] == 'CONTROL')
        ].groupby('Well')['Value'].mean()
        
        stim = mfr[
            (mfr['BASE_STIM'] == 'STIM') &
            (mfr['EXP_TYPE'] == 'CONTROL')
        ].groupby('Well')['Value'].mean()
        
        response = stim - baseline
        
        ax.bar(range(len(response)), response.values,
              color=self.palette.CONDITIONS['STIM'], alpha=0.85)
        
        ax.axhline(y=0, color='0.3', linestyle='--', linewidth=0.8)
        ax.set_xticks(range(len(response)))
        ax.set_xticklabels(response.index, rotation=0)
        ax.set_ylabel('MFR Response (Hz)', fontweight='bold')
        ax.set_title('Light Response\n(Per-Well)', fontsize=9)
    
    def _plot_light_response_burst(self, ax):
        """Burst response to light"""
        burst = self.df[self.df['Metric'] == 'burst_frequency_hz']
        
        baseline = burst[
            (burst['BASE_STIM'] == 'BASE') &
            (burst['EXP_TYPE'] == 'CONTROL')
        ].groupby('Well')['Value'].mean()
        
        stim = burst[
            (burst['BASE_STIM'] == 'STIM') &
            (burst['EXP_TYPE'] == 'CONTROL')
        ].groupby('Well')['Value'].mean()
        
        response = stim - baseline
        
        colors = [self.palette.CATEGORICAL[2] if x > 0 
                 else self.palette.CATEGORICAL[1] 
                 for x in response.values]
        
        ax.bar(range(len(response)), response.values,
              color=colors, alpha=0.85)
        
        ax.axhline(y=0, color='0.3', linestyle='--', linewidth=0.8)
        ax.set_xticks(range(len(response)))
        ax.set_xticklabels(response.index, rotation=0)
        ax.set_ylabel('Burst Response (Hz)', fontweight='bold')
        ax.set_title('Light Response\n(Burst)', fontsize=9)
    
    def _plot_light_modulation(self, ax):
        """Light response modulation by drug"""
        # Control light response
        ctrl_base = self.df[
            (self.df['BASE_STIM'] == 'BASE') &
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ].groupby('Well')['Value'].mean()
        
        ctrl_stim = self.df[
            (self.df['BASE_STIM'] == 'STIM') &
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ].groupby('Well')['Value'].mean()
        
        ctrl_response = ctrl_stim - ctrl_base
        
        # Drug light response
        drug_base = self.df[
            (self.df['BASE_STIM'] == 'BASE') &
            (self.df['EXP_TYPE'] == 'DRUG') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ].groupby('Well')['Value'].mean()
        
        drug_stim = self.df[
            (self.df['BASE_STIM'] == 'STIM') &
            (self.df['EXP_TYPE'] == 'DRUG') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ].groupby('Well')['Value'].mean()
        
        drug_response = drug_stim - drug_base
        
        modulation = drug_response - ctrl_response
        
        colors = [self.palette.CONDITIONS['DRUG'] if x < 0 
                 else self.palette.CONDITIONS['CONTROL'] 
                 for x in modulation.values]
        
        ax.bar(range(len(modulation)), modulation.values,
              color=colors, alpha=0.85)
        
        ax.axhline(y=0, color='0.3', linestyle='--', linewidth=0.8)
        ax.set_xticks(range(len(modulation)))
        ax.set_xticklabels(modulation.index, rotation=0)
        ax.set_ylabel('Modulation (Hz)', fontweight='bold')
        ax.set_title('Light Response Modulation\n(Drug Effect)', fontsize=9)
    
    def _plot_burst_drug_effect(self, ax):
        """Burst change by drug"""
        burst = self.df[self.df['Metric'] == 'burst_frequency_hz']
        
        ctrl = burst[burst['EXP_TYPE'] == 'CONTROL'].groupby('Well')['Value'].mean()
        drug = burst[burst['EXP_TYPE'] == 'DRUG'].groupby('Well')['Value'].mean()
        
        pct_change = ((drug - ctrl) / ctrl * 100)
        
        colors = [self.palette.CONDITIONS['DRUG'] if x < 0 
                 else self.palette.CONDITIONS['CONTROL'] 
                 for x in pct_change.values]
        
        ax.bar(range(len(pct_change)), pct_change.values,
              color=colors, alpha=0.85)
        
        ax.axhline(y=0, color='0.3', linestyle='--', linewidth=0.8)
        ax.set_xticks(range(len(pct_change)))
        ax.set_xticklabels(pct_change.index, rotation=0)
        ax.set_ylabel('% Change', fontweight='bold')
        ax.set_title('Burst Change\n(Drug Effect)', fontsize=9)
    
    def _plot_drug_comparison(self, ax):
        """Drug effect comparison (baseline vs light)"""
        # Baseline drug effect
        base_ctrl = self.df[
            (self.df['BASE_STIM'] == 'BASE') &
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ].groupby('Well')['Value'].mean()
        
        base_drug = self.df[
            (self.df['BASE_STIM'] == 'BASE') &
            (self.df['EXP_TYPE'] == 'DRUG') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ].groupby('Well')['Value'].mean()
        
        base_effect = ((base_drug - base_ctrl) / base_ctrl * 100)
        
        # Light drug effect
        stim_ctrl = self.df[
            (self.df['BASE_STIM'] == 'STIM') &
            (self.df['EXP_TYPE'] == 'CONTROL') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ].groupby('Well')['Value'].mean()
        
        stim_drug = self.df[
            (self.df['BASE_STIM'] == 'STIM') &
            (self.df['EXP_TYPE'] == 'DRUG') &
            (self.df['Metric'] == 'mean_firing_rate_hz')
        ].groupby('Well')['Value'].mean()
        
        stim_effect = ((stim_drug - stim_ctrl) / stim_ctrl * 100)
        
        # Plot grouped bars
        x = np.arange(len(base_effect))
        width = 0.35
        
        ax.bar(x - width/2, base_effect.values, width,
              label='Baseline', color=self.palette.CONDITIONS['BASE'], alpha=0.85)
        ax.bar(x + width/2, stim_effect.values, width,
              label='Light', color=self.palette.CONDITIONS['STIM'], alpha=0.85)
        
        ax.axhline(y=0, color='0.3', linestyle='--', linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(base_effect.index, rotation=0)
        ax.set_ylabel('% Change', fontweight='bold')
        ax.set_title('Drug Effect Summary\n(Comparison)', fontsize=9)
        ax.legend(frameon=False, fontsize=7, loc='best')


# ============================================================================
# MAIN INTEGRATION
# ============================================================================
if __name__ == '__main__':
    from mea_auto_analyzer_v32 import OptimizedFormatLoader
    
    input_dir = Path(r"D:\MEAdata\#7-1\output\processed")
    output_dir = Path(r"D:\MEAdata\#7-1\analysis_professional")
    
    # Load data
    loader = OptimizedFormatLoader(input_dir)
    df = loader.load_all()
    
    # Professional per-well analysis
    perwell = ProfessionalPerWellAnalyzer(df, output_dir)
    for well in sorted(df['Well'].unique()):
        perwell.analyze_well(well)
    
    # Professional spatial heatmaps
    spatial = ProfessionalSpatialHeatmap(df, output_dir)
    spatial.create_all_heatmaps()
    
    # Professional dashboard
    dashboard_path = output_dir / 'MASTER_DASHBOARD_PROFESSIONAL.png'
    dashboard = ProfessionalDashboard(df, dashboard_path)
    dashboard.create()
    
    print('\n✅ Professional visualization complete!')
