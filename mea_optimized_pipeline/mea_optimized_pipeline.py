"""
MEA 최적화 통합 파이프라인 (Optimized Pipeline)
================================================
중복 제거 및 통합 최적화 버전

기능:
1. 데이터 전처리 (MEAPipeline)
2. 기본 분석 (v3.2 + v3.5 burst enhancements)
3. 고급 분석 (v3.3 advanced analytics) - 선택사항
4. 전문가급 시각화 (v3.4 professional style) - 선택사항

장점:
- 중복 제거: mea_full_pipeline_v32와 mea_complete_analyzer_v35 통합
- 유연성: 분석 레벨 선택 가능 (basic/advanced/professional/full)
- 효율성: 한 번의 실행으로 전처리부터 고급 분석까지 완료

Usage:
    from mea_optimized_pipeline import OptimizedPipeline

    # 기본 분석만
    pipeline = OptimizedPipeline(
        input_dir=r"D:\MyProjects\#7-1",
        output_base=r"D:\MyProjects\#7-1\output"
    )
    pipeline.run(mode='basic')

    # 모든 분석 (권장)
    pipeline.run(mode='full')
"""

from pathlib import Path
from datetime import datetime

# 전처리
from mea_pipeline import MEAPipeline

# v3.2 기본 분석 (with v3.5 burst enhancements)
from mea_auto_analyzer_v32 import (
    OptimizedFormatLoader,
    SpontaneousAnalyzer,
    LightResponseAnalyzer,
    DrugEffectAnalyzer,
    CombinedExcelCreator,
    DetailedReportGenerator,
    PerWellAnalyzerEnhanced,
    EnhancedDashboard
)

# Burst Analyzer 추가
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

class BurstAnalyzer:
    """Burst 관련 metric 전용 분석기"""
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir) / '04_burst_analysis'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.burst_df = None
        self.burst_summary = None
    
    def analyze(self):
        """Burst 관련 분석 수행"""
        print('\n[4] Burst Analysis...')
        
        # Burst 관련 metric 필터링
        burst_metrics = self.df[
            self.df['Metric'].str.contains('burst', case=False, na=False)
        ]
        
        if burst_metrics.empty:
            print('  ⚠ No burst metrics found')
            return self
        
        self.burst_df = burst_metrics.copy()
        
        # Burst metric 목록
        burst_metric_list = sorted(burst_metrics['Metric'].unique())
        print(f'  ✓ Found {len(burst_metric_list)} burst metrics:')
        for metric in burst_metric_list[:10]:  # 처음 10개만 표시
            print(f'    - {metric}')
        if len(burst_metric_list) > 10:
            print(f'    ... and {len(burst_metric_list) - 10} more')
        
        # 요약 통계 생성
        self._create_summary()
        
        # CSV 저장
        csv_path = self.output_dir / 'burst_analysis_all.csv'
        self.burst_df.to_csv(csv_path, index=False)
        print(f'  ✓ Burst data saved: {csv_path.name}')
        
        return self
    
    def _create_summary(self):
        """Burst 요약 통계 생성 (Wavelength별 구분 추가)"""
        if self.burst_df is None or self.burst_df.empty:
            return
        
        summary_list = []
        
        for metric in sorted(self.burst_df['Metric'].unique()):
            metric_data = self.burst_df[self.burst_df['Metric'] == metric]
            
            # Well별 × Wavelength별 통계
            for well in sorted(metric_data['Well'].unique()):
                well_data = metric_data[metric_data['Well'] == well]
                
                # Wavelength별로 구분
                wavelengths = sorted(well_data['LIGHT_CODE'].unique()) if 'LIGHT_CODE' in well_data.columns else ['UNKNOWN']
                
                for wavelength in wavelengths:
                    wavelength_data = well_data[well_data['LIGHT_CODE'] == wavelength] if 'LIGHT_CODE' in well_data.columns else well_data
                    
                    if wavelength_data.empty:
                        continue
                    
                    summary_list.append({
                        'Well': well,
                        'Wavelength': wavelength,
                        'Metric': metric,
                        'Mean': wavelength_data['Value'].mean(),
                        'Std': wavelength_data['Value'].std(),
                        'Min': wavelength_data['Value'].min(),
                        'Max': wavelength_data['Value'].max(),
                        'Count': len(wavelength_data),
                        'BASE_STIM': wavelength_data['BASE_STIM'].iloc[0] if 'BASE_STIM' in wavelength_data.columns else 'N/A',
                        'EXP_TYPE': wavelength_data['EXP_TYPE'].iloc[0] if 'EXP_TYPE' in wavelength_data.columns else 'N/A',
                        'DRUG': wavelength_data['DRUG'].iloc[0] if 'DRUG' in wavelength_data.columns else 'N/A'
                    })
        
        self.burst_summary = pd.DataFrame(summary_list)
        
        if not self.burst_summary.empty:
            summary_path = self.output_dir / 'burst_summary_statistics.csv'
            self.burst_summary.to_csv(summary_path, index=False)
            print(f'  ✓ Summary statistics saved: {summary_path.name} (with wavelength breakdown)')
    
    def visualize(self):
        """Burst 시각화"""
        if self.burst_df is None or self.burst_df.empty:
            print('  ⚠ No burst data to visualize')
            return self
        
        print('  Creating burst visualizations...')
        
        # 1. Burst metrics 비교 (Well별)
        self._plot_well_comparison()
        
        # 2. Burst metrics 비교 (Condition별)
        self._plot_condition_comparison()
        
        # 3. Burst metrics 히트맵
        self._plot_heatmap()
        
        # 4. 주요 Burst metrics 시계열/분포
        self._plot_key_metrics()
        
        print('  ✓ Burst visualizations complete')
        return self
    
    def _plot_well_comparison(self):
        """Well별 burst metrics 비교"""
        if self.burst_summary is None or self.burst_summary.empty:
            return
        
        # 주요 metric 선택
        key_metrics = [
            'burst_frequency',
            'burst_duration',
            'spikes_per_burst',
            'inter_burst_interval'
        ]
        
        available_metrics = [m for m in key_metrics 
                           if any(m in str(met).lower() for met in self.burst_summary['Metric'].unique())]
        
        if not available_metrics:
            return
        
        n_metrics = len(available_metrics)
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        axes = axes.flatten()
        
        for idx, metric_pattern in enumerate(available_metrics[:4]):
            ax = axes[idx]
            
            # 해당 metric 필터링
            metric_data = self.burst_summary[
                self.burst_summary['Metric'].str.contains(metric_pattern, case=False, na=False)
            ]
            
            if metric_data.empty:
                ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
                continue
            
            # Well별 평균
            well_means = metric_data.groupby('Well')['Mean'].mean().sort_values(ascending=False)
            
            ax.bar(range(len(well_means)), well_means.values, alpha=0.7, edgecolor='black')
            ax.set_xticks(range(len(well_means)))
            ax.set_xticklabels(well_means.index, rotation=45, ha='right')
            ax.set_ylabel('Mean Value', fontweight='bold')
            ax.set_title(f'{metric_pattern.replace("_", " ").title()}\n(Per Well)', 
                        fontweight='bold', fontsize=11)
            ax.grid(axis='y', alpha=0.3)
        
        # 빈 subplot 숨기기
        for idx in range(len(available_metrics), 4):
            axes[idx].set_visible(False)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'burst_well_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f'    ✓ Saved: burst_well_comparison.png')
    
    def _plot_condition_comparison(self):
        """Condition별 burst metrics 비교"""
        if self.burst_summary is None or self.burst_summary.empty:
            return
        
        # BASE_STIM 또는 EXP_TYPE별 비교
        if 'BASE_STIM' in self.burst_summary.columns:
            condition_col = 'BASE_STIM'
        elif 'EXP_TYPE' in self.burst_summary.columns:
            condition_col = 'EXP_TYPE'
        else:
            return
        
        # 주요 metric 선택
        key_metric = None
        for pattern in ['burst_frequency', 'burst_duration', 'spikes_per_burst']:
            matching = self.burst_summary[
                self.burst_summary['Metric'].str.contains(pattern, case=False, na=False)
            ]
            if not matching.empty:
                key_metric = matching['Metric'].iloc[0]
                break
        
        if key_metric is None:
            return
        
        metric_data = self.burst_summary[self.burst_summary['Metric'] == key_metric]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        conditions = sorted(metric_data[condition_col].unique())
        well_means = []
        condition_labels = []
        
        for condition in conditions:
            cond_data = metric_data[metric_data[condition_col] == condition]
            if not cond_data.empty:
                well_means.append(cond_data['Mean'].mean())
                condition_labels.append(str(condition))
        
        if well_means:
            ax.bar(range(len(condition_labels)), well_means, alpha=0.7, edgecolor='black')
            ax.set_xticks(range(len(condition_labels)))
            ax.set_xticklabels(condition_labels, fontweight='bold')
            ax.set_ylabel('Mean Value', fontweight='bold')
            ax.set_title(f'{key_metric.replace("_", " ").title()}\nby {condition_col}', 
                        fontweight='bold', fontsize=12)
            ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'burst_condition_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f'    ✓ Saved: burst_condition_comparison.png')
    
    def _plot_heatmap(self):
        """Burst metrics 히트맵"""
        if self.burst_summary is None or self.burst_summary.empty:
            return
        
        # Well × Metric pivot
        pivot = self.burst_summary.pivot_table(
            index='Well',
            columns='Metric',
            values='Mean',
            aggfunc='mean'
        )
        
        if pivot.empty:
            return
        
        fig, ax = plt.subplots(figsize=(max(12, len(pivot.columns) * 0.8), 
                                        max(8, len(pivot.index) * 0.5)))
        
        sns.heatmap(pivot, annot=True, fmt='.2f', cmap='YlOrRd',
                   cbar_kws={'label': 'Mean Value'},
                   linewidths=0.5, linecolor='white', ax=ax)
        
        ax.set_title('Burst Metrics Heatmap\n(Well × Metric)', 
                    fontweight='bold', fontsize=14, pad=15)
        ax.set_xlabel('Burst Metrics', fontweight='bold')
        ax.set_ylabel('Wells', fontweight='bold')
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(self.output_dir / 'burst_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f'    ✓ Saved: burst_heatmap.png')
    
    def _plot_key_metrics(self):
        """주요 burst metrics 상세 플롯"""
        if self.burst_df is None or self.burst_df.empty:
            return
        
        # 가장 중요한 metric 선택
        metric_counts = self.burst_df['Metric'].value_counts()
        top_metrics = metric_counts.head(4).index.tolist()
        
        if not top_metrics:
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        axes = axes.flatten()
        
        for idx, metric in enumerate(top_metrics[:4]):
            ax = axes[idx]
            
            metric_data = self.burst_df[self.burst_df['Metric'] == metric]
            
            # Well별 분포
            wells = sorted(metric_data['Well'].unique())
            data_by_well = [metric_data[metric_data['Well'] == w]['Value'].values for w in wells]
            
            bp = ax.boxplot(data_by_well, labels=wells, patch_artist=True)
            
            # 박스 색상
            colors = plt.cm.Set3(np.linspace(0, 1, len(bp['boxes'])))
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
            
            ax.set_ylabel('Value', fontweight='bold')
            ax.set_title(f'{metric.replace("_", " ").title()}\n(Distribution by Well)', 
                        fontweight='bold', fontsize=10)
            ax.grid(axis='y', alpha=0.3)
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'burst_key_metrics_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f'    ✓ Saved: burst_key_metrics_distribution.png')

# v3.3 고급 분석
try:
    from mea_advanced_analytics_v33 import AdvancedVisualizer
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False
    print("Warning: mea_advanced_analytics_v33 not found. Advanced analytics disabled.")

# v3.4 전문가급 시각화
try:
    from mea_professional_visualizer_v34 import (
        ProfessionalPerWellAnalyzer,
        ProfessionalSpatialHeatmap,
        ProfessionalDashboard
    )
    HAS_PROFESSIONAL = True
except ImportError:
    HAS_PROFESSIONAL = False
    print("Warning: mea_professional_visualizer_v34 not found. Professional visualizations disabled.")


class OptimizedPipeline:
    """최적화된 통합 파이프라인"""

    def __init__(self, input_dir, output_base):
        """
        Parameters:
        -----------
        input_dir : str or Path
            입력 데이터 디렉토리 (CSV 파일 또는 Excel 파일)
        output_base : str or Path
            출력 기본 디렉토리
        """
        self.input_dir = Path(input_dir)
        self.output_base = Path(output_base)
        self.output_base.mkdir(parents=True, exist_ok=True)

        self.processed_dir = self.output_base / 'processed'
        self.analysis_dir = self.output_base / 'analysis'

        # 디렉토리 생성
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.df = None

    def run(self, mode='full', skip_preprocessing=False):
        """
        전체 파이프라인 실행

        Parameters:
        -----------
        mode : str
            분석 모드 선택
            - 'basic': 기본 분석만 (v3.2 + v3.5 burst)
            - 'advanced': 기본 + 고급 분석 (v3.2 + v3.3 + v3.5)
            - 'professional': 기본 + 전문가급 (v3.2 + v3.4 + v3.5)
            - 'full': 모든 분석 (v3.2 + v3.3 + v3.4 + v3.5) [기본값]

        skip_preprocessing : bool
            True면 전처리를 건너뛰고 기존 processed 폴더 사용
            (이미 전처리된 데이터가 있을 때 유용)
        """
        print('='*80)
        print('MEA OPTIMIZED INTEGRATED PIPELINE')
        print('='*80)
        print(f'\nInput: {self.input_dir}')
        print(f'Output: {self.output_base}')
        print(f'Mode: {mode.upper()}')
        print(f'Timestamp: {self.timestamp}')
        print('='*80)

        # ====================================================================
        # STAGE 1: 전처리 (선택사항)
        # ====================================================================
        if not skip_preprocessing:
            print('\n' + '='*80)
            print('STAGE 1: DATA PREPROCESSING')
            print('='*80)

            pipeline = MEAPipeline(log_level='INFO')
            stats = pipeline.run_full_pipeline(
                input_dir=self.input_dir,
                output_dir=self.processed_dir,
                keep_intermediate=False
            )

            print(f"\n✓ Preprocessing complete: {stats['elapsed_seconds']:.2f}s")
        else:
            print('\n⏩ Skipping preprocessing (using existing processed data)')
            stats = {'elapsed_seconds': 0, 'input_format': 'N/A', 'stages_executed': []}

        # ====================================================================
        # STAGE 2: 데이터 로딩
        # ====================================================================
        print('\n' + '='*80)
        print('STAGE 2: DATA LOADING')
        print('='*80)

        loader = OptimizedFormatLoader(self.processed_dir)
        self.df = loader.load_all()

        if self.df.empty:
            print('❌ No data loaded!')
            return self

        print(f'✓ Loaded {len(self.df)} rows from {len(self.df["Well"].unique())} wells')

        # ====================================================================
        # STAGE 3: 기본 분석 (v3.2 + v3.5 Burst Enhancements)
        # ====================================================================
        print('\n' + '='*80)
        print('STAGE 3: BASIC ANALYSES (v3.2 + v3.5 Burst Enhancements)')
        print('='*80)
        print('\nRunning:')
        print('  • Per-well analysis (enhanced color codes)')
        print('  • Spontaneous activity (baseline only)')
        print('  • Light response (+ per-well + burst)')
        print('  • Drug effects (+ light response + burst)')
        print('  • Enhanced dashboard')
        print('  • Combined Excel & detailed report')

        # Combined Excel
        combined_path = self.analysis_dir / 'COMBINED_DATA.xlsx'
        combiner = CombinedExcelCreator(self.processed_dir, combined_path)
        combiner.create()

        # Per-well analysis
        perwell = PerWellAnalyzerEnhanced(self.df, self.analysis_dir)
        perwell.analyze()

        # Spontaneous activity
        spont = SpontaneousAnalyzer(self.df, self.analysis_dir)
        spont.analyze().visualize()

        # Light response
        light = LightResponseAnalyzer(self.df, self.analysis_dir)
        light.analyze().visualize()

        # Drug effects
        drug = DrugEffectAnalyzer(self.df, self.analysis_dir)
        drug.analyze().visualize()

        # Burst analysis (NEW SECTION)
        burst = BurstAnalyzer(self.df, self.analysis_dir)
        burst.analyze().visualize()

        # Enhanced dashboard
        dashboard_path = self.analysis_dir / 'MASTER_DASHBOARD.png'
        dashboard = EnhancedDashboard(self.analysis_dir, dashboard_path)
        dashboard.create()

        # Detailed report
        report_path = self.analysis_dir / f'DETAILED_REPORT_{self.timestamp}.txt'
        report_gen = DetailedReportGenerator(self.df, self.analysis_dir, report_path)
        report_gen.generate()

        print('\n✓ Basic analyses complete')

        # ====================================================================
        # STAGE 4: 고급 분석 (v3.3) - 선택사항
        # ====================================================================
        if mode in ['advanced', 'full']:
            if HAS_ADVANCED:
                print('\n' + '='*80)
                print('STAGE 4: ADVANCED ANALYTICS (v3.3) 🔬')
                print('='*80)

                visualizer = AdvancedVisualizer(self.df, self.analysis_dir)
                visualizer.run_all_advanced_analyses()

                print('\n✓ Advanced analytics complete')
            else:
                print('\n⚠ Advanced analytics skipped (module not available)')

        # ====================================================================
        # STAGE 5: 전문가급 시각화 (v3.4) - 선택사항
        # ====================================================================
        if mode in ['professional', 'full']:
            if HAS_PROFESSIONAL:
                print('\n' + '='*80)
                print('STAGE 5: PROFESSIONAL VISUALIZATIONS (v3.4) ⭐')
                print('='*80)

                # Professional per-well
                print('\n[PROFESSIONAL] Per-well analysis...')
                perwell_prof = ProfessionalPerWellAnalyzer(self.df, self.analysis_dir)
                for well in sorted(self.df['Well'].unique()):
                    perwell_prof.analyze_well(well)

                # Professional spatial heatmaps
                spatial = ProfessionalSpatialHeatmap(self.df, self.analysis_dir)
                spatial.create_all_heatmaps()

                # Professional dashboard
                dashboard_prof_path = self.analysis_dir / 'MASTER_DASHBOARD_PROFESSIONAL.png'
                dashboard_prof = ProfessionalDashboard(self.df, dashboard_prof_path)
                dashboard_prof.create()

                print('\n✓ Professional visualizations complete')
            else:
                print('\n⚠ Professional visualizations skipped (module not available)')

        # ====================================================================
        # 최종 리포트
        # ====================================================================
        self._generate_final_report(stats, mode)

        # ====================================================================
        # 완료
        # ====================================================================
        print('\n' + '='*80)
        print('🎉 PIPELINE COMPLETE!')
        print('='*80)
        print(f'\nResults: {self.output_base}')
        print('\n📁 Output structure:')
        print(f'  {self.output_base.name}/')

        if not skip_preprocessing:
            print(f'    ├── processed/              (preprocessed data)')

        print(f'    └── analysis/')
        print(f'        ├── 00_per_well/        (enhanced per-well analysis)')
        print(f'        ├── 01_spontaneous/     (baseline activity)')
        print(f'        ├── 02_light_response/  (+ per-well + burst)')
        print(f'        ├── 03_drug_effects/    (+ light + burst)')
        print(f'        ├── 04_burst_analysis/  (burst metrics dedicated)')  # NEW

        if mode in ['advanced', 'full'] and HAS_ADVANCED:
            print(f'        ├── advanced_analytics/ (v3.3 advanced)')

        if mode in ['professional', 'full'] and HAS_PROFESSIONAL:
            print(f'        ├── 00_per_well_professional/')
            print(f'        ├── spatial_heatmaps_professional/')
            print(f'        ├── MASTER_DASHBOARD_PROFESSIONAL.png')

        print(f'        ├── MASTER_DASHBOARD.png ⭐')
        print(f'        ├── COMBINED_DATA.xlsx')
        print(f'        └── DETAILED_REPORT_{self.timestamp}.txt')
        print('='*80)

        return self

    def _generate_final_report(self, preprocessing_stats, mode):
        """최종 리포트 생성"""
        report = []
        report.append('='*80)
        report.append('MEA OPTIMIZED PIPELINE - FINAL REPORT')
        report.append('='*80)
        report.append(f'\nTimestamp: {self.timestamp}')
        report.append(f'Input: {self.input_dir}')
        report.append(f'Output: {self.output_base}')
        report.append(f'Analysis Mode: {mode.upper()}')
        report.append('')

        # Preprocessing
        report.append('STAGE 1 - PREPROCESSING:')
        report.append(f"  Format detected: {preprocessing_stats.get('input_format', 'N/A')}")
        report.append(f"  Stages executed: {', '.join(preprocessing_stats.get('stages_executed', []))}")
        report.append(f"  Processing time: {preprocessing_stats.get('elapsed_seconds', 0):.2f}s")
        report.append('')

        # Basic analyses
        report.append('STAGE 3 - BASIC ANALYSES (v3.2 + v3.5):')
        report.append('  ✓ Per-well analysis (enhanced color codes)')
        report.append('  ✓ Spontaneous activity (baseline only)')
        report.append('  ✓ Light response (+ per-well + burst)')
        report.append('  ✓ Drug effects (+ light response + burst)')
        report.append('  ✓ Burst analysis (dedicated section)')  # NEW
        report.append('  ✓ Enhanced dashboard')
        report.append('  ✓ Combined Excel & detailed report')
        report.append('')

        # Advanced
        if mode in ['advanced', 'full']:
            report.append('STAGE 4 - ADVANCED ANALYTICS (v3.3):')
            if HAS_ADVANCED:
                report.append('  ✓ Connectivity analysis')
                report.append('  ✓ Spatial analysis')
                report.append('  ✓ Hierarchical clustering')
                report.append('  ✓ Advanced visualizations')
            else:
                report.append('  ⚠ Skipped (module not available)')
            report.append('')

        # Professional
        if mode in ['professional', 'full']:
            report.append('STAGE 5 - PROFESSIONAL VISUALIZATIONS (v3.4):')
            if HAS_PROFESSIONAL:
                report.append('  ✓ Nature/Cell/Science style figures')
                report.append('  ✓ Colorblind-friendly palettes')
                report.append('  ✓ Statistical annotations')
                report.append('  ✓ Vector graphics (PDF)')
            else:
                report.append('  ⚠ Skipped (module not available)')
            report.append('')

        report.append('KEY IMPROVEMENTS (vs separate pipelines):')
        report.append('  • Eliminated redundancy between v32 and v35')
        report.append('  • Single execution for all analyses')
        report.append('  • Flexible mode selection')
        report.append('  • Option to skip preprocessing')
        report.append('  • Reduced code duplication')
        report.append('')

        report.append('PUBLICATION READY:')
        report.append('  • Use MASTER_DASHBOARD_PROFESSIONAL.pdf for vector graphics')
        report.append('  • Colorblind-safe palettes included')
        report.append('  • Follows high-tier journal guidelines')
        report.append('  • Complete statistical annotations')
        report.append('='*80)

        report_path = self.output_base / f'FINAL_REPORT_{self.timestamp}.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))

        print(f'\n✓ Final report saved: {report_path.name}')


# ============================================================================
# QUICK RUN FUNCTIONS
# ============================================================================

def run_full_pipeline(input_dir, output_base, mode='full'):
    """
    전체 파이프라인 실행 (전처리 + 분석)

    Parameters:
    -----------
    input_dir : str
        입력 데이터 디렉토리
    output_base : str
        출력 디렉토리
    mode : str
        'basic', 'advanced', 'professional', 'full'
    """
    pipeline = OptimizedPipeline(input_dir, output_base)
    pipeline.run(mode=mode, skip_preprocessing=False)
    return pipeline


def run_analysis_only(processed_dir, output_dir, mode='full'):
    """
    분석만 실행 (전처리 건너뛰기)

    Parameters:
    -----------
    processed_dir : str
        전처리된 데이터 디렉토리
    output_dir : str
        분석 결과 출력 디렉토리
    mode : str
        'basic', 'advanced', 'professional', 'full'
    """
    # processed_dir를 input으로 사용
    pipeline = OptimizedPipeline(
        input_dir=processed_dir,  # 이미 processed 폴더
        output_base=output_dir
    )
    # processed 폴더를 그대로 사용
    pipeline.processed_dir = Path(processed_dir)
    pipeline.run(mode=mode, skip_preprocessing=True)
    return pipeline


# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    # =======================================================================
    # 사용 예시 1: 전체 파이프라인 (전처리 + 분석)
    # =======================================================================
    PROJECT_NUM = "7-1"  # 프로젝트 번호 변경

    input_dir = rf"D:\MyProjects\#{PROJECT_NUM}"
    output_base = rf"D:\MyProjects\#{PROJECT_NUM}\output"

    pipeline = OptimizedPipeline(
        input_dir=input_dir,
        output_base=output_base
    )

    # 모든 분석 실행 (권장)
    pipeline.run(mode='full')

    # 또는 기본 분석만
    # pipeline.run(mode='basic')

    # =======================================================================
    # 사용 예시 2: 이미 전처리된 데이터로 분석만 실행
    # =======================================================================
    # processed_dir = rf"D:\MyProjects\#{PROJECT_NUM}\output\processed"
    # analysis_dir = rf"D:\MyProjects\#{PROJECT_NUM}\analysis_new"
    #
    # run_analysis_only(processed_dir, analysis_dir, mode='full')
