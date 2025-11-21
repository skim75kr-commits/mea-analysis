"""
MEA 전체 자동화 파이프라인 v3.2
===============================
전처리 + 분석 (Revised)

개선 사항:
1. Per-well: Fixed color code
2. Spontaneous: Baseline only analysis
3. Light Response: Per-well + Burst analysis added
4. Drug Effects: Light response + Burst effects added
5. Dashboard: Enhanced with mea_dashboard.py style

Usage:
    from mea_full_pipeline_v32 import FullPipeline
    
    pipeline = FullPipeline(
        input_dir=r"D:\MEAdata\#7-1",
        output_base=r"D:\MEAdata\#7-1\output"
    )
    pipeline.run_all()
"""

from pathlib import Path
from datetime import datetime
from mea_pipeline import MEAPipeline
from mea_auto_analyzer_v32 import AutoAnalyzer


class FullPipeline:
    """전처리 + 분석 통합 파이프라인 v3.2"""
    
    def __init__(self, input_dir, output_base):
        self.input_dir = Path(input_dir)
        self.output_base = Path(output_base)
        self.output_base.mkdir(parents=True, exist_ok=True)
        
        self.processed_dir = self.output_base / 'processed'
        self.analysis_dir = self.output_base / 'analysis'
        
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def run_all(self):
        """전체 파이프라인 실행"""
        print('='*80)
        print('MEA FULL AUTOMATION PIPELINE v3.2 - REVISED')
        print('='*80)
        print(f'\nInput: {self.input_dir}')
        print(f'Output: {self.output_base}')
        print(f'Timestamp: {self.timestamp}')
        print('\nRevisions:')
        print('  1. ✓ Per-well: Fixed color code')
        print('  2. ✓ Spontaneous: Baseline only')
        print('  3. ✓ Light Response: Per-well + Burst')
        print('  4. ✓ Drug Effects: Light + Burst')
        print('  5. ✓ Dashboard: Enhanced')
        print('='*80)
        
        # Stage 1: 전처리
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
        
        # Stage 2: 자동 분석 (Revised)
        print('\n' + '='*80)
        print('STAGE 2: AUTOMATIC ANALYSIS (REVISED v3.2)')
        print('='*80)
        
        analyzer = AutoAnalyzer(
            input_dir=self.processed_dir,
            output_dir=self.analysis_dir
        )
        analyzer.run()
        
        # 최종 리포트
        self._generate_final_report(stats)
        
        print('\n' + '='*80)
        print('🎉 FULL PIPELINE COMPLETE!')
        print('='*80)
        print(f'\nOutput structure:')
        print(f'  {self.output_base}/')
        print(f'    ├── processed/              (preprocessed data)')
        print(f'    └── analysis/               (analysis results)')
        print(f'        ├── 00_per_well/        (FIXED color code)')
        print(f'        ├── 01_spontaneous/     (BASELINE ONLY)')
        print(f'        ├── 02_light_response/  (+ PER-WELL + BURST)')
        print(f'        ├── 03_drug_effects/    (+ LIGHT + BURST)')
        print(f'        ├── MASTER_DASHBOARD.png ⭐ (ENHANCED)')
        print(f'        ├── COMBINED_DATA.xlsx')
        print(f'        └── DETAILED_REPORT.txt')
        print('='*80)
        
        return self
    
    def _generate_final_report(self, preprocessing_stats):
        """최종 리포트"""
        report = []
        report.append('='*80)
        report.append('MEA FULL PIPELINE v3.2 - FINAL REPORT')
        report.append('='*80)
        report.append(f'\nTimestamp: {self.timestamp}')
        report.append(f'Input: {self.input_dir}')
        report.append(f'Output: {self.output_base}')
        report.append('')
        report.append('STAGE 1 - PREPROCESSING:')
        report.append(f"  Format detected: {preprocessing_stats.get('input_format', 'N/A')}")
        report.append(f"  Stages executed: {', '.join(preprocessing_stats.get('stages_executed', []))}")
        report.append(f"  Processing time: {preprocessing_stats.get('elapsed_seconds', 0):.2f}s")
        report.append('')
        report.append('STAGE 2 - ANALYSIS (REVISED v3.2):')
        report.append('  ✓ Per-well analysis (FIXED color code)')
        report.append('  ✓ Spontaneous activity (BASELINE ONLY)')
        report.append('  ✓ Light response (+ PER-WELL + BURST)')
        report.append('  ✓ Drug effects (+ LIGHT RESPONSE + BURST)')
        report.append('  ✓ Master dashboard (ENHANCED)')
        report.append('  ✓ Combined Excel')
        report.append('  ✓ Detailed report')
        report.append('')
        report.append('REVISIONS in v3.2:')
        report.append('  🔧 Fixed per-well bargraph color codes')
        report.append('  🔧 Confirmed spontaneous analysis uses baseline only')
        report.append('  🆕 Added per-well analysis to light response')
        report.append('  🆕 Added burst analysis to light response')
        report.append('  🆕 Added light response drug effects')
        report.append('  🆕 Added burst drug effects')
        report.append('  ⭐ Enhanced dashboard (mea_dashboard.py style)')
        report.append('')
        report.append('OUTPUT LOCATIONS:')
        report.append(f"  Processed data: {self.processed_dir}")
        report.append(f"  Analysis results: {self.analysis_dir}")
        report.append('')
        report.append('KEY FILES:')
        report.append('  📊 MASTER_DASHBOARD.png - Enhanced comprehensive visualization')
        report.append('  📊 COMBINED_DATA.xlsx - All data in one file')
        report.append('  📄 DETAILED_REPORT.txt - Comprehensive statistics & findings')
        report.append('')
        report.append('ANALYSIS BREAKDOWN:')
        report.append('  00_per_well/')
        report.append('    - Each well folder contains:')
        report.append('      • {well}_data.csv (all raw data)')
        report.append('      • {well}_light_response.csv (light response metrics)')
        report.append('      • {well}_drug_effect.csv (drug effect metrics)')
        report.append('      • summary.txt (text summary)')
        report.append('      • {well}_comprehensive.png (6-panel figure with FIXED colors)')
        report.append('')
        report.append('  01_spontaneous/')
        report.append('    - spontaneous_activity.csv (BASELINE data only)')
        report.append('    - spontaneous_report.xlsx')
        report.append('    - fig1_mfr_by_well.png')
        report.append('')
        report.append('  02_light_response/')
        report.append('    - light_response.csv (overall response)')
        report.append('    - light_response_per_well.csv (NEW: per-well breakdown)')
        report.append('    - light_response_burst.csv (NEW: burst analysis)')
        report.append('    - light_response_report.xlsx')
        report.append('    - fig1_light_response_comprehensive.png')
        report.append('')
        report.append('  03_drug_effects/')
        report.append('    - baseline_drug_effects.csv (baseline effects)')
        report.append('    - light_response_modulation.csv (NEW: light modulation)')
        report.append('    - burst_drug_effects.csv (NEW: burst effects)')
        report.append('    - drug_effects_report.xlsx')
        report.append('    - fig1_drug_effects_comprehensive.png')
        report.append('='*80)
        
        report_path = self.output_base / f'FINAL_REPORT_{self.timestamp}.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        print('\n' + '\n'.join(report[-20:]))  # Print last 20 lines
        print(f'\n✓ Final report saved: {report_path.name}')


# ============================================================================
# QUICK RUN FUNCTIONS
# ============================================================================

def quick_run(input_dir, output_base):
    """빠른 실행"""
    pipeline = FullPipeline(input_dir, output_base)
    pipeline.run_all()


def preprocess_only(input_dir, output_dir):
    """전처리만"""
    from mea_pipeline import MEAPipeline
    pipeline = MEAPipeline()
    pipeline.run_full_pipeline(
        input_dir=Path(input_dir),
        output_dir=Path(output_dir)
    )


def analyze_only(input_dir, output_dir):
    """분석만 (v3.2)"""
    analyzer = AutoAnalyzer(input_dir, output_dir)
    analyzer.run()


# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    # 🔧 여기만 수정하세요!
    PROJECT_NUM = "7-1"  # "1", "2", "4-1", "7-1" 등으로 변경
    
    # 자동 경로 설정
    input_dir = rf"D:\MyProjects\#{PROJECT_NUM}"
    output_base = rf"D:\MyProjects\#{PROJECT_NUM}\output"
    
    # 실행
    pipeline = FullPipeline(
        input_dir=input_dir,
        output_base=output_base
    )
    pipeline.run_all()