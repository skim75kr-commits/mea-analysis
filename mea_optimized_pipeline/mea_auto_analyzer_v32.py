"""
MEA Automatic Analyzer v3.2 - REVISED
=======================================
개선 사항:
1. 00_per_well: bargraph color code 수정
2. 01_spontaneous: baseline만 분석하도록 명확화
3. 02_light_response: per-well 분석 + burst 분석 추가
4. 03_drug_effects: light response & burst drug effect 추가
5. Dashboard: 더 포괄적인 시각화

Usage:
    from mea_auto_analyzer_v32 import AutoAnalyzer
    
    analyzer = AutoAnalyzer(
        input_dir=r"D:\MEAdata\#7-1\improved",
        output_dir=r"D:\MEAdata\#7-1\analysis"
    )
    analyzer.run()
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


# ============================================================================
# DATA LOADER
# ============================================================================
class OptimizedFormatLoader:
    """최적화 포맷 로더"""
    
    def __init__(self, input_dir):
        self.input_dir = Path(input_dir)
        self.files = []
        
    def load_all(self):
        """모든 파일 로드"""
        self.files = list(self.input_dir.glob('*.xlsx'))
        self.files = [f for f in self.files if not f.name.startswith('~$')]
        
        print(f"Found {len(self.files)} files")
        
        if len(self.files) == 0:
            print("  ❌ No Excel files found!")
            print(f"  Searched in: {self.input_dir}")
            return pd.DataFrame()
        
        all_data = []
        
        for file_path in self.files:
            try:
                df_meta = pd.read_excel(file_path, sheet_name='Metadata')
                df_template = pd.read_excel(file_path, sheet_name='Template')
                df_well = pd.read_excel(file_path, sheet_name='Well_Info')
                
                metadata = df_meta.iloc[0].to_dict()
                
                rows = self._to_long_format(df_template, df_well, metadata, file_path.stem)
                all_data.extend(rows)
                
            except Exception as e:
                print(f"  ⚠ Warning: {file_path.name}: {e}")
                continue
        
        if len(all_data) == 0:
            print("  ❌ No data loaded from any files!")
            print("  Please check:")
            print("    1. Files have correct sheets: 'Metadata', 'Template', 'Well_Info'")
            print("    2. Data format is correct")
            return pd.DataFrame()
        
        df = pd.DataFrame(all_data)
        
        # Well 컬럼 존재 확인
        if 'Well' not in df.columns:
            print("  ❌ 'Well' column not found in data!")
            print(f"  Available columns: {df.columns.tolist()}")
            return pd.DataFrame()
        
        print(f"  ✓ Loaded: {len(df)} measurements, {df['Well'].nunique()} wells")
        
        return df
    
    def _to_long_format(self, df_template, df_well, metadata, filename):
        """Long format 변환"""
        rows = []
        
        metric_col = df_template.columns[0]
        well_cols = [c for c in df_template.columns if c != metric_col]
        
        # DIFF_DAY 컬럼이 있는 경우에만 사용 (옵션)
        if 'DIFF_DAY' in df_well.columns:
            well_diff_day = dict(zip(df_well['Well'], df_well['DIFF_DAY']))
        else:
            well_diff_day = {}
        
        for _, row in df_template.iterrows():
            metric = row[metric_col]
            if pd.isna(metric):
                continue
                
            for well in well_cols:
                value = row[well]
                if pd.isna(value):
                    continue
                
                rows.append({
                    'File': filename,
                    'Plate_ID': metadata.get('PLATE_ID', 'UNKNOWN'),
                    'Well': well,
                    'Metric': str(metric),
                    'Value': float(value),
                    'BASE_STIM': metadata.get('BASE_STIM', 'UNKNOWN'),
                    'TIME_START': metadata.get('TIME_START', 0),
                    'TIME_DURATION_SEC': metadata.get('TIME_DURATION_SEC', 60),
                    'PLATING_DAY': metadata.get('PLATING_DAY', 0),
                    'DIFF_DAY': well_diff_day.get(well, np.nan),
                    'LIGHT_CODE': metadata.get('LIGHT_CODE', 'UNKNOWN'),
                    'INTENSITY_PCT': metadata.get('INTENSITY_PCT', 0),
                    'EXP_TYPE': metadata.get('EXP_TYPE', 'UNKNOWN'),
                    'DRUG': metadata.get('DRUG', 'NONE'),
                    'CONCENTRATION_MM': metadata.get('CONCENTRATION_MM', 'NONE')
                })
        
        return rows


# ============================================================================
# PER-WELL ANALYZER (ENHANCED with Color Code Fix)
# ============================================================================
class PerWellAnalyzerEnhanced:
    """각 well 독립 분석 - Color code 개선"""
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir) / '00_per_well'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 개선된 color palette
        self.color_palette = {
            'BASE': '#2E86AB',  # 파란색
            'STIM': '#A23B72',  # 자주색
            'Control': '#06A77D',  # 초록색
            'Drug': '#F18F01',  # 주황색
            'BL': '#0066CC',  # 파란색 (Blue Light)
            'GR': '#00AA00',  # 초록색 (Green)
            'OR': '#FF8800',  # 주황색 (Orange)
            'RD': '#DD0000',  # 빨간색 (Red)
        }
    
    def analyze(self):
        """Well별 분석"""
        print('\n[0] Per-Well Analysis (Enhanced with Color Code Fix)...')
        
        wells = sorted(self.df['Well'].unique())
        print(f"  Analyzing {len(wells)} wells...")
        
        for well in wells:
            well_data = self.df[self.df['Well'] == well]
            self._analyze_single_well(well, well_data)
        
        print(f"  ✓ Per-well analysis complete: {len(wells)} wells")
        return self
    
    def _analyze_single_well(self, well, well_data):
        """단일 well 분석"""
        well_dir = self.output_dir / well
        well_dir.mkdir(exist_ok=True)
        
        # Save raw data
        well_data.to_csv(well_dir / f'{well}_data.csv', index=False)
        
        # Light response analysis
        light_resp = self._calculate_light_response(well_data)
        if light_resp is not None:
            light_resp.to_csv(well_dir / f'{well}_light_response.csv', index=False)
        
        # Drug effect analysis
        drug_eff = self._calculate_drug_effect(well_data)
        if drug_eff is not None:
            drug_eff.to_csv(well_dir / f'{well}_drug_effect.csv', index=False)
        
        # Summary
        self._write_summary(well, well_data, light_resp, drug_eff, well_dir)
        
        # Enhanced visualization with fixed colors
        self._plot_well_enhanced(well, well_data, light_resp, drug_eff, well_dir)
    
    def _calculate_light_response(self, well_data):
        """Light response 계산 (Wavelength별 구분)"""
        baseline = well_data[
            (well_data['BASE_STIM'] == 'BASE') & 
            (well_data['EXP_TYPE'] == 'CONTROL')
        ]
        stim = well_data[
            (well_data['BASE_STIM'] == 'STIM') & 
            (well_data['EXP_TYPE'] == 'CONTROL')
        ]
        
        if baseline.empty or stim.empty:
            return None
        
        results = []
        # Wavelength별로 구분하여 계산
        wavelengths = sorted(stim['LIGHT_CODE'].unique()) if 'LIGHT_CODE' in stim.columns else ['UNKNOWN']
        
        for wavelength in wavelengths:
            baseline_wl = baseline[baseline['LIGHT_CODE'] == wavelength] if 'LIGHT_CODE' in baseline.columns else baseline
            stim_wl = stim[stim['LIGHT_CODE'] == wavelength] if 'LIGHT_CODE' in stim.columns else stim
            
            for metric in baseline_wl['Metric'].unique():
                base_vals = baseline_wl[baseline_wl['Metric'] == metric]['Value']
                stim_vals = stim_wl[stim_wl['Metric'] == metric]['Value']
                
                if len(base_vals) == 0 or len(stim_vals) == 0:
                    continue
                
                base_mean = base_vals.mean()
                stim_mean = stim_vals.mean()
                response = stim_mean - base_mean
                pct_change = (response / base_mean * 100) if base_mean != 0 else 0
                
                drug = stim_wl['DRUG'].iloc[0] if len(stim_wl) > 0 else 'NONE'
                
                results.append({
                    'Metric': metric,
                    'Wavelength': wavelength,
                    'Baseline': base_mean,
                    'Stim': stim_mean,
                    'Response': response,
                    'Pct_Change': pct_change,
                    'Light_Code': wavelength,
                    'Drug': drug
                })
        
        return pd.DataFrame(results) if results else None
    
    def _calculate_drug_effect(self, well_data):
        """Drug effect 계산"""
        control = well_data[well_data['EXP_TYPE'] == 'CONTROL']
        drug = well_data[well_data['EXP_TYPE'] == 'DRUG']
        
        if control.empty or drug.empty:
            return None
        
        results = []
        for metric in control['Metric'].unique():
            ctrl_vals = control[control['Metric'] == metric]['Value']
            drug_vals = drug[drug['Metric'] == metric]['Value']
            
            if len(ctrl_vals) == 0 or len(drug_vals) == 0:
                continue
            
            ctrl_mean = ctrl_vals.mean()
            drug_mean = drug_vals.mean()
            difference = drug_mean - ctrl_mean
            pct_change = (difference / ctrl_mean * 100) if ctrl_mean != 0 else 0
            
            drug_name = drug['DRUG'].iloc[0] if len(drug) > 0 else 'UNKNOWN'
            
            results.append({
                'Metric': metric,
                'Control': ctrl_mean,
                'Drug': drug_mean,
                'Drug_Name': drug_name,
                'Difference': difference,
                'Pct_Change': pct_change
            })
        
        return pd.DataFrame(results) if results else None
    
    def _write_summary(self, well, well_data, light_resp, drug_eff, well_dir):
        """요약 정보 작성"""
        summary = []
        summary.append(f"WELL {well} - COMPREHENSIVE ANALYSIS")
        summary.append("="*50)
        
        diff_day = well_data['DIFF_DAY'].iloc[0] if len(well_data) > 0 else 'N/A'
        summary.append(f"DIFF_DAY: {diff_day}")
        summary.append(f"Total Measurements: {len(well_data)}")
        
        # Baseline info
        baseline = well_data[
            (well_data['BASE_STIM'] == 'BASE') & 
            (well_data['Metric'] == 'mean_firing_rate_hz')
        ]
        if not baseline.empty:
            summary.append(f"\nBaseline MFR: {baseline['Value'].mean():.4f} Hz")
        
        # Light response
        if light_resp is not None:
            summary.append("\nLIGHT RESPONSE:")
            mfr_resp = light_resp[light_resp['Metric'] == 'mean_firing_rate_hz']
            if not mfr_resp.empty:
                summary.append(f"  Response: {mfr_resp['Response'].iloc[0]:.4f} Hz")
                summary.append(f"  Change: {mfr_resp['Pct_Change'].iloc[0]:.2f}%")
        
        # Drug effect
        if drug_eff is not None:
            summary.append("\nDRUG EFFECT:")
            mfr_drug = drug_eff[drug_eff['Metric'] == 'mean_firing_rate_hz']
            if not mfr_drug.empty:
                summary.append(f"  Drug: {mfr_drug['Drug_Name'].iloc[0]}")
                summary.append(f"  Effect: {mfr_drug['Difference'].iloc[0]:.4f} Hz")
                summary.append(f"  Change: {mfr_drug['Pct_Change'].iloc[0]:.2f}%")
        
        with open(well_dir / 'summary.txt', 'w') as f:
            f.write('\n'.join(summary))
    
    def _plot_well_enhanced(self, well, well_data, light_resp, drug_eff, well_dir):
        """Enhanced well 시각화 - 개선된 color code"""
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
        
        fig.suptitle(f'Well {well} - Comprehensive Analysis', fontsize=14, fontweight='bold')
        
        # 1. MFR baseline vs stim
        ax = fig.add_subplot(gs[0, 0])
        mfr_data = well_data[well_data['Metric'] == 'mean_firing_rate_hz']
        if not mfr_data.empty:
            conditions = []
            values = []
            colors = []
            for cond in ['BASE', 'STIM']:
                data = mfr_data[mfr_data['BASE_STIM'] == cond]
                if not data.empty:
                    conditions.append(cond)
                    values.append(data['Value'].mean())
                    colors.append(self.color_palette.get(cond, '#808080'))
            
            ax.bar(conditions, values, alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
            ax.set_ylabel('MFR (Hz)', fontsize=10, fontweight='bold')
            ax.set_title('Mean Firing Rate', fontsize=11, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
        
        # 2. Light response
        ax = fig.add_subplot(gs[0, 1])
        if light_resp is not None:
            mfr_resp = light_resp[light_resp['Metric'] == 'mean_firing_rate_hz']
            if not mfr_resp.empty:
                x = ['Baseline', 'Stim']
                y = [mfr_resp['Baseline'].iloc[0], mfr_resp['Stim'].iloc[0]]
                light_code = mfr_resp['Light_Code'].iloc[0]
                color = self.color_palette.get(light_code, '#808080')
                
                ax.bar(x, y, alpha=0.8, color=[self.color_palette['Control'], color], 
                       edgecolor='black', linewidth=1.5)
                ax.set_ylabel('MFR (Hz)', fontsize=10, fontweight='bold')
                ax.set_title(f'Light Response ({light_code})', fontsize=11, fontweight='bold')
                ax.grid(axis='y', alpha=0.3)
        
        # 3. Drug effect
        ax = fig.add_subplot(gs[0, 2])
        if drug_eff is not None:
            mfr_drug = drug_eff[drug_eff['Metric'] == 'mean_firing_rate_hz']
            if not mfr_drug.empty:
                x = ['Control', 'Drug']
                y = [mfr_drug['Control'].iloc[0], mfr_drug['Drug'].iloc[0]]
                
                ax.bar(x, y, alpha=0.8, color=[self.color_palette['Control'], self.color_palette['Drug']],
                       edgecolor='black', linewidth=1.5)
                ax.set_ylabel('MFR (Hz)', fontsize=10, fontweight='bold')
                ax.set_title(f'Drug Effect ({mfr_drug["Drug_Name"].iloc[0]})', fontsize=11, fontweight='bold')
                ax.grid(axis='y', alpha=0.3)
        
        # 4. Burst frequency
        ax = fig.add_subplot(gs[1, 0])
        burst_data = well_data[well_data['Metric'].str.contains('burst_frequency', case=False, na=False)]
        if not burst_data.empty:
            conditions = []
            values = []
            colors = []
            for cond in ['BASE', 'STIM']:
                data = burst_data[burst_data['BASE_STIM'] == cond]
                if not data.empty:
                    conditions.append(cond)
                    values.append(data['Value'].mean())
                    colors.append(self.color_palette.get(cond, '#808080'))
            
            ax.bar(conditions, values, alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
            ax.set_ylabel('Burst Freq (Hz)', fontsize=10, fontweight='bold')
            ax.set_title('Burst Frequency', fontsize=11, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
        
        # 5. Spikes
        ax = fig.add_subplot(gs[1, 1])
        spike_data = well_data[well_data['Metric'] == 'number_of_spikes']
        if not spike_data.empty:
            conditions = []
            values = []
            colors = []
            for cond in ['BASE', 'STIM']:
                data = spike_data[spike_data['BASE_STIM'] == cond]
                if not data.empty:
                    conditions.append(cond)
                    values.append(data['Value'].mean())
                    colors.append(self.color_palette.get(cond, '#808080'))
            
            ax.bar(conditions, values, alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
            ax.set_ylabel('Spike Count', fontsize=10, fontweight='bold')
            ax.set_title('Total Spikes', fontsize=11, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
        
        # 6. Active electrodes
        ax = fig.add_subplot(gs[1, 2])
        elec_data = well_data[well_data['Metric'] == 'number_of_active_electrodes']
        if not elec_data.empty:
            conditions = []
            values = []
            colors = []
            for cond in ['BASE', 'STIM']:
                data = elec_data[elec_data['BASE_STIM'] == cond]
                if not data.empty:
                    conditions.append(cond)
                    values.append(data['Value'].mean())
                    colors.append(self.color_palette.get(cond, '#808080'))
            
            ax.bar(conditions, values, alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
            ax.set_ylabel('Active Electrodes', fontsize=10, fontweight='bold')
            ax.set_title('Active Electrodes', fontsize=11, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
        
        plt.savefig(well_dir / f'{well}_comprehensive.png', dpi=300, bbox_inches='tight')
        plt.close()


# ============================================================================
# SPONTANEOUS ANALYZER (Baseline Only)
# ============================================================================
class SpontaneousAnalyzer:
    """Spontaneous activity 분석 - BASELINE 전용"""
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir) / '01_spontaneous'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.result_df = None
    
    def analyze(self):
        """Spontaneous activity 분석 - BASELINE만 (Wavelength별 구분 추가)"""
        print('\n[1] Spontaneous Activity Analysis (BASELINE ONLY with Wavelength Breakdown)...')
        
        # BASELINE 데이터만 필터링
        baseline = self.df[self.df['BASE_STIM'] == 'BASE'].copy()
        
        if baseline.empty:
            print('  ⚠ No baseline data found!')
            return self
        
        print(f'  Using BASELINE data only: {len(baseline)} measurements')
        
        # Well별 × Wavelength별 평균 계산
        results = []
        for well in sorted(baseline['Well'].unique()):
            well_data = baseline[baseline['Well'] == well]
            
            # Wavelength별로 구분
            wavelengths = sorted(well_data['LIGHT_CODE'].unique()) if 'LIGHT_CODE' in well_data.columns else ['UNKNOWN']
            
            for wavelength in wavelengths:
                wavelength_data = well_data[well_data['LIGHT_CODE'] == wavelength] if 'LIGHT_CODE' in well_data.columns else well_data
                
                for metric in sorted(wavelength_data['Metric'].unique()):
                    metric_data = wavelength_data[wavelength_data['Metric'] == metric]
                    
                    if metric_data.empty:
                        continue
                    
                    results.append({
                        'Well': well,
                        'Wavelength': wavelength,
                        'Plate_ID': metric_data['Plate_ID'].iloc[0] if 'Plate_ID' in metric_data.columns else 'UNKNOWN',
                        'Metric': metric,
                        'Mean': metric_data['Value'].mean(),
                        'Std': metric_data['Value'].std(),
                        'Count': len(metric_data),
                        'DIFF_DAY': metric_data['DIFF_DAY'].mean() if 'DIFF_DAY' in metric_data.columns else np.nan,
                        'Drug': metric_data['DRUG'].iloc[0] if 'DRUG' in metric_data.columns else 'NONE',
                        'EXP_TYPE': metric_data['EXP_TYPE'].iloc[0] if 'EXP_TYPE' in metric_data.columns else 'UNKNOWN'
                    })
        
        self.result_df = pd.DataFrame(results)
        
        # CSV 저장
        csv_path = self.output_dir / 'spontaneous_activity.csv'
        self.result_df.to_csv(csv_path, index=False)
        print(f'  ✓ CSV saved: {csv_path.name} (with wavelength breakdown)')
        
        # Excel 리포트
        self._create_report()
        
        return self
    
    def _create_report(self):
        """Excel 리포트 생성"""
        report_path = self.output_dir / 'spontaneous_report.xlsx'
        
        with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
            # 전체 데이터
            self.result_df.to_excel(writer, sheet_name='All_Metrics', index=False)
            
            # 주요 metric별 시트
            for metric in ['mean_firing_rate_hz', 'burst_frequency_hz', 'number_of_spikes']:
                metric_data = self.result_df[self.result_df['Metric'].str.contains(metric, case=False, na=False)]
                if not metric_data.empty:
                    sheet_name = metric[:30]  # Excel 시트 이름 제한
                    metric_data.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f'  ✓ Excel report saved: {report_path.name}')
    
    def visualize(self):
        """시각화 (Wavelength별 구분 추가)"""
        if self.result_df is None or self.result_df.empty:
            return self
        
        # MFR by well (전체)
        mfr = self.result_df[self.result_df['Metric'] == 'mean_firing_rate_hz']
        if not mfr.empty:
            # 1. Well별 전체 평균
            fig, ax = plt.subplots(figsize=(10, 6))
            wells = sorted(mfr['Well'].unique())
            means = [mfr[mfr['Well'] == w]['Mean'].mean() for w in wells]
            
            ax.bar(wells, means, alpha=0.8, color='steelblue', edgecolor='black', linewidth=1.5)
            ax.set_xlabel('Well', fontsize=12, fontweight='bold')
            ax.set_ylabel('MFR (Hz)', fontsize=12, fontweight='bold')
            ax.set_title('Spontaneous Activity - MFR by Well (BASELINE)', 
                        fontsize=14, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(self.output_dir / 'fig1_mfr_by_well.png', dpi=300, bbox_inches='tight')
            plt.close()
            
            # 2. Well별 × Wavelength별 비교
            if 'Wavelength' in mfr.columns:
                wavelengths = sorted(mfr['Wavelength'].unique())
                if len(wavelengths) > 1:
                    fig, ax = plt.subplots(figsize=(14, 6))
                    
                    x = np.arange(len(wells))
                    width = 0.8 / len(wavelengths)
                    
                    wavelength_colors = {'BL': '#0066CC', 'GR': '#00AA00', 'OR': '#FF8800', 'RD': '#DD0000', 'UNKNOWN': '#808080'}
                    
                    for i, wl in enumerate(wavelengths):
                        wl_data = mfr[mfr['Wavelength'] == wl]
                        wl_means = [wl_data[wl_data['Well'] == w]['Mean'].mean() if len(wl_data[wl_data['Well'] == w]) > 0 else 0 
                                  for w in wells]
                        color = wavelength_colors.get(wl, '#808080')
                        ax.bar(x + i * width, wl_means, width, label=wl, alpha=0.8, 
                              color=color, edgecolor='black', linewidth=1)
                    
                    ax.set_xlabel('Well', fontsize=12, fontweight='bold')
                    ax.set_ylabel('MFR (Hz)', fontsize=12, fontweight='bold')
                    ax.set_title('Spontaneous Activity - MFR by Well × Wavelength (BASELINE)', 
                                fontsize=14, fontweight='bold')
                    ax.set_xticks(x + width * (len(wavelengths) - 1) / 2)
                    ax.set_xticklabels(wells)
                    ax.legend(title='Wavelength', fontsize=10)
                    ax.grid(axis='y', alpha=0.3)
                    
                    plt.tight_layout()
                    plt.savefig(self.output_dir / 'fig2_mfr_by_well_wavelength.png', dpi=300, bbox_inches='tight')
                    plt.close()
            
            print(f'  ✓ Visualizations saved')
        
        return self


# ============================================================================
# LIGHT RESPONSE ANALYZER (with Per-Well and Burst)
# ============================================================================
class LightResponseAnalyzer:
    """Light response 분석 - Per-well 및 Burst 추가"""
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir) / '02_light_response'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.result_df = None
        self.per_well_df = None
        self.burst_df = None
    
    def analyze(self):
        """Light response 분석 - 전체, per-well, burst"""
        print('\n[2] Light Response Analysis (with Per-Well & Burst)...')
        
        # 전체 분석
        self._analyze_overall()
        
        # Per-well 분석 추가
        self._analyze_per_well()
        
        # Burst 분석 추가
        self._analyze_burst()
        
        return self
    
    def _analyze_overall(self):
        """전체 light response 분석"""
        baseline = self.df[
            (self.df['BASE_STIM'] == 'BASE') & 
            (self.df['EXP_TYPE'] == 'CONTROL')
        ]
        stim = self.df[
            (self.df['BASE_STIM'] == 'STIM') & 
            (self.df['EXP_TYPE'] == 'CONTROL')
        ]
        
        if baseline.empty or stim.empty:
            print('  ⚠ No light response data found!')
            return
        
        results = []
        for well in sorted(set(baseline['Well'].unique()) & set(stim['Well'].unique())):
            well_base = baseline[baseline['Well'] == well]
            well_stim = stim[stim['Well'] == well]
            
            for metric in sorted(set(well_base['Metric'].unique()) & set(well_stim['Metric'].unique())):
                base_vals = well_base[well_base['Metric'] == metric]['Value']
                stim_vals = well_stim[well_stim['Metric'] == metric]['Value']
                
                if len(base_vals) == 0 or len(stim_vals) == 0:
                    continue
                
                base_mean = base_vals.mean()
                stim_mean = stim_vals.mean()
                response = stim_mean - base_mean
                pct_change = (response / base_mean * 100) if base_mean != 0 else 0
                
                light_code = well_stim['LIGHT_CODE'].iloc[0]
                
                results.append({
                    'Well': well,
                    'Metric': metric,
                    'Baseline': base_mean,
                    'Stim': stim_mean,
                    'Response': response,
                    'Pct_Change': pct_change,
                    'Light_Code': light_code,
                    'Plate_ID': well_base['Plate_ID'].iloc[0],
                    'DIFF_DAY': well_base['DIFF_DAY'].mean()
                })
        
        self.result_df = pd.DataFrame(results)
        
        if not self.result_df.empty:
            csv_path = self.output_dir / 'light_response.csv'
            self.result_df.to_csv(csv_path, index=False)
            print(f'  ✓ Overall light response saved: {csv_path.name}')
    
    def _analyze_per_well(self):
        """Per-well 분석 (Wavelength별 명확한 구분)"""
        if self.result_df is None or self.result_df.empty:
            return
        
        print('  Adding per-well analysis (with wavelength breakdown)...')
        
        # Per-well × Wavelength별 상세 데이터
        per_well_results = []
        for well in sorted(self.result_df['Well'].unique()):
            well_data = self.result_df[self.result_df['Well'] == well]
            
            # Wavelength별로 구분
            wavelengths = sorted(well_data['Light_Code'].unique()) if 'Light_Code' in well_data.columns else ['UNKNOWN']
            
            for wavelength in wavelengths:
                wavelength_data = well_data[well_data['Light_Code'] == wavelength] if 'Light_Code' in well_data.columns else well_data
                
                for metric in ['mean_firing_rate_hz', 'burst_frequency_hz', 'number_of_spikes']:
                    metric_data = wavelength_data[wavelength_data['Metric'].str.contains(metric, case=False, na=False)]
                    if not metric_data.empty:
                        per_well_results.append({
                            'Well': well,
                            'Wavelength': wavelength,
                            'Metric': metric,
                            'Baseline_Mean': metric_data['Baseline'].mean(),
                            'Stim_Mean': metric_data['Stim'].mean(),
                            'Response_Mean': metric_data['Response'].mean(),
                            'Pct_Change_Mean': metric_data['Pct_Change'].mean(),
                            'Light_Code': wavelength
                        })
        
        self.per_well_df = pd.DataFrame(per_well_results)
        
        if not self.per_well_df.empty:
            csv_path = self.output_dir / 'light_response_per_well.csv'
            self.per_well_df.to_csv(csv_path, index=False)
            print(f'  ✓ Per-well analysis saved: {csv_path.name} (Well × Wavelength breakdown)')
    
    def _analyze_burst(self):
        """Burst 관련 분석"""
        if self.result_df is None or self.result_df.empty:
            return
        
        print('  Adding burst analysis...')
        
        # Burst 관련 metric 필터링
        burst_metrics = self.result_df[
            self.result_df['Metric'].str.contains('burst', case=False, na=False)
        ]
        
        if burst_metrics.empty:
            print('  ⚠ No burst metrics found')
            return
        
        self.burst_df = burst_metrics.copy()
        
        csv_path = self.output_dir / 'light_response_burst.csv'
        self.burst_df.to_csv(csv_path, index=False)
        print(f'  ✓ Burst analysis saved: {csv_path.name}')
    
    def visualize(self):
        """시각화"""
        if self.result_df is None or self.result_df.empty:
            return self
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Light Response Analysis', fontsize=16, fontweight='bold')
        
        # 1. Overall response by light code
        ax = axes[0, 0]
        mfr = self.result_df[self.result_df['Metric'] == 'mean_firing_rate_hz']
        if not mfr.empty:
            light_codes = sorted(mfr['Light_Code'].unique())
            responses = [mfr[mfr['Light_Code'] == lc]['Response'].mean() for lc in light_codes]
            
            colors = {'BL': '#0066CC', 'GR': '#00AA00', 'OR': '#FF8800', 'RD': '#DD0000'}
            bar_colors = [colors.get(lc, '#808080') for lc in light_codes]
            
            ax.bar(light_codes, responses, alpha=0.8, color=bar_colors, edgecolor='black', linewidth=1.5)
            ax.set_xlabel('Wavelength', fontsize=11, fontweight='bold')
            ax.set_ylabel('MFR Response (Hz)', fontsize=11, fontweight='bold')
            ax.set_title('Overall Light Response', fontsize=12, fontweight='bold')
            ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
            ax.grid(axis='y', alpha=0.3)
        
        # 2. Per-well response
        ax = axes[0, 1]
        if self.per_well_df is not None and not self.per_well_df.empty:
            mfr_well = self.per_well_df[self.per_well_df['Metric'] == 'mean_firing_rate_hz']
            if not mfr_well.empty:
                wells = sorted(mfr_well['Well'].unique())
                responses = [mfr_well[mfr_well['Well'] == w]['Response_Mean'].iloc[0] for w in wells]
                
                ax.bar(wells, responses, alpha=0.8, color='#A23B72', edgecolor='black', linewidth=1.5)
                ax.set_xlabel('Well', fontsize=11, fontweight='bold')
                ax.set_ylabel('MFR Response (Hz)', fontsize=11, fontweight='bold')
                ax.set_title('Per-Well Light Response', fontsize=12, fontweight='bold')
                ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
                ax.grid(axis='y', alpha=0.3)
        
        # 3. Burst response
        ax = axes[1, 0]
        if self.burst_df is not None and not self.burst_df.empty:
            burst_mfr = self.burst_df[self.burst_df['Metric'].str.contains('burst_frequency', case=False, na=False)]
            if not burst_mfr.empty:
                wells = sorted(burst_mfr['Well'].unique())
                responses = [burst_mfr[burst_mfr['Well'] == w]['Response'].mean() for w in wells]
                
                ax.bar(wells, responses, alpha=0.8, color='coral', edgecolor='black', linewidth=1.5)
                ax.set_xlabel('Well', fontsize=11, fontweight='bold')
                ax.set_ylabel('Burst Frequency Response (Hz)', fontsize=11, fontweight='bold')
                ax.set_title('Burst Response to Light', fontsize=12, fontweight='bold')
                ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
                ax.grid(axis='y', alpha=0.3)
        
        # 4. Percent change summary
        ax = axes[1, 1]
        if self.per_well_df is not None and not self.per_well_df.empty:
            mfr_well = self.per_well_df[self.per_well_df['Metric'] == 'mean_firing_rate_hz']
            if not mfr_well.empty:
                wells = sorted(mfr_well['Well'].unique())
                pct_changes = [mfr_well[mfr_well['Well'] == w]['Pct_Change_Mean'].iloc[0] for w in wells]
                
                ax.bar(wells, pct_changes, alpha=0.8, color='#06A77D', edgecolor='black', linewidth=1.5)
                ax.set_xlabel('Well', fontsize=11, fontweight='bold')
                ax.set_ylabel('% Change', fontsize=11, fontweight='bold')
                ax.set_title('Percent Change in MFR', fontsize=12, fontweight='bold')
                ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
                ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'fig1_light_response_comprehensive.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f'  ✓ Visualization saved')
        
        # Excel 리포트
        self._create_report()
        
        return self
    
    def _create_report(self):
        """Excel 리포트 생성"""
        report_path = self.output_dir / 'light_response_report.xlsx'
        
        with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
            if self.result_df is not None:
                self.result_df.to_excel(writer, sheet_name='Overall', index=False)
            
            if self.per_well_df is not None:
                self.per_well_df.to_excel(writer, sheet_name='Per_Well', index=False)
            
            if self.burst_df is not None:
                self.burst_df.to_excel(writer, sheet_name='Burst', index=False)
        
        print(f'  ✓ Excel report saved: {report_path.name}')


# ============================================================================
# DRUG EFFECT ANALYZER (with Light Response & Burst)
# ============================================================================
class DrugEffectAnalyzer:
    """Drug effect 분석 - Light response & Burst 포함"""
    
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir) / '03_drug_effects'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_df = None
        self.light_modulation_df = None
        self.burst_effect_df = None
    
    def analyze(self):
        """Drug effect 분석 - Baseline, Light response, Burst"""
        print('\n[3] Drug Effect Analysis (Baseline + Light Response + Burst)...')
        
        # Baseline drug effect
        self._analyze_baseline_effect()
        
        # Light response modulation
        self._analyze_light_modulation()
        
        # Burst effect
        self._analyze_burst_effect()
        
        return self
    
    def _analyze_baseline_effect(self):
        """Baseline drug effect (Wavelength별 구분 추가)"""
        print('  Analyzing baseline drug effect (with wavelength breakdown)...')
        
        control = self.df[
            (self.df['BASE_STIM'] == 'BASE') & 
            (self.df['EXP_TYPE'] == 'CONTROL')
        ]
        drug = self.df[
            (self.df['BASE_STIM'] == 'BASE') & 
            (self.df['EXP_TYPE'] == 'DRUG')
        ]
        
        if control.empty or drug.empty:
            print('  ⚠ No baseline drug data found!')
            return
        
        results = []
        for well in sorted(set(control['Well'].unique()) & set(drug['Well'].unique())):
            well_ctrl = control[control['Well'] == well]
            well_drug = drug[drug['Well'] == well]
            
            # Wavelength별로 구분
            wavelengths = sorted(set(well_ctrl['LIGHT_CODE'].unique()) & set(well_drug['LIGHT_CODE'].unique())) if 'LIGHT_CODE' in well_ctrl.columns else ['UNKNOWN']
            
            for wavelength in wavelengths:
                ctrl_wl = well_ctrl[well_ctrl['LIGHT_CODE'] == wavelength] if 'LIGHT_CODE' in well_ctrl.columns else well_ctrl
                drug_wl = well_drug[well_drug['LIGHT_CODE'] == wavelength] if 'LIGHT_CODE' in well_drug.columns else well_drug
                
                for metric in sorted(set(ctrl_wl['Metric'].unique()) & set(drug_wl['Metric'].unique())):
                    ctrl_vals = ctrl_wl[ctrl_wl['Metric'] == metric]['Value']
                    drug_vals = drug_wl[drug_wl['Metric'] == metric]['Value']
                    
                    if len(ctrl_vals) == 0 or len(drug_vals) == 0:
                        continue
                    
                    ctrl_mean = ctrl_vals.mean()
                    drug_mean = drug_vals.mean()
                    difference = drug_mean - ctrl_mean
                    pct_change = (difference / ctrl_mean * 100) if ctrl_mean != 0 else 0
                    
                    drug_name = drug_wl['DRUG'].iloc[0] if len(drug_wl) > 0 else 'UNKNOWN'
                    
                    results.append({
                        'Well': well,
                        'Wavelength': wavelength,
                        'Metric': metric,
                        'Control': ctrl_mean,
                        'Drug': drug_mean,
                        'Drug_Name': drug_name,
                        'Difference': difference,
                        'Pct_Change': pct_change,
                        'Plate_ID': ctrl_wl['Plate_ID'].iloc[0] if 'Plate_ID' in ctrl_wl.columns else 'UNKNOWN'
                    })
        
        self.baseline_df = pd.DataFrame(results)
        
        if not self.baseline_df.empty:
            csv_path = self.output_dir / 'baseline_drug_effects.csv'
            self.baseline_df.to_csv(csv_path, index=False)
            print(f'  ✓ Baseline drug effects saved: {csv_path.name} (with wavelength breakdown)')
    
    def _analyze_light_modulation(self):
        """Light response modulation by drug"""
        print('  Analyzing light response modulation...')
        
        # Control light response
        control_base = self.df[
            (self.df['BASE_STIM'] == 'BASE') & 
            (self.df['EXP_TYPE'] == 'CONTROL')
        ]
        control_stim = self.df[
            (self.df['BASE_STIM'] == 'STIM') & 
            (self.df['EXP_TYPE'] == 'CONTROL')
        ]
        
        # Drug light response
        drug_base = self.df[
            (self.df['BASE_STIM'] == 'BASE') & 
            (self.df['EXP_TYPE'] == 'DRUG')
        ]
        drug_stim = self.df[
            (self.df['BASE_STIM'] == 'STIM') & 
            (self.df['EXP_TYPE'] == 'DRUG')
        ]
        
        if any(df.empty for df in [control_base, control_stim, drug_base, drug_stim]):
            print('  ⚠ No light modulation data found!')
            return
        
        results = []
        wells = sorted(set(control_base['Well'].unique()) & set(drug_base['Well'].unique()))
        
        for well in wells:
            # Control response
            cb = control_base[control_base['Well'] == well]
            cs = control_stim[control_stim['Well'] == well]
            
            # Drug response
            db = drug_base[drug_base['Well'] == well]
            ds = drug_stim[drug_stim['Well'] == well]
            
            # Wavelength별로 구분
            wavelengths = sorted(set(cs['LIGHT_CODE'].unique()) & set(ds['LIGHT_CODE'].unique())) if 'LIGHT_CODE' in cs.columns else ['UNKNOWN']
            
            for wavelength in wavelengths:
                cs_wl = cs[cs['LIGHT_CODE'] == wavelength] if 'LIGHT_CODE' in cs.columns else cs
                ds_wl = ds[ds['LIGHT_CODE'] == wavelength] if 'LIGHT_CODE' in ds.columns else ds
                cb_wl = cb[cb['LIGHT_CODE'] == wavelength] if 'LIGHT_CODE' in cb.columns else cb
                db_wl = db[db['LIGHT_CODE'] == wavelength] if 'LIGHT_CODE' in db.columns else db
                
                for metric in sorted(set(cb_wl['Metric'].unique()) & set(cs_wl['Metric'].unique()) & 
                                    set(db_wl['Metric'].unique()) & set(ds_wl['Metric'].unique())):
                    # Control response
                    ctrl_resp = cs_wl[cs_wl['Metric'] == metric]['Value'].mean() - cb_wl[cb_wl['Metric'] == metric]['Value'].mean()
                    
                    # Drug response
                    drug_resp = ds_wl[ds_wl['Metric'] == metric]['Value'].mean() - db_wl[db_wl['Metric'] == metric]['Value'].mean()
                    
                    # Modulation
                    modulation = drug_resp - ctrl_resp
                    pct_change = (modulation / ctrl_resp * 100) if ctrl_resp != 0 else 0
                    
                    drug_name = db_wl['DRUG'].iloc[0] if len(db_wl) > 0 else 'UNKNOWN'
                    
                    results.append({
                        'Well': well,
                        'Wavelength': wavelength,
                        'Metric': metric,
                        'Control_Response': ctrl_resp,
                        'Drug_Response': drug_resp,
                        'Modulation': modulation,
                        'Pct_Change': pct_change,
                        'Light_Code': wavelength,
                        'Drug_Name': drug_name
                    })
        
        self.light_modulation_df = pd.DataFrame(results)
        
        if not self.light_modulation_df.empty:
            csv_path = self.output_dir / 'light_response_modulation.csv'
            self.light_modulation_df.to_csv(csv_path, index=False)
            print(f'  ✓ Light response modulation saved: {csv_path.name} (with wavelength breakdown)')
    
    def _analyze_burst_effect(self):
        """Burst drug effect"""
        print('  Analyzing burst drug effect...')
        
        if self.baseline_df is None or self.baseline_df.empty:
            return
        
        # Burst 관련 metric 필터링
        burst_metrics = self.baseline_df[
            self.baseline_df['Metric'].str.contains('burst', case=False, na=False)
        ]
        
        if burst_metrics.empty:
            print('  ⚠ No burst metrics found')
            return
        
        self.burst_effect_df = burst_metrics.copy()
        
        csv_path = self.output_dir / 'burst_drug_effects.csv'
        self.burst_effect_df.to_csv(csv_path, index=False)
        print(f'  ✓ Burst drug effects saved: {csv_path.name}')
    
    def visualize(self):
        """시각화"""
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Drug Effect Analysis', fontsize=16, fontweight='bold')
        
        # 1. Baseline drug effect
        ax = axes[0, 0]
        if self.baseline_df is not None and not self.baseline_df.empty:
            mfr = self.baseline_df[self.baseline_df['Metric'] == 'mean_firing_rate_hz']
            if not mfr.empty:
                wells = sorted(mfr['Well'].unique())
                pct_changes = [mfr[mfr['Well'] == w]['Pct_Change'].mean() for w in wells]
                
                colors = ['#06A77D' if pc >= 0 else '#F18F01' for pc in pct_changes]
                
                ax.bar(wells, pct_changes, alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
                ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
                ax.set_xlabel('Well', fontsize=11, fontweight='bold')
                ax.set_ylabel('% Change in MFR', fontsize=11, fontweight='bold')
                ax.set_title('Baseline Drug Effect on MFR', fontsize=12, fontweight='bold')
                ax.grid(axis='y', alpha=0.3)
        
        # 2. Light response modulation
        ax = axes[0, 1]
        if self.light_modulation_df is not None and not self.light_modulation_df.empty:
            mfr_mod = self.light_modulation_df[self.light_modulation_df['Metric'] == 'mean_firing_rate_hz']
            if not mfr_mod.empty:
                wells = sorted(mfr_mod['Well'].unique())
                modulations = [mfr_mod[mfr_mod['Well'] == w]['Modulation'].mean() for w in wells]
                
                colors = ['#2E86AB' if m >= 0 else '#A23B72' for m in modulations]
                
                ax.bar(wells, modulations, alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
                ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
                ax.set_xlabel('Well', fontsize=11, fontweight='bold')
                ax.set_ylabel('Modulation (Hz)', fontsize=11, fontweight='bold')
                ax.set_title('Light Response Modulation by Drug', fontsize=12, fontweight='bold')
                ax.grid(axis='y', alpha=0.3)
        
        # 3. Burst drug effect
        ax = axes[1, 0]
        if self.burst_effect_df is not None and not self.burst_effect_df.empty:
            burst_freq = self.burst_effect_df[
                self.burst_effect_df['Metric'].str.contains('burst_frequency', case=False, na=False)
            ]
            if not burst_freq.empty:
                wells = sorted(burst_freq['Well'].unique())
                pct_changes = [burst_freq[burst_freq['Well'] == w]['Pct_Change'].mean() for w in wells]
                
                colors = ['coral' if pc >= 0 else 'indianred' for pc in pct_changes]
                
                ax.bar(wells, pct_changes, alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
                ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
                ax.set_xlabel('Well', fontsize=11, fontweight='bold')
                ax.set_ylabel('% Change', fontsize=11, fontweight='bold')
                ax.set_title('Burst Frequency Drug Effect', fontsize=12, fontweight='bold')
                ax.grid(axis='y', alpha=0.3)
        
        # 4. Summary comparison
        ax = axes[1, 1]
        if all(df is not None for df in [self.baseline_df, self.light_modulation_df]):
            mfr_base = self.baseline_df[self.baseline_df['Metric'] == 'mean_firing_rate_hz']
            mfr_light = self.light_modulation_df[self.light_modulation_df['Metric'] == 'mean_firing_rate_hz']
            
            if not mfr_base.empty and not mfr_light.empty:
                wells = sorted(set(mfr_base['Well'].unique()) & set(mfr_light['Well'].unique()))
                
                x = np.arange(len(wells))
                width = 0.35
                
                base_pct = [mfr_base[mfr_base['Well'] == w]['Pct_Change'].mean() for w in wells]
                light_pct = [mfr_light[mfr_light['Well'] == w]['Pct_Change'].mean() for w in wells]
                
                ax.bar(x - width/2, base_pct, width, label='Baseline', 
                      alpha=0.8, color='#06A77D', edgecolor='black', linewidth=1.5)
                ax.bar(x + width/2, light_pct, width, label='Light Response', 
                      alpha=0.8, color='#2E86AB', edgecolor='black', linewidth=1.5)
                
                ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
                ax.set_xlabel('Well', fontsize=11, fontweight='bold')
                ax.set_ylabel('% Change', fontsize=11, fontweight='bold')
                ax.set_title('Drug Effect Comparison', fontsize=12, fontweight='bold')
                ax.set_xticks(x)
                ax.set_xticklabels(wells)
                ax.legend()
                ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'fig1_drug_effects_comprehensive.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f'  ✓ Visualization saved')
        
        # Excel 리포트
        self._create_report()
        
        return self
    
    def _create_report(self):
        """Excel 리포트 생성"""
        report_path = self.output_dir / 'drug_effects_report.xlsx'
        
        # 최소 하나의 시트가 있는지 확인
        has_data = False
        if self.baseline_df is not None and not self.baseline_df.empty:
            has_data = True
        if self.light_modulation_df is not None and not self.light_modulation_df.empty:
            has_data = True
        if self.burst_effect_df is not None and not self.burst_effect_df.empty:
            has_data = True
        
        # 데이터가 없으면 리포트 생성 건너뛰기
        if not has_data:
            print(f'  ⚠ No data available for Excel report')
            return
        
        with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
            if self.baseline_df is not None and not self.baseline_df.empty:
                self.baseline_df.to_excel(writer, sheet_name='Baseline_Effects', index=False)
            
            if self.light_modulation_df is not None and not self.light_modulation_df.empty:
                self.light_modulation_df.to_excel(writer, sheet_name='Light_Modulation', index=False)
            
            if self.burst_effect_df is not None and not self.burst_effect_df.empty:
                self.burst_effect_df.to_excel(writer, sheet_name='Burst_Effects', index=False)
        
        print(f'  ✓ Excel report saved: {report_path.name}')


# ============================================================================
# ENHANCED DASHBOARD (mea_dashboard.py 스타일)
# ============================================================================
class EnhancedDashboard:
    """개선된 Dashboard - mea_dashboard.py 스타일"""
    
    def __init__(self, analysis_dir, output_path):
        self.analysis_dir = Path(analysis_dir)
        self.output_path = Path(output_path)
        
        # Load data
        self.spont = None
        self.light = None
        self.light_per_well = None
        self.burst_light = None
        self.drug_baseline = None
        self.drug_light_mod = None
        self.drug_burst = None
        
        self._load_data()
    
    def _load_data(self):
        """분석 결과 로드"""
        try:
            self.spont = pd.read_csv(self.analysis_dir / '01_spontaneous' / 'spontaneous_activity.csv')
        except:
            pass
        
        try:
            self.light = pd.read_csv(self.analysis_dir / '02_light_response' / 'light_response.csv')
        except:
            pass
        
        try:
            self.light_per_well = pd.read_csv(self.analysis_dir / '02_light_response' / 'light_response_per_well.csv')
        except:
            pass
        
        try:
            self.burst_light = pd.read_csv(self.analysis_dir / '02_light_response' / 'light_response_burst.csv')
        except:
            pass
        
        try:
            self.drug_baseline = pd.read_csv(self.analysis_dir / '03_drug_effects' / 'baseline_drug_effects.csv')
        except:
            pass
        
        try:
            self.drug_light_mod = pd.read_csv(self.analysis_dir / '03_drug_effects' / 'light_response_modulation.csv')
        except:
            pass
        
        try:
            self.drug_burst = pd.read_csv(self.analysis_dir / '03_drug_effects' / 'burst_drug_effects.csv')
        except:
            pass
    
    def create(self):
        """Enhanced Dashboard 생성"""
        print('\n[DASHBOARD] Creating enhanced dashboard...')
        
        fig = plt.figure(figsize=(20, 15))
        gs = fig.add_gridspec(3, 3, hspace=0.4, wspace=0.35)
        
        fig.suptitle('MEA Comprehensive Analysis Dashboard', 
                    fontsize=18, fontweight='bold', y=0.98)
        
        # Row 1: Spontaneous Activity & Drug Effect
        ax1 = fig.add_subplot(gs[0, 0])
        self._plot_spontaneous_activity(ax1)
        
        ax2 = fig.add_subplot(gs[0, 1])
        self._plot_spontaneous_drug_effect(ax2)
        
        ax3 = fig.add_subplot(gs[0, 2])
        self._plot_burst_baseline(ax3)
        
        # Row 2: Light Response
        ax4 = fig.add_subplot(gs[1, 0])
        self._plot_light_response_overall(ax4)
        
        ax5 = fig.add_subplot(gs[1, 1])
        self._plot_light_response_per_well(ax5)
        
        ax6 = fig.add_subplot(gs[1, 2])
        self._plot_burst_light_response(ax6)
        
        # Row 3: Drug Effects on Light Response & Burst
        ax7 = fig.add_subplot(gs[2, 0])
        self._plot_light_response_modulation(ax7)
        
        ax8 = fig.add_subplot(gs[2, 1])
        self._plot_burst_drug_effect(ax8)
        
        ax9 = fig.add_subplot(gs[2, 2])
        self._plot_summary_comparison(ax9)
        
        plt.savefig(self.output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"  ✓ Enhanced dashboard saved: {self.output_path.name}")
        return self
    
    def _plot_spontaneous_activity(self, ax):
        """Spontaneous MFR"""
        if self.spont is None:
            ax.set_visible(False)
            return
        
        mfr = self.spont[self.spont['Metric'] == 'mean_firing_rate_hz']
        if mfr.empty:
            ax.set_visible(False)
            return
        
        wells = sorted(mfr['Well'].unique())
        means = [mfr[mfr['Well'] == w]['Mean'].mean() for w in wells]
        
        ax.bar(wells, means, alpha=0.8, color='steelblue', edgecolor='black', linewidth=1.5)
        ax.set_xlabel('Well', fontsize=10, fontweight='bold')
        ax.set_ylabel('MFR (Hz)', fontsize=10, fontweight='bold')
        ax.set_title('Spontaneous Activity\n(Baseline MFR)', fontsize=11, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    
    def _plot_spontaneous_drug_effect(self, ax):
        """Spontaneous drug effect (mea_dashboard.py 스타일)"""
        if self.drug_baseline is None:
            ax.set_visible(False)
            return
        
        mfr = self.drug_baseline[self.drug_baseline['Metric'] == 'mean_firing_rate_hz']
        if mfr.empty:
            ax.set_visible(False)
            return
        
        wells = sorted(mfr['Well'].unique())
        pct_changes = [mfr[mfr['Well'] == w]['Pct_Change'].mean() for w in wells]
        
        colors = ['#06A77D' if pc >= 0 else '#F18F01' for pc in pct_changes]
        
        ax.bar(wells, pct_changes, alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
        ax.set_xlabel('Well', fontsize=10, fontweight='bold')
        ax.set_ylabel('% Change', fontsize=10, fontweight='bold')
        ax.set_title('Spontaneous Activity Change\n(Drug vs Control, MFR)', fontsize=11, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    
    def _plot_burst_baseline(self, ax):
        """Baseline burst frequency"""
        if self.spont is None:
            ax.set_visible(False)
            return
        
        burst = self.spont[self.spont['Metric'].str.contains('burst_frequency', case=False, na=False)]
        if burst.empty:
            ax.set_visible(False)
            return
        
        wells = sorted(burst['Well'].unique())
        means = [burst[burst['Well'] == w]['Mean'].mean() for w in wells]
        
        ax.bar(wells, means, alpha=0.8, color='coral', edgecolor='black', linewidth=1.5)
        ax.set_xlabel('Well', fontsize=10, fontweight='bold')
        ax.set_ylabel('Burst Freq (Hz)', fontsize=10, fontweight='bold')
        ax.set_title('Spontaneous Activity\n(Baseline Burst)', fontsize=11, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    
    def _plot_light_response_overall(self, ax):
        """Overall light response"""
        if self.light is None:
            ax.set_visible(False)
            return
        
        mfr = self.light[self.light['Metric'] == 'mean_firing_rate_hz']
        if mfr.empty:
            ax.set_visible(False)
            return
        
        light_codes = sorted(mfr['Light_Code'].unique())
        responses = [mfr[mfr['Light_Code'] == lc]['Response'].mean() for lc in light_codes]
        
        colors = {'BL': '#0066CC', 'GR': '#00AA00', 'OR': '#FF8800', 'RD': '#DD0000'}
        bar_colors = [colors.get(lc, '#808080') for lc in light_codes]
        
        ax.bar(light_codes, responses, alpha=0.8, color=bar_colors, edgecolor='black', linewidth=1.5)
        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
        ax.set_xlabel('Wavelength', fontsize=10, fontweight='bold')
        ax.set_ylabel('MFR Response (Hz)', fontsize=10, fontweight='bold')
        ax.set_title('Light Response\n(Overall, by Wavelength)', fontsize=11, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    
    def _plot_light_response_per_well(self, ax):
        """Per-well light response"""
        if self.light_per_well is None:
            ax.set_visible(False)
            return
        
        mfr = self.light_per_well[self.light_per_well['Metric'] == 'mean_firing_rate_hz']
        if mfr.empty:
            ax.set_visible(False)
            return
        
        wells = sorted(mfr['Well'].unique())
        responses = [mfr[mfr['Well'] == w]['Response_Mean'].iloc[0] for w in wells]
        
        ax.bar(wells, responses, alpha=0.8, color='#A23B72', edgecolor='black', linewidth=1.5)
        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
        ax.set_xlabel('Well', fontsize=10, fontweight='bold')
        ax.set_ylabel('MFR Response (Hz)', fontsize=10, fontweight='bold')
        ax.set_title('Light Response\n(Per-Well)', fontsize=11, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    
    def _plot_burst_light_response(self, ax):
        """Burst light response"""
        if self.burst_light is None:
            ax.set_visible(False)
            return
        
        burst = self.burst_light[self.burst_light['Metric'].str.contains('burst_frequency', case=False, na=False)]
        if burst.empty:
            ax.set_visible(False)
            return
        
        wells = sorted(burst['Well'].unique())
        responses = [burst[burst['Well'] == w]['Response'].mean() for w in wells]
        
        ax.bar(wells, responses, alpha=0.8, color='coral', edgecolor='black', linewidth=1.5)
        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
        ax.set_xlabel('Well', fontsize=10, fontweight='bold')
        ax.set_ylabel('Burst Response (Hz)', fontsize=10, fontweight='bold')
        ax.set_title('Light Response\n(Burst)', fontsize=11, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    
    def _plot_light_response_modulation(self, ax):
        """Light response modulation by drug (mea_dashboard.py 스타일)"""
        if self.drug_light_mod is None:
            ax.set_visible(False)
            return
        
        mfr = self.drug_light_mod[self.drug_light_mod['Metric'] == 'mean_firing_rate_hz']
        if mfr.empty:
            ax.set_visible(False)
            return
        
        # Well별 평균
        wells = sorted(mfr['Well'].unique())
        pct_changes = [mfr[mfr['Well'] == w]['Pct_Change'].mean() for w in wells]
        
        colors = ['#2E86AB' if pc >= 0 else '#A23B72' for pc in pct_changes]
        
        ax.bar(wells, pct_changes, alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
        ax.set_xlabel('Well', fontsize=10, fontweight='bold')
        ax.set_ylabel('% Change', fontsize=10, fontweight='bold')
        ax.set_title('Light Response Modulation\n(Drug Effect)', fontsize=11, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    
    def _plot_burst_drug_effect(self, ax):
        """Burst drug effect (mea_dashboard.py 스타일)"""
        if self.drug_burst is None:
            ax.set_visible(False)
            return
        
        burst = self.drug_burst[self.drug_burst['Metric'].str.contains('burst_frequency', case=False, na=False)]
        if burst.empty:
            ax.set_visible(False)
            return
        
        wells = sorted(burst['Well'].unique())
        pct_changes = [burst[burst['Well'] == w]['Pct_Change'].mean() for w in wells]
        
        colors = ['coral' if pc >= 0 else 'indianred' for pc in pct_changes]
        
        ax.bar(wells, pct_changes, alpha=0.8, color=colors, edgecolor='black', linewidth=1.5)
        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
        ax.set_xlabel('Well', fontsize=10, fontweight='bold')
        ax.set_ylabel('% Change', fontsize=10, fontweight='bold')
        ax.set_title('Burst Change\n(Drug Effect)', fontsize=11, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    
    def _plot_summary_comparison(self, ax):
        """Summary comparison"""
        if self.drug_baseline is None or self.drug_light_mod is None:
            ax.set_visible(False)
            return
        
        mfr_base = self.drug_baseline[self.drug_baseline['Metric'] == 'mean_firing_rate_hz']
        mfr_light = self.drug_light_mod[self.drug_light_mod['Metric'] == 'mean_firing_rate_hz']
        
        if mfr_base.empty or mfr_light.empty:
            ax.set_visible(False)
            return
        
        wells = sorted(set(mfr_base['Well'].unique()) & set(mfr_light['Well'].unique()))
        
        x = np.arange(len(wells))
        width = 0.25
        
        base_pct = [mfr_base[mfr_base['Well'] == w]['Pct_Change'].mean() for w in wells]
        light_pct = [mfr_light[mfr_light['Well'] == w]['Pct_Change'].mean() for w in wells]
        
        # Burst 추가
        burst_pct = []
        if self.drug_burst is not None:
            burst_data = self.drug_burst[self.drug_burst['Metric'].str.contains('burst_frequency', case=False, na=False)]
            for w in wells:
                burst_well = burst_data[burst_data['Well'] == w]
                burst_pct.append(burst_well['Pct_Change'].mean() if not burst_well.empty else 0)
        
        ax.bar(x - width, base_pct, width, label='Baseline', 
              alpha=0.8, color='#06A77D', edgecolor='black', linewidth=1.5)
        ax.bar(x, light_pct, width, label='Light Response', 
              alpha=0.8, color='#2E86AB', edgecolor='black', linewidth=1.5)
        if burst_pct:
            ax.bar(x + width, burst_pct, width, label='Burst', 
                  alpha=0.8, color='coral', edgecolor='black', linewidth=1.5)
        
        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
        ax.set_xlabel('Well', fontsize=10, fontweight='bold')
        ax.set_ylabel('% Change', fontsize=10, fontweight='bold')
        ax.set_title('Drug Effect Summary\n(Comparison)', fontsize=11, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(wells, fontsize=9)
        ax.legend(fontsize=9)
        ax.grid(axis='y', alpha=0.3)


# ============================================================================
# COMBINED EXCEL CREATOR
# ============================================================================
class CombinedExcelCreator:
    """Combined Excel 생성기"""
    
    def __init__(self, input_dir, output_path):
        self.input_dir = Path(input_dir)
        self.output_path = Path(output_path)
    
    def create(self):
        """Combined Excel 생성"""
        print('\n[COMBINE] Creating combined Excel...')
        
        files = list(self.input_dir.glob('*.xlsx'))
        files = [f for f in files if not f.name.startswith('~$')]
        
        print(f"  Found {len(files)} files to combine")
        
        with pd.ExcelWriter(self.output_path, engine='openpyxl') as writer:
            # Sheet 1: Index
            index_data = []
            for i, file_path in enumerate(files, 1):
                df_meta = pd.read_excel(file_path, sheet_name='Metadata')
                meta = df_meta.iloc[0].to_dict()
                
                index_data.append({
                    'Index': i,
                    'Filename': file_path.name,
                    'Plate_ID': meta.get('PLATE_ID', ''),
                    'BASE_STIM': meta.get('BASE_STIM', ''),
                    'Light_Code': meta.get('LIGHT_CODE', ''),
                    'Exp_Type': meta.get('EXP_TYPE', ''),
                    'Drug': meta.get('DRUG', ''),
                    'Concentration_MM': meta.get('CONCENTRATION_MM', '')
                })
            
            df_index = pd.DataFrame(index_data)
            df_index.to_excel(writer, sheet_name='Index', index=False)
            
            # Sheet 2-N: 각 파일
            for i, file_path in enumerate(files, 1):
                try:
                    df_meta = pd.read_excel(file_path, sheet_name='Metadata')
                    df_template = pd.read_excel(file_path, sheet_name='Template')
                    df_well = pd.read_excel(file_path, sheet_name='Well_Info')
                    
                    # 각 시트를 별도 탭으로
                    sheet_name = f"F{i:02d}"
                    
                    # Metadata
                    df_meta.to_excel(writer, sheet_name=f"{sheet_name}_Meta", index=False)
                    
                    # Template
                    df_template.to_excel(writer, sheet_name=f"{sheet_name}_Data", index=False)
                    
                    # Well_Info
                    df_well.to_excel(writer, sheet_name=f"{sheet_name}_Well", index=False)
                    
                except Exception as e:
                    print(f"  Warning: {file_path.name}: {e}")
                    continue
        
        print(f"  ✓ Combined Excel saved: {self.output_path.name}")
        return self


# ============================================================================
# DETAILED REPORT GENERATOR
# ============================================================================
class DetailedReportGenerator:
    """상세 요약 리포트 생성"""
    
    def __init__(self, df, analysis_dir, output_path):
        self.df = df
        self.analysis_dir = Path(analysis_dir)
        self.output_path = Path(output_path)
        
        # Load analysis results
        self.spont = None
        self.light = None
        self.light_per_well = None
        self.burst_light = None
        self.drug_baseline = None
        self.drug_light_mod = None
        self.drug_burst = None
        
        self._load_results()
    
    def _load_results(self):
        """분석 결과 로드"""
        try:
            self.spont = pd.read_csv(self.analysis_dir / '01_spontaneous' / 'spontaneous_activity.csv')
        except:
            pass
        
        try:
            self.light = pd.read_csv(self.analysis_dir / '02_light_response' / 'light_response.csv')
        except:
            pass
        
        try:
            self.light_per_well = pd.read_csv(self.analysis_dir / '02_light_response' / 'light_response_per_well.csv')
        except:
            pass
        
        try:
            self.burst_light = pd.read_csv(self.analysis_dir / '02_light_response' / 'light_response_burst.csv')
        except:
            pass
        
        try:
            self.drug_baseline = pd.read_csv(self.analysis_dir / '03_drug_effects' / 'baseline_drug_effects.csv')
        except:
            pass
        
        try:
            self.drug_light_mod = pd.read_csv(self.analysis_dir / '03_drug_effects' / 'light_response_modulation.csv')
        except:
            pass
        
        try:
            self.drug_burst = pd.read_csv(self.analysis_dir / '03_drug_effects' / 'burst_drug_effects.csv')
        except:
            pass
    
    def generate(self):
        """상세 리포트 생성"""
        print('\n[REPORT] Generating detailed report...')
        
        report = []
        report.append('='*80)
        report.append('MEA COMPREHENSIVE ANALYSIS REPORT v3.2')
        report.append('='*80)
        report.append(f'\nGenerated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        report.append('')
        
        # Data Overview
        report.extend(self._section_data_overview())
        
        # Spontaneous Activity
        if self.spont is not None:
            report.extend(self._section_spontaneous())
        
        # Light Response
        if self.light is not None:
            report.extend(self._section_light_response())
        
        # Drug Effects
        report.extend(self._section_drug_effects())
        
        # Key Findings
        report.extend(self._section_key_findings())
        
        report.append('='*80)
        report.append('END OF REPORT')
        report.append('='*80)
        
        # Save
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        print(f"  ✓ Detailed report saved: {self.output_path.name}")
        return self
    
    def _section_data_overview(self):
        """Data overview section"""
        lines = []
        lines.append('\n' + '='*80)
        lines.append('1. DATA OVERVIEW')
        lines.append('='*80)
        lines.append(f"\nTotal measurements: {len(self.df)}")
        lines.append(f"Plates analyzed: {self.df['Plate_ID'].nunique()}")
        lines.append(f"Wells analyzed: {self.df['Well'].nunique()}")
        lines.append(f"Unique metrics: {self.df['Metric'].nunique()}")
        lines.append(f"Light wavelengths: {', '.join(sorted(self.df['LIGHT_CODE'].unique()))}")
        lines.append(f"Drugs tested: {', '.join(sorted(self.df['DRUG'].unique()))}")
        lines.append(f"Experimental conditions: {', '.join(sorted(self.df['EXP_TYPE'].unique()))}")
        
        # DIFF_DAY range
        diff_day_range = (self.df['DIFF_DAY'].min(), self.df['DIFF_DAY'].max())
        lines.append(f"DIFF_DAY range: {diff_day_range[0]:.0f} - {diff_day_range[1]:.0f} days")
        
        return lines
    
    def _section_spontaneous(self):
        """Spontaneous activity section"""
        lines = []
        lines.append('\n' + '='*80)
        lines.append('2. SPONTANEOUS ACTIVITY (BASELINE ONLY)')
        lines.append('='*80)
        
        mfr = self.spont[self.spont['Metric'] == 'mean_firing_rate_hz']
        if not mfr.empty:
            lines.append(f"\nMean Firing Rate Statistics:")
            lines.append(f"  Wells analyzed: {len(mfr['Well'].unique())}")
            lines.append(f"  Mean MFR: {mfr['Mean'].mean():.4f} Hz")
            lines.append(f"  Range: {mfr['Mean'].min():.4f} - {mfr['Mean'].max():.4f} Hz")
            
            lines.append(f"\n  Per-well MFR:")
            for well in sorted(mfr['Well'].unique()):
                well_mfr = mfr[mfr['Well'] == well]['Mean'].mean()
                lines.append(f"    {well}: {well_mfr:.4f} Hz")
        
        burst = self.spont[self.spont['Metric'].str.contains('burst_frequency', case=False, na=False)]
        if not burst.empty:
            lines.append(f"\nBurst Frequency Statistics:")
            lines.append(f"  Mean burst freq: {burst['Mean'].mean():.4f} Hz")
            lines.append(f"  Range: {burst['Mean'].min():.4f} - {burst['Mean'].max():.4f} Hz")
        
        return lines
    
    def _section_light_response(self):
        """Light response section"""
        lines = []
        lines.append('\n' + '='*80)
        lines.append('3. LIGHT RESPONSE ANALYSIS')
        lines.append('='*80)
        
        # Overall
        mfr = self.light[self.light['Metric'] == 'mean_firing_rate_hz']
        if not mfr.empty:
            lines.append(f"\nOverall Light Response:")
            for light_code in sorted(mfr['Light_Code'].unique()):
                lc_data = mfr[mfr['Light_Code'] == light_code]
                lines.append(f"\n  {light_code} Light:")
                lines.append(f"    Wells tested: {len(lc_data['Well'].unique())}")
                lines.append(f"    Mean response: {lc_data['Response'].mean():.4f} Hz")
                lines.append(f"    Mean % change: {lc_data['Pct_Change'].mean():.2f}%")
        
        # Per-well
        if self.light_per_well is not None and not self.light_per_well.empty:
            lines.append(f"\nPer-Well Light Response (MFR):")
            mfr_well = self.light_per_well[self.light_per_well['Metric'] == 'mean_firing_rate_hz']
            for well in sorted(mfr_well['Well'].unique()):
                well_data = mfr_well[mfr_well['Well'] == well].iloc[0]
                lines.append(f"  {well}: {well_data['Response_Mean']:.4f} Hz ({well_data['Pct_Change_Mean']:.2f}%)")
        
        # Burst
        if self.burst_light is not None and not self.burst_light.empty:
            lines.append(f"\nBurst Response to Light:")
            burst_freq = self.burst_light[self.burst_light['Metric'].str.contains('burst_frequency', case=False, na=False)]
            if not burst_freq.empty:
                lines.append(f"  Mean burst response: {burst_freq['Response'].mean():.4f} Hz")
                lines.append(f"  Mean % change: {burst_freq['Pct_Change'].mean():.2f}%")
        
        return lines
    
    def _section_drug_effects(self):
        """Drug effects section"""
        lines = []
        lines.append('\n' + '='*80)
        lines.append('4. DRUG EFFECTS ANALYSIS')
        lines.append('='*80)
        
        # Baseline effect
        if self.drug_baseline is not None and not self.drug_baseline.empty:
            mfr = self.drug_baseline[self.drug_baseline['Metric'] == 'mean_firing_rate_hz']
            if not mfr.empty:
                lines.append(f"\nBaseline Activity Drug Effect:")
                for drug in sorted(mfr['Drug_Name'].unique()):
                    drug_data = mfr[mfr['Drug_Name'] == drug]
                    lines.append(f"\n  {drug}:")
                    lines.append(f"    Wells tested: {len(drug_data['Well'].unique())}")
                    lines.append(f"    Control MFR: {drug_data['Control'].mean():.4f} Hz")
                    lines.append(f"    Drug MFR: {drug_data['Drug'].mean():.4f} Hz")
                    lines.append(f"    Mean effect: {drug_data['Difference'].mean():.4f} Hz ({drug_data['Pct_Change'].mean():.2f}%)")
        
        # Light modulation
        if self.drug_light_mod is not None and not self.drug_light_mod.empty:
            mfr_mod = self.drug_light_mod[self.drug_light_mod['Metric'] == 'mean_firing_rate_hz']
            if not mfr_mod.empty:
                lines.append(f"\nLight Response Modulation by Drug:")
                lines.append(f"  Mean modulation: {mfr_mod['Modulation'].mean():.4f} Hz")
                lines.append(f"  Mean % change: {mfr_mod['Pct_Change'].mean():.2f}%")
                
                lines.append(f"\n  Per-well modulation:")
                for well in sorted(mfr_mod['Well'].unique()):
                    well_data = mfr_mod[mfr_mod['Well'] == well].iloc[0]
                    lines.append(f"    {well}: {well_data['Modulation']:.4f} Hz ({well_data['Pct_Change']:.2f}%)")
        
        # Burst effect
        if self.drug_burst is not None and not self.drug_burst.empty:
            burst_freq = self.drug_burst[self.drug_burst['Metric'].str.contains('burst_frequency', case=False, na=False)]
            if not burst_freq.empty:
                lines.append(f"\nBurst Drug Effect:")
                lines.append(f"  Mean % change: {burst_freq['Pct_Change'].mean():.2f}%")
        
        return lines
    
    def _section_key_findings(self):
        """Key findings section"""
        lines = []
        lines.append('\n' + '='*80)
        lines.append('5. KEY FINDINGS & SUMMARY')
        lines.append('='*80)
        lines.append('')
        
        # Most active well
        if self.spont is not None:
            mfr = self.spont[self.spont['Metric'] == 'mean_firing_rate_hz']
            if not mfr.empty:
                well_means = mfr.groupby('Well')['Mean'].mean().sort_values(ascending=False)
                lines.append(f"• Most active well (baseline): {well_means.index[0]} (MFR: {well_means.iloc[0]:.4f} Hz)")
        
        # Strongest light response
        if self.light is not None:
            mfr = self.light[self.light['Metric'] == 'mean_firing_rate_hz']
            if not mfr.empty:
                max_resp = mfr.loc[mfr['Response'].idxmax()]
                lines.append(f"• Strongest light response: {max_resp['Well']} with {max_resp['Light_Code']} ({max_resp['Response']:.4f} Hz, {max_resp['Pct_Change']:.2f}%)")
        
        # Strongest drug effect
        if self.drug_baseline is not None:
            mfr = self.drug_baseline[self.drug_baseline['Metric'] == 'mean_firing_rate_hz']
            if not mfr.empty:
                max_eff = mfr.loc[mfr['Difference'].abs().idxmax()]
                lines.append(f"• Strongest baseline drug effect: {max_eff['Well']} with {max_eff['Drug_Name']} ({max_eff['Difference']:.4f} Hz, {max_eff['Pct_Change']:.2f}%)")
        
        # Light modulation
        if self.drug_light_mod is not None:
            mfr_mod = self.drug_light_mod[self.drug_light_mod['Metric'] == 'mean_firing_rate_hz']
            if not mfr_mod.empty:
                max_mod = mfr_mod.loc[mfr_mod['Modulation'].abs().idxmax()]
                lines.append(f"• Strongest light response modulation: {max_mod['Well']} ({max_mod['Modulation']:.4f} Hz, {max_mod['Pct_Change']:.2f}%)")
        
        # Burst effect
        if self.drug_burst is not None and not self.drug_burst.empty:
            burst = self.drug_burst[self.drug_burst['Metric'].str.contains('burst_frequency', case=False, na=False)]
            if not burst.empty:
                max_burst = burst.loc[burst['Pct_Change'].abs().idxmax()]
                lines.append(f"• Strongest burst drug effect: {max_burst['Well']} ({max_burst['Pct_Change']:.2f}%)")
        
        return lines


# ============================================================================
# AUTO ANALYZER
# ============================================================================
class AutoAnalyzer:
    """통합 자동 분석기 v3.2"""
    
    def __init__(self, input_dir, output_dir):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.df = None
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def run(self):
        """전체 분석 실행"""
        print('='*80)
        print('MEA AUTOMATIC ANALYZER v3.2 - REVISED')
        print('='*80)
        print('\nRevisions:')
        print('  1. ✓ Per-well: Fixed color code')
        print('  2. ✓ Spontaneous: Baseline only analysis')
        print('  3. ✓ Light Response: Per-well + Burst analysis added')
        print('  4. ✓ Drug Effects: Light response + Burst effects added')
        print('  5. ✓ Dashboard: Enhanced with mea_dashboard.py style')
        print('='*80)
        
        # Load
        print('\n[LOAD] Loading data...')
        loader = OptimizedFormatLoader(self.input_dir)
        self.df = loader.load_all()
        
        if self.df.empty:
            print('❌ No data loaded!')
            return
        
        # Combined Excel
        combined_path = self.output_dir / 'COMBINED_DATA.xlsx'
        combiner = CombinedExcelCreator(self.input_dir, combined_path)
        combiner.create()
        
        # Per-well (Enhanced with Color Code Fix)
        perwell = PerWellAnalyzerEnhanced(self.df, self.output_dir)
        perwell.analyze()
        
        # Spontaneous (Baseline Only)
        spont = SpontaneousAnalyzer(self.df, self.output_dir)
        spont.analyze().visualize()
        
        # Light response (with Per-Well and Burst)
        light = LightResponseAnalyzer(self.df, self.output_dir)
        light.analyze().visualize()
        
        # Drug effects (with Light Response and Burst)
        drug = DrugEffectAnalyzer(self.df, self.output_dir)
        drug.analyze().visualize()
        
        # Enhanced Dashboard
        dashboard_path = self.output_dir / 'MASTER_DASHBOARD.png'
        dashboard = EnhancedDashboard(self.output_dir, dashboard_path)
        dashboard.create()
        
        # Detailed Report
        report_path = self.output_dir / f'DETAILED_REPORT_{self.timestamp}.txt'
        report_gen = DetailedReportGenerator(self.df, self.output_dir, report_path)
        report_gen.generate()
        
        print('\n' + '='*80)
        print('✅ ANALYSIS COMPLETE!')
        print('='*80)
        print(f'\nResults: {self.output_dir}')
        print('\nGenerated:')
        print('  📁 00_per_well/ (enhanced with FIXED color code)')
        print('  📁 01_spontaneous/ (BASELINE ONLY)')
        print('  📁 02_light_response/ (with PER-WELL + BURST)')
        print('  📁 03_drug_effects/ (with LIGHT RESPONSE + BURST)')
        print('  📊 MASTER_DASHBOARD.png (ENHANCED)')
        print('  📄 DETAILED_REPORT.txt')
        print('  📊 COMBINED_DATA.xlsx')
        print('='*80)
        
        return self


# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    analyzer = AutoAnalyzer(
        input_dir=r"D:\MEAdata\#7-1\improved",
        output_dir=r"D:\MEAdata\#7-1\analysis"
    )
    analyzer.run()