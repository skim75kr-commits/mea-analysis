"""
MEA 직관적 시각화 - 원클릭 실행
================================
데이터를 한눈에 파악할 수 있는 3가지 핵심 플롯 생성

📊 생성되는 플롯:
1. DIV Timeline - 분화시기별 활성도 변화 추이
2. Drug Comparison - 약물 효과 직접 비교
3. DIV-Drug Heatmap - 전체 조건 통합 히트맵

🎯 사용법:
    Jupyter:
        from quick_visual import quick_visual
        quick_visual(r"D:\MyProjects\#7-1")
    
    Python:
        python quick_visual.py

⏱️ 실행시간: ~30초
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime

# 스타일 설정
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = '#fafafa'

# 색상 팔레트 (논문 품질)
COLORS = {
    'control': '#1f77b4',    # Professional Blue
    'drug': '#d62728',       # Professional Red
    'highlight': '#ff7f0e',  # Orange
    'neutral': '#7f7f7f'     # Gray
}


# ============================================================================
# 데이터 로더
# ============================================================================

def auto_load_data(project_path):
    """
    프로젝트 폴더에서 자동으로 데이터 찾아서 로드
    
    검색 순서:
    1. output/processed/*.parquet
    2. output/analysis/*_data.csv
    3. DATASET/**/*.csv
    4. **/*_data.csv
    """
    project = Path(project_path)
    
    print('='*80)
    print('🔍 자동 데이터 검색 중...')
    print('='*80)
    
    # 검색 패턴 (우선순위)
    search_patterns = [
        ('output/processed', '*.parquet'),
        ('output/analysis', '*_data.csv'),
        ('DATASET', '*.csv'),
        ('.', '*_data.csv'),
    ]
    
    for subdir, pattern in search_patterns:
        search_path = project / subdir
        if search_path.exists():
            files = list(search_path.rglob(pattern))
            if files:
                print(f'\n✓ Found {len(files)} files in {subdir}/')
                return _load_files(files)
    
    print('\n❌ No data files found!')
    print('\n💡 Expected structure:')
    print('  D:\\MyProjects\\#7-1\\')
    print('    ├── output\\processed\\')
    print('    ├── output\\analysis\\')
    print('    └── DATASET\\')
    return None


def _load_files(file_list):
    """파일 목록 로드"""
    print(f'\n📂 Loading files...')
    
    df_list = []
    for i, file in enumerate(file_list, 1):
        try:
            if file.suffix == '.parquet':
                df = pd.read_parquet(file)
            else:
                df = pd.read_csv(file)
            
            # 필수 컬럼 체크
            if all(col in df.columns for col in ['Well', 'Metric', 'Value']):
                df_list.append(df)
                if i <= 3:
                    print(f'  {i}. {file.name} ✓')
        except Exception as e:
            if i <= 3:
                print(f'  {i}. {file.name} ✗ ({e})')
    
    if len(file_list) > 3:
        print(f'  ... and {len(file_list)-3} more files')
    
    if not df_list:
        return None
    
    df = pd.concat(df_list, ignore_index=True)
    
    print(f'\n✅ Data loaded:')
    print(f'  • Rows: {len(df):,}')
    print(f'  • Wells: {sorted(df["Well"].unique())}')
    
    if 'DIFF_DAY' in df.columns:
        divs = df['DIFF_DAY'].dropna().unique()
        if len(divs) > 0:
            print(f'  • DIV: {min(divs):.0f} - {max(divs):.0f}')
    
    if 'DRUG' in df.columns:
        drugs = [d for d in df['DRUG'].unique() if pd.notna(d) and d != 'NONE']
        if drugs:
            print(f'  • Drugs: {drugs}')
    
    return df


# ============================================================================
# 시각화 함수
# ============================================================================

def plot_div_timeline(df, output_dir):
    """DIV별 시계열 플롯"""
    print('\n[1/3] DIV Timeline Plot...')
    
    # MFR 데이터만
    mfr = df[df['Metric'] == 'mean_firing_rate_hz'].copy()
    
    if 'DIFF_DAY' not in mfr.columns or mfr['DIFF_DAY'].isna().all():
        print('  ⚠ No DIV data - skipping')
        return
    
    # Well별 평균
    timeline = mfr.groupby(['Well', 'DIFF_DAY', 'DRUG'])['Value'].mean().reset_index()
    
    # 플롯
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for well in sorted(timeline['Well'].unique()):
        well_data = timeline[timeline['Well'] == well]
        
        for drug in well_data['DRUG'].unique():
            drug_data = well_data[well_data['DRUG'] == drug]
            color = COLORS['drug'] if pd.notna(drug) and drug != 'NONE' else COLORS['control']
            label = f"{well} - {drug}" if pd.notna(drug) and drug != 'NONE' else f"{well} - Control"
            
            ax.plot(drug_data['DIFF_DAY'], drug_data['Value'], 
                   'o-', color=color, label=label, linewidth=2, markersize=6, alpha=0.8)
    
    ax.set_xlabel('DIV (Days)', fontsize=12, fontweight='bold')
    ax.set_ylabel('MFR (Hz)', fontsize=12, fontweight='bold')
    ax.set_title('신경 활성도 시간 변화 (DIV Timeline)', fontsize=14, fontweight='bold', pad=15)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', frameon=True, fancybox=True)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(output_dir / '1_DIV_timeline.png', dpi=300, bbox_inches='tight')
    plt.close()
    print('  ✓ Saved: 1_DIV_timeline.png')


def plot_drug_comparison(df, output_dir):
    """약물 효과 비교"""
    print('\n[2/3] Drug Comparison Plot...')
    
    # MFR 데이터
    mfr = df[df['Metric'] == 'mean_firing_rate_hz'].copy()
    
    if 'DRUG' not in mfr.columns:
        print('  ⚠ No drug data - skipping')
        return
    
    # EXP_TYPE이 있으면 사용, 없으면 DRUG로 구분
    if 'EXP_TYPE' in mfr.columns:
        control = mfr[mfr['EXP_TYPE'] == 'CONTROL'].groupby('Well')['Value'].mean()
        drug = mfr[mfr['EXP_TYPE'] == 'DRUG'].groupby('Well')['Value'].mean()
    else:
        control = mfr[mfr['DRUG'].isin(['NONE', 'Control', None])].groupby('Well')['Value'].mean()
        drug = mfr[~mfr['DRUG'].isin(['NONE', 'Control', None])].groupby('Well')['Value'].mean()
    
    if control.empty or drug.empty:
        print('  ⚠ Insufficient data - skipping')
        return
    
    # 퍼센트 변화
    common_wells = control.index.intersection(drug.index)
    pct_change = ((drug[common_wells] - control[common_wells]) / control[common_wells] * 100)
    
    # 플롯
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = np.arange(len(common_wells))
    width = 0.35
    
    ax.bar(x - width/2, control[common_wells], width, label='Control', 
           color=COLORS['control'], alpha=0.8)
    ax.bar(x + width/2, drug[common_wells], width, label='Drug', 
           color=COLORS['drug'], alpha=0.8)
    
    # 변화율 표시
    for i, well in enumerate(common_wells):
        change = pct_change[well]
        y_pos = max(control[well], drug[well]) * 1.05
        color = COLORS['drug'] if change < -20 else COLORS['neutral']
        ax.text(i, y_pos, f'{change:+.0f}%', ha='center', va='bottom', 
               fontsize=9, fontweight='bold', color=color)
    
    ax.set_xticks(x)
    ax.set_xticklabels(common_wells)
    ax.set_ylabel('MFR (Hz)', fontsize=12, fontweight='bold')
    ax.set_title('약물 효과 비교 (Drug Effect Comparison)', fontsize=14, fontweight='bold', pad=15)
    ax.legend(frameon=True, fancybox=True)
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(output_dir / '2_drug_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print('  ✓ Saved: 2_drug_comparison.png')


def plot_heatmap(df, output_dir):
    """DIV-Drug 통합 히트맵"""
    print('\n[3/3] Integrated Heatmap...')
    
    mfr = df[df['Metric'] == 'mean_firing_rate_hz'].copy()
    
    # DIV와 Drug 정보 모두 필요
    if 'DIFF_DAY' not in mfr.columns or 'DRUG' not in mfr.columns:
        print('  ⚠ Missing DIV or Drug data - skipping')
        return
    
    # 조건 조합
    mfr['Condition'] = mfr.apply(
        lambda x: f"DIV{int(x['DIFF_DAY'])}-{x['DRUG']}" 
        if pd.notna(x['DIFF_DAY']) and pd.notna(x['DRUG']) 
        else 'Unknown', axis=1
    )
    
    # Pivot
    pivot = mfr.pivot_table(values='Value', index='Well', columns='Condition', aggfunc='mean')
    
    if pivot.empty:
        print('  ⚠ No data for heatmap - skipping')
        return
    
    # 플롯
    fig, ax = plt.subplots(figsize=(max(12, len(pivot.columns)*0.8), max(6, len(pivot)*0.6)))
    
    sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlBu_r', center=pivot.values.mean(),
                cbar_kws={'label': 'MFR (Hz)'}, linewidths=0.5, linecolor='white',
                ax=ax, vmin=0)
    
    ax.set_title('전체 조건 통합 히트맵 (DIV × Drug Heatmap)', 
                fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Condition (DIV-Drug)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Well', fontsize=12, fontweight='bold')
    
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / '3_integrated_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print('  ✓ Saved: 3_integrated_heatmap.png')


# ============================================================================
# 메인 함수
# ============================================================================

def quick_visual(project_path, output_name='quick_visual'):
    """
    원클릭 시각화
    
    Args:
        project_path: 프로젝트 폴더 (예: "D:\\MyProjects\\#7-1")
        output_name: 출력 폴더명 (기본: 'quick_visual')
    
    Returns:
        성공 여부 (True/False)
    """
    start_time = datetime.now()
    
    print('\n' + '='*80)
    print('🎨 MEA 직관적 시각화 (Quick Visual)')
    print('='*80)
    print(f'\n📂 Project: {project_path}')
    
    # 1. 데이터 로드
    df = auto_load_data(project_path)
    if df is None:
        print('\n❌ Failed to load data')
        return False
    
    # 2. 출력 디렉토리
    output_dir = Path(project_path) / output_name
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f'\n📁 Output: {output_dir}')
    
    # 3. 시각화 생성
    print('\n' + '='*80)
    print('🎨 Creating visualizations...')
    print('='*80)
    
    try:
        plot_div_timeline(df, output_dir)
        plot_drug_comparison(df, output_dir)
        plot_heatmap(df, output_dir)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print('\n' + '='*80)
        print('✅ 완료!')
        print('='*80)
        print(f'\n⏱️  Time: {elapsed:.1f}s')
        print(f'📊 Location: {output_dir}')
        print('\n생성된 파일:')
        print('  1️⃣  1_DIV_timeline.png      - 시간 변화 추이')
        print('  2️⃣  2_drug_comparison.png   - 약물 효과 비교')
        print('  3️⃣  3_integrated_heatmap.png - 통합 히트맵')
        print('\n💡 빠른 판단:')
        print('  • DIV timeline: 분화 과정 정상 진행 확인')
        print('  • Drug comparison: 약물 효과 크기 및 방향')
        print('  • Heatmap: 전체 조건 패턴 파악')
        print('='*80)
        
        return True
        
    except Exception as e:
        print(f'\n❌ Error: {e}')
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 배치 실행 (여러 프로젝트)
# ============================================================================

def quick_visual_batch(project_list):
    """
    여러 프로젝트 일괄 처리
    
    Args:
        project_list: 프로젝트 경로 리스트
    
    Example:
        quick_visual_batch([
            r"D:\\MyProjects\\#1",
            r"D:\\MyProjects\\#2",
            r"D:\\MyProjects\\#7-1"
        ])
    """
    print('\n' + '='*80)
    print(f'🎨 Batch Processing: {len(project_list)} projects')
    print('='*80)
    
    results = {}
    for i, proj in enumerate(project_list, 1):
        print(f'\n[{i}/{len(project_list)}] Processing: {proj}')
        print('-'*80)
        success = quick_visual(proj)
        results[proj] = success
    
    print('\n' + '='*80)
    print('📊 Batch Results:')
    print('='*80)
    for proj, success in results.items():
        status = '✅' if success else '❌'
        proj_name = Path(proj).name
        print(f'  {status} {proj_name}')
    
    success_count = sum(results.values())
    print(f'\n✅ Success: {success_count}/{len(project_list)}')


# ============================================================================
# 실행
# ============================================================================

if __name__ == '__main__':
    # 🔧 여기만 수정!
    PROJECT = r"D:\MyProjects\#7-1"
    
    quick_visual(PROJECT)
    
    # 여러 프로젝트를 한번에 처리하려면:
    # quick_visual_batch([
    #     r"D:\MyProjects\#1",
    #     r"D:\MyProjects\#4-1",
    #     r"D:\MyProjects\#7-1"
    # ])
