"""
MEA Excel 데이터 직관적 시각화 도구
====================================
improved_*.xlsx 형식의 MEA 데이터 전용 시각화

데이터 형식:
- Metadata 시트: PLATE_ID, DRUG, CONCENTRATION_MM, PLATING_DAY 등
- Template 시트: Metric × Wells (행렬 형식)
- Well_Info 시트: Well 상세 정보

사용법:
    python mea_excel_visualizer.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Optional, List, Dict
import warnings
warnings.filterwarnings('ignore')

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False


class MEAExcelVisualizer:
    """Excel 형식 MEA 데이터 시각화 클래스"""
    
    # 논문 품질 색상 팔레트
    COLORS = {
        'control': '#1f77b4',      # Professional Blue
        'drug': '#d62728',         # Professional Red
        'drug_alt': '#ff7f0e',     # Orange
        'background': '#fafafa',   # Light Gray
        'grid': '#e0e0e0',         # Grid Gray
        'text': '#333333'          # Dark Gray
    }
    
    def __init__(self, input_dir: str, output_dir: str):
        """
        Args:
            input_dir: Excel 파일들이 있는 디렉토리
            output_dir: 결과 저장 디렉토리
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.data_list = []  # 모든 파일의 데이터
        self.df_long = None  # Long format 데이터프레임
        
    def load_excel_files(self) -> bool:
        """디렉토리에서 모든 Excel 파일 로딩"""
        print('\n' + '='*80)
        print('📂 Excel 파일 로딩 중...')
        print('='*80)
        
        if not self.input_dir.exists():
            print(f'❌ 디렉토리를 찾을 수 없습니다: {self.input_dir}')
            return False
        
        # Excel 파일 검색
        excel_files = list(self.input_dir.rglob('*.xlsx'))
        
        # improved_로 시작하는 파일만 (필요시 수정)
        improved_files = [f for f in excel_files if f.name.startswith('improved_')]
        if improved_files:
            excel_files = improved_files
        
        if not excel_files:
            print(f'❌ Excel 파일을 찾을 수 없습니다: {self.input_dir}')
            return False
        
        print(f'✓ {len(excel_files)}개 Excel 파일 발견')
        
        # 파일 로딩
        for i, file in enumerate(excel_files, 1):
            print(f'\n[{i}/{len(excel_files)}] {file.name}')
            try:
                data = self._load_single_excel(file)
                if data is not None:
                    self.data_list.append(data)
                    print(f'  ✓ 로딩 완료')
            except Exception as e:
                print(f'  ❌ 로딩 실패: {e}')
        
        if not self.data_list:
            print('\n❌ 유효한 데이터 파일이 없습니다')
            return False
        
        print(f'\n✅ 총 {len(self.data_list)}개 파일 로딩 완료!')
        return True
    
    def _load_single_excel(self, file_path: Path) -> Optional[Dict]:
        """단일 Excel 파일 로딩"""
        xl_file = pd.ExcelFile(file_path)
        
        # 필수 시트 확인
        if 'Metadata' not in xl_file.sheet_names or 'Template' not in xl_file.sheet_names:
            print(f'  ⚠️  필수 시트(Metadata, Template)가 없습니다')
            return None
        
        # Metadata 로딩
        metadata = pd.read_excel(file_path, sheet_name='Metadata').iloc[0].to_dict()
        
        # Template 로딩 (Metric × Wells)
        template = pd.read_excel(file_path, sheet_name='Template')
        
        return {
            'file_name': file_path.name,
            'metadata': metadata,
            'template': template
        }
    
    def process_data(self) -> bool:
        """데이터를 Long format으로 변환"""
        print('\n' + '='*80)
        print('🔧 데이터 변환 중...')
        print('='*80)
        
        if not self.data_list:
            print('❌ 로딩된 데이터가 없습니다')
            return False
        
        all_rows = []
        
        for data in self.data_list:
            metadata = data['metadata']
            template = data['template']
            
            # Template을 Long format으로 변환
            # Metric 컬럼을 제외한 나머지가 Well 이름
            metric_col = 'Metric'
            well_cols = [col for col in template.columns if col != metric_col]
            
            for _, row in template.iterrows():
                metric_name = row[metric_col]
                
                for well in well_cols:
                    value = row[well]
                    
                    # 각 데이터 포인트 생성
                    data_point = {
                        'File': data['file_name'],
                        'Well': well,
                        'Metric': metric_name,
                        'Value': value,
                        # Metadata 추가
                        'PLATE_ID': metadata.get('PLATE_ID', 'Unknown'),
                        'DRUG': metadata.get('DRUG', 'Unknown'),
                        'CONCENTRATION_MM': metadata.get('CONCENTRATION_MM', 0),
                        'EXP_TYPE': metadata.get('EXP_TYPE', 'Unknown'),
                        'PLATING_DAY': metadata.get('PLATING_DAY', None),
                        'BASE_STIM': metadata.get('BASE_STIM', 'Unknown'),
                    }
                    
                    all_rows.append(data_point)
        
        self.df_long = pd.DataFrame(all_rows)
        
        # DIV 계산 (PLATING_DAY가 있는 경우)
        if 'PLATING_DAY' in self.df_long.columns and self.df_long['PLATING_DAY'].notna().any():
            # 파일명에서 날짜 정보 추출 시도
            self.df_long['DIFF_DAY'] = 0  # 기본값
        else:
            self.df_long['DIFF_DAY'] = 0
        
        print(f'✅ 변환 완료!')
        print(f'  - 총 데이터 포인트: {len(self.df_long):,}')
        print(f'  - Wells: {sorted(self.df_long["Well"].unique())}')
        print(f'  - Metrics: {len(self.df_long["Metric"].unique())}개')
        print(f'  - Drugs: {list(self.df_long["DRUG"].unique())}')
        
        return True
    
    def generate_summary_report(self):
        """요약 리포트 생성"""
        print('\n' + '='*80)
        print('📋 데이터 요약 리포트')
        print('='*80)
        
        if self.df_long is None or len(self.df_long) == 0:
            print('❌ 변환된 데이터가 없습니다')
            return
        
        df = self.df_long
        
        print(f'\n📊 전체 데이터')
        print(f'  - 파일 수: {len(self.data_list)}')
        print(f'  - 데이터 포인트: {len(df):,}')
        
        print(f'\n🧪 실험 조건')
        print(f'  - Plate IDs: {list(df["PLATE_ID"].unique())}')
        print(f'  - 약물: {list(df["DRUG"].unique())}')
        
        if 'CONCENTRATION_MM' in df.columns:
            print(f'  - 농도 (mM): {sorted(df["CONCENTRATION_MM"].unique())}')
        
        print(f'\n🔬 Wells')
        print(f'  - 총 Wells: {len(df["Well"].unique())}개')
        print(f'  - Well 목록: {sorted(df["Well"].unique())}')
        
        print(f'\n📈 Metrics ({len(df["Metric"].unique())}개)')
        for i, metric in enumerate(sorted(df["Metric"].unique())[:10], 1):
            print(f'  {i:2d}. {metric}')
        if len(df["Metric"].unique()) > 10:
            print(f'  ... 외 {len(df["Metric"].unique())-10}개')
        
        print(f'\n💊 약물별 데이터')
        for drug in sorted(df["DRUG"].unique()):
            count = len(df[df["DRUG"] == drug])
            wells = len(df[df["DRUG"] == drug]["Well"].unique())
            print(f'  - {drug}: {count:,} 데이터 포인트, {wells}개 Wells')
        
        print('\n' + '='*80)
    
    def create_drug_comparison_plot(self, metric: str = 'mean_firing_rate_hz'):
        """약물 효과 비교 플롯"""
        print(f'\n📊 Drug Comparison Plot 생성 중... ({metric})')
        
        df = self.df_long
        df_metric = df[df['Metric'] == metric].copy()
        
        if len(df_metric) == 0:
            print(f'⚠️  {metric} 데이터가 없습니다')
            available = df['Metric'].unique()[:5]
            print(f'   사용 가능: {list(available)}...')
            return
        
        # Drug별 통계
        drug_stats = df_metric.groupby('DRUG')['Value'].agg(['mean', 'std', 'sem']).reset_index()
        
        # Control/None을 왼쪽에, Drug response를 오른쪽에 배치하기 위한 정렬
        def sort_key(drug):
            drug_str = str(drug).upper()
            if 'CONTROL' in drug_str or 'NONE' in drug_str:
                return (0, drug_str)  # Control은 0으로 먼저 정렬
            else:
                return (1, drug_str)  # Drug은 1로 나중에 정렬
        
        drug_stats = drug_stats.sort_values('DRUG', key=lambda x: x.apply(sort_key)).reset_index(drop=True)
        
        # 플롯 생성
        fig, ax = plt.subplots(figsize=(10, 6), facecolor=self.COLORS['background'])
        
        x_pos = range(len(drug_stats))
        colors = [self.COLORS['control'] if 'CONTROL' in str(drug).upper() or 'NONE' in str(drug).upper() 
                 else self.COLORS['drug'] for drug in drug_stats['DRUG']]
        
        # Bar plot
        bars = ax.bar(x_pos, drug_stats['mean'], 
                     yerr=drug_stats['sem'], 
                     color=colors, alpha=0.8, 
                     capsize=10, edgecolor='black', linewidth=1.5)
        
        # 개별 데이터 포인트 표시
        for i, drug in enumerate(drug_stats['DRUG']):
            drug_data = df_metric[df_metric['DRUG'] == drug]['Value']
            x_jitter = np.random.normal(i, 0.04, len(drug_data))
            ax.scatter(x_jitter, drug_data, alpha=0.4, s=50, 
                      color='black', edgecolors='white', linewidths=0.5)
        
        # 스타일링
        ax.set_xticks(x_pos)
        ax.set_xticklabels(drug_stats['DRUG'], fontsize=11, fontweight='bold')
        ax.set_ylabel(metric.replace('_', ' ').title(), fontsize=13, fontweight='bold')
        ax.set_title(f'{metric.replace("_", " ").title()} by Drug Treatment',
                    fontsize=15, fontweight='bold', pad=15)
        ax.grid(axis='y', alpha=0.3, linestyle='--', color=self.COLORS['grid'])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_facecolor('white')
        
        plt.tight_layout()
        
        # 저장
        output_file = self.output_dir / f'drug_comparison_{metric}.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor=self.COLORS['background'])
        plt.close()
        
        print(f'✓ 저장: {output_file.name}')
    
    def create_well_comparison_plot(self, metric: str = 'mean_firing_rate_hz'):
        """Well별 비교 플롯"""
        print(f'\n📊 Well Comparison Plot 생성 중... ({metric})')
        
        df = self.df_long
        df_metric = df[df['Metric'] == metric].copy()
        
        if len(df_metric) == 0:
            print(f'⚠️  {metric} 데이터가 없습니다')
            return
        
        # 플롯 생성
        fig, ax = plt.subplots(figsize=(14, 6), facecolor=self.COLORS['background'])
        
        # Drug별로 색상 구분
        wells = sorted(df_metric['Well'].unique())
        
        for well in wells:
            df_well = df_metric[df_metric['Well'] == well]
            
            for drug in df_well['DRUG'].unique():
                df_drug_well = df_well[df_well['DRUG'] == drug]
                
                color = (self.COLORS['control'] if 'CONTROL' in str(drug).upper() or 'NONE' in str(drug).upper() 
                        else self.COLORS['drug'])
                
                value = df_drug_well['Value'].values[0] if len(df_drug_well) > 0 else 0
                
                ax.bar(well, value, color=color, alpha=0.8, 
                      edgecolor='black', linewidth=1)
        
        # 스타일링
        ax.set_xlabel('Wells', fontsize=13, fontweight='bold')
        ax.set_ylabel(metric.replace('_', ' ').title(), fontsize=13, fontweight='bold')
        ax.set_title(f'{metric.replace("_", " ").title()} by Well',
                    fontsize=15, fontweight='bold', pad=15)
        ax.grid(axis='y', alpha=0.3, linestyle='--', color=self.COLORS['grid'])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_facecolor('white')
        
        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=self.COLORS['control'], label='Control'),
            Patch(facecolor=self.COLORS['drug'], label='Drug')
        ]
        ax.legend(handles=legend_elements, fontsize=11, frameon=True, 
                 fancybox=True, shadow=True)
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # 저장
        output_file = self.output_dir / f'well_comparison_{metric}.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor=self.COLORS['background'])
        plt.close()
        
        print(f'✓ 저장: {output_file.name}')
    
    def create_heatmap(self, metric: str = 'mean_firing_rate_hz'):
        """Well × Drug 히트맵"""
        print(f'\n📊 Heatmap 생성 중... ({metric})')
        
        df = self.df_long
        df_metric = df[df['Metric'] == metric].copy()
        
        if len(df_metric) == 0:
            print(f'⚠️  {metric} 데이터가 없습니다')
            return
        
        # Pivot 테이블
        pivot = df_metric.pivot_table(
            values='Value',
            index='Well',
            columns='DRUG',
            aggfunc='mean'
        )
        
        # 플롯 생성
        fig, ax = plt.subplots(figsize=(10, 8), facecolor=self.COLORS['background'])
        
        sns.heatmap(pivot, annot=True, fmt='.3f', cmap='RdYlBu_r',
                   cbar_kws={'label': metric.replace('_', ' ').title()},
                   linewidths=1, linecolor='white', ax=ax)
        
        ax.set_title(f'{metric.replace("_", " ").title()} Heatmap: Well × Drug',
                    fontsize=15, fontweight='bold', pad=15)
        ax.set_xlabel('Drug Treatment', fontsize=13, fontweight='bold')
        ax.set_ylabel('Wells', fontsize=13, fontweight='bold')
        
        plt.tight_layout()
        
        # 저장
        output_file = self.output_dir / f'heatmap_{metric}.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor=self.COLORS['background'])
        plt.close()
        
        print(f'✓ 저장: {output_file.name}')
    
    def create_all_plots(self, metrics: Optional[List[str]] = None):
        """모든 플롯 생성"""
        if metrics is None:
            # 주요 Metric 자동 선택
            all_metrics = self.df_long['Metric'].unique()
            key_metrics = [
                'mean_firing_rate_hz',
                'number_of_spikes',
                'weighted_mean_firing_rate_hz',
                'number_of_active_electrodes'
            ]
            metrics = [m for m in key_metrics if m in all_metrics]
            
            if not metrics:
                metrics = list(all_metrics[:3])
        
        print('\n' + '='*80)
        print('🎨 플롯 생성 시작')
        print('='*80)
        
        for metric in metrics:
            print(f'\n--- {metric} ---')
            try:
                self.create_drug_comparison_plot(metric)
                self.create_well_comparison_plot(metric)
                self.create_heatmap(metric)
            except Exception as e:
                print(f'❌ {metric} 플롯 생성 실패: {e}')
                import traceback
                traceback.print_exc()
        
        print('\n' + '='*80)
        print('✅ 모든 플롯 생성 완료!')
        print('='*80)
    
    def run(self, metrics: Optional[List[str]] = None):
        """전체 파이프라인 실행"""
        print('\n' + '='*80)
        print('🚀 MEA Excel 데이터 시각화 시작')
        print('='*80)
        
        # 1. Excel 파일 로딩
        if not self.load_excel_files():
            return False
        
        # 2. 데이터 변환
        if not self.process_data():
            return False
        
        # 3. 요약 리포트
        self.generate_summary_report()
        
        # 4. 플롯 생성
        self.create_all_plots(metrics)
        
        print(f'\n📁 결과 저장 위치: {self.output_dir}')
        print('\n' + '='*80)
        print('🎉 완료!')
        print('='*80)
        
        return True


# ============================================================================
# 간편 실행 함수
# ============================================================================

def quick_visualize(input_dir: str, output_dir: str, metrics: Optional[List[str]] = None):
    """
    한 줄로 실행
    
    Args:
        input_dir: Excel 파일들이 있는 디렉토리
        output_dir: 결과 저장 디렉토리
        metrics: 시각화할 Metric 리스트
    """
    viz = MEAExcelVisualizer(input_dir, output_dir)
    viz.run(metrics)


# ============================================================================
# 메인 실행
# ============================================================================

if __name__ == '__main__':
    # 경로 설정
    INPUT_DIR = r"D:\MyProjects\#7-1\output\processed"
    OUTPUT_DIR = r"D:\MyProjects\#7-1\output\excel_plots"
    
    # 특정 Metric만 시각화
    METRICS = [
        'mean_firing_rate_hz',
        'number_of_spikes',
        'weighted_mean_firing_rate_hz',
        'number_of_active_electrodes'
    ]
    
    # 실행
    quick_visualize(INPUT_DIR, OUTPUT_DIR, METRICS)
