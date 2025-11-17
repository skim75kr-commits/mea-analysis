"""
MEA Complete Analyzer v3.5 - ENHANCED BURST METRICS EDITION
===========================================================
v3.5: Enhanced Burst Analysis (Number, Duration, Frequency)

Complete Features:
- v3.2: Standard analyses
- v3.3: Advanced analytics (connectivity, spatial, clustering)
- v3.4: High-tier journal style (Nature/Cell/Science)
- v3.5: ⭐ Enhanced burst metrics (number, duration, frequency)

New in v3.5:
- Number of bursts analysis added
- Burst duration analysis added
- 9-panel per-well comprehensive figures (was 6-panel)
- Enhanced burst metrics in all reports
- Detailed burst statistics in spontaneous, light response, and drug effects
"""

from pathlib import Path
from datetime import datetime

# Standard v3.2 imports (with v3.5 burst enhancements)
from mea_auto_analyzer_v32 import (
    OptimizedFormatLoader,
    SpontaneousAnalyzer,
    LightResponseAnalyzer,
    DrugEffectAnalyzer,
    CombinedExcelCreator,
    DetailedReportGenerator
)

# Advanced v3.3 imports
from mea_advanced_analytics_v33 import AdvancedVisualizer

# Professional v3.4 imports
from mea_professional_visualizer_v34 import (
    ProfessionalPerWellAnalyzer,
    ProfessionalSpatialHeatmap,
    ProfessionalDashboard
)


class CompleteAnalyzerV35:
    """통합 분석기 v3.5 - Enhanced Burst Metrics Edition"""

    def __init__(self, input_dir, output_dir):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.df = None
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    def run(self, mode='full'):
        """
        분석 실행

        Parameters:
        -----------
        mode : str
            'basic' - 기본 분석만 (v3.2 + v3.5 burst enhancements)
            'advanced' - 기본 + 고급 분석 (v3.2 + v3.3 + v3.5)
            'professional' - 기본 + 전문가급 스타일 (v3.2 + v3.4 + v3.5)
            'full' - 모든 분석 (v3.2 + v3.3 + v3.4 + v3.5) [기본값]
        """
        print('='*80)
        print('MEA COMPLETE ANALYZER v3.5 - ENHANCED BURST METRICS EDITION')
        print('='*80)
        print(f'\nMode: {mode.upper()}')
        print('\nFeatures:')
        print('  v3.2: ✓ Standard analyses')
        print('  v3.3: ✓ Advanced analytics (connectivity, clustering)')
        print('  v3.4: ✓ Professional style (Nature/Cell/Science)')
        print('  v3.5: ⭐ Enhanced burst metrics (number, duration, frequency)')
        print('='*80)

        # Load data
        print('\n[LOAD] Loading data...')
        loader = OptimizedFormatLoader(self.input_dir)
        self.df = loader.load_all()

        if self.df.empty:
            print('❌ No data loaded!')
            return

        print(f'  ✓ Loaded {len(self.df)} rows from {len(self.df["Well"].unique())} wells')

        # Combined Excel
        combined_path = self.output_dir / 'COMBINED_DATA.xlsx'
        combiner = CombinedExcelCreator(self.input_dir, combined_path)
        combiner.create()

        # ====================================================================
        # STAGE 1: BASIC ANALYSES (v3.2 + v3.5 BURST ENHANCEMENTS)
        # ====================================================================
        if mode in ['basic', 'advanced', 'professional', 'full']:
            print('\n' + '='*80)
            print('STAGE 1: BASIC ANALYSES (v3.2 + v3.5 Burst Enhancements)')
            print('='*80)
            print('\nv3.5 Enhancements:')
            print('  ⭐ Number of bursts analysis')
            print('  ⭐ Burst duration analysis')
            print('  ⭐ 9-panel per-well figures (was 6-panel)')
            print('  ⭐ Enhanced burst statistics in all reports')

            # Spontaneous (with enhanced burst metrics)
            spont = SpontaneousAnalyzer(self.df, self.output_dir)
            spont.analyze().visualize()

            # Light response (with burst number & duration)
            light = LightResponseAnalyzer(self.df, self.output_dir)
            light.analyze().visualize()

            # Drug effects (with burst number & duration)
            drug = DrugEffectAnalyzer(self.df, self.output_dir)
            drug.analyze().visualize()

            # Report (with enhanced burst statistics)
            report_path = self.output_dir / f'DETAILED_REPORT_{self.timestamp}.txt'
            report_gen = DetailedReportGenerator(self.df, self.output_dir, report_path)
            report_gen.generate()

        # ====================================================================
        # STAGE 2: ADVANCED ANALYTICS (v3.3)
        # ====================================================================
        if mode in ['advanced', 'full']:
            print('\n' + '='*80)
            print('STAGE 2: ADVANCED ANALYTICS (v3.3) 🔬')
            print('='*80)

            visualizer = AdvancedVisualizer(self.df, self.output_dir)
            visualizer.run_all_advanced_analyses()

        # ====================================================================
        # STAGE 3: PROFESSIONAL STYLE (v3.4)
        # ====================================================================
        if mode in ['professional', 'full']:
            print('\n' + '='*80)
            print('STAGE 3: PROFESSIONAL VISUALIZATIONS (v3.4) ⭐')
            print('='*80)

            # Professional per-well
            print('\n[PROFESSIONAL] Per-well analysis...')
            perwell = ProfessionalPerWellAnalyzer(self.df, self.output_dir)
            for well in sorted(self.df['Well'].unique()):
                perwell.analyze_well(well)

            # Professional spatial heatmaps
            spatial = ProfessionalSpatialHeatmap(self.df, self.output_dir)
            spatial.create_all_heatmaps()

            # Professional dashboard
            dashboard_path = self.output_dir / 'MASTER_DASHBOARD_PROFESSIONAL.png'
            dashboard = ProfessionalDashboard(self.df, dashboard_path)
            dashboard.create()

        # ====================================================================
        # SUMMARY
        # ====================================================================
        print('\n' + '='*80)
        print('✅ ANALYSIS COMPLETE!')
        print('='*80)
        print(f'\nResults: {self.output_dir}')

        if mode in ['basic', 'advanced', 'professional', 'full']:
            print('\n📁 Basic Analyses (v3.2 + v3.5 Burst Enhancements):')
            print('  • 01_spontaneous/')
            print('    ⭐ Number of bursts statistics')
            print('    ⭐ Burst duration statistics')
            print('  • 02_light_response/')
            print('    ⭐ Burst number & duration responses')
            print('  • 03_drug_effects/')
            print('    ⭐ Burst number & duration drug effects')
            print('  • 00_per_well/ (9-panel comprehensive figures)')
            print('    ⭐ Panel 7: Number of Bursts')
            print('    ⭐ Panel 8: Burst Duration')
            print('    ⭐ Panel 9: Burst Metrics Summary')
            print('  • COMBINED_DATA.xlsx')
            print('  • DETAILED_REPORT.txt (enhanced burst stats)')

        if mode in ['advanced', 'full']:
            print('\n🔬 Advanced Analytics (v3.3):')
            print('  • advanced_analytics/')
            print('    - Spatial heatmaps (3 types)')
            print('    - Circular connectivity plot')
            print('    - Time-evolution heatmap')
            print('    - Response distribution pies')
            print('    - Hierarchical clustering')
            print('    - Connectivity heatmaps')

        if mode in ['professional', 'full']:
            print('\n⭐ Professional Style (v3.4):')
            print('  • 00_per_well_professional/')
            print('    - Nature/Cell/Science style')
            print('    - Colorblind-friendly palettes')
            print('    - Statistical annotations')
            print('    - Vector graphics (PDF)')
            print('  • spatial_heatmaps_professional/')
            print('  • MASTER_DASHBOARD_PROFESSIONAL.png (+ PDF)')

        print('\n' + '='*80)
        print('🆕 v3.5 Burst Metrics Summary:')
        print('  • ✓ Burst Frequency (Hz)')
        print('  • ⭐ Number of Bursts (NEW)')
        print('  • ⭐ Burst Duration (ms) (NEW)')
        print('  • ⭐ 9-panel per-well figures (NEW)')
        print('  • ⭐ Enhanced statistics in all reports (NEW)')
        print('='*80)

        print('\n🎓 Publication Tips:')
        print('  • Use *_professional.pdf for vector graphics')
        print('  • Colorblind-safe palettes included')
        print('  • Follows Nature/Cell/Science guidelines')
        print('  • Statistical significance marked')
        print('  • Complete burst analysis metrics available')
        print('='*80)

        return self


# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    # 🔧 여기만 수정하세요!
    PROJECT_NUM = "7-1"  # "#1", "#2", "#7-1" 등으로 변경
    
    # 자동 경로 설정
    input_dir = rf"D:\MyProjects\#{PROJECT_NUM}\output\processed"
    output_dir = rf"D:\MyProjects\#{PROJECT_NUM}\analysis_v35"
    
    # 실행
    analyzer = CompleteAnalyzerV35(
        input_dir=input_dir,
        output_dir=output_dir
    )
    
    analyzer.run(mode='full')  # 모든 기능 실행
