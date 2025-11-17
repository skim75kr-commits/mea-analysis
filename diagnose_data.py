"""
MEA Data Diagnostics - 데이터 문제 진단
======================================
데이터가 제대로 로드되지 않을 때 사용
"""

import pandas as pd
from pathlib import Path

def diagnose_data(input_dir):
    """데이터 진단"""
    
    input_path = Path(input_dir)
    
    print("="*80)
    print("MEA DATA DIAGNOSTICS")
    print("="*80)
    print(f"\n📂 Checking: {input_path}")
    
    # 1. 디렉토리 확인
    if not input_path.exists():
        print(f"\n❌ Directory does not exist: {input_path}")
        return
    
    print(f"✓ Directory exists")
    
    # 2. Excel 파일 찾기
    excel_files = list(input_path.glob('*.xlsx'))
    excel_files = [f for f in excel_files if not f.name.startswith('~$')]
    
    print(f"\n📄 Found {len(excel_files)} Excel files:")
    
    if len(excel_files) == 0:
        print("❌ No Excel files found!")
        print("\n💡 Make sure you have .xlsx files in:")
        print(f"   {input_path}")
        return
    
    for f in excel_files:
        print(f"  • {f.name}")
    
    # 3. 각 파일 검사
    print("\n" + "="*80)
    print("DETAILED FILE INSPECTION")
    print("="*80)
    
    for i, file_path in enumerate(excel_files, 1):
        print(f"\n[{i}/{len(excel_files)}] {file_path.name}")
        print("-" * 60)
        
        try:
            # Excel 파일 열기
            xl = pd.ExcelFile(file_path)
            sheet_names = xl.sheet_names
            
            print(f"  📋 Sheets found: {sheet_names}")
            
            # 필수 시트 확인
            required_sheets = ['Metadata', 'Template', 'Well_Info']
            missing_sheets = [s for s in required_sheets if s not in sheet_names]
            
            if missing_sheets:
                print(f"  ❌ Missing required sheets: {missing_sheets}")
                print(f"  💡 Required sheets: {required_sheets}")
                continue
            else:
                print(f"  ✓ All required sheets present")
            
            # Metadata 시트 확인
            print("\n  📊 Metadata sheet:")
            df_meta = pd.read_excel(file_path, sheet_name='Metadata')
            print(f"    Shape: {df_meta.shape}")
            print(f"    Columns: {df_meta.columns.tolist()}")
            if len(df_meta) > 0:
                print(f"    First row: {df_meta.iloc[0].to_dict()}")
            
            # Template 시트 확인
            print("\n  📊 Template sheet:")
            df_template = pd.read_excel(file_path, sheet_name='Template')
            print(f"    Shape: {df_template.shape}")
            print(f"    Columns: {df_template.columns.tolist()}")
            print(f"    First few rows:")
            print(df_template.head())
            
            # Well_Info 시트 확인
            print("\n  📊 Well_Info sheet:")
            df_well = pd.read_excel(file_path, sheet_name='Well_Info')
            print(f"    Shape: {df_well.shape}")
            print(f"    Columns: {df_well.columns.tolist()}")
            print(f"    First few rows:")
            print(df_well.head())
            
            # 데이터 변환 시도
            print("\n  🔄 Testing data conversion...")
            try:
                from mea_auto_analyzer_v32 import OptimizedFormatLoader
                loader = OptimizedFormatLoader(input_path)
                
                # 한 파일만 테스트
                metadata = df_meta.iloc[0].to_dict()
                rows = loader._to_long_format(df_template, df_well, metadata, file_path.stem)
                
                if len(rows) > 0:
                    print(f"  ✓ Conversion successful: {len(rows)} rows created")
                    print(f"    Sample row keys: {rows[0].keys()}")
                    print(f"    Sample row: {rows[0]}")
                else:
                    print(f"  ⚠ Conversion returned 0 rows")
                    
            except Exception as e:
                print(f"  ❌ Conversion failed: {e}")
                import traceback
                traceback.print_exc()
            
        except Exception as e:
            print(f"  ❌ Error reading file: {e}")
            import traceback
            traceback.print_exc()
    
    # 4. 전체 로드 테스트
    print("\n" + "="*80)
    print("FULL LOAD TEST")
    print("="*80)
    
    try:
        from mea_auto_analyzer_v32 import OptimizedFormatLoader
        loader = OptimizedFormatLoader(input_path)
        df = loader.load_all()
        
        if df.empty:
            print("❌ No data loaded!")
        else:
            print(f"✓ Successfully loaded {len(df)} rows")
            print(f"\nColumns: {df.columns.tolist()}")
            print(f"\nData info:")
            print(df.info())
            print(f"\nFirst few rows:")
            print(df.head())
            
            if 'Well' in df.columns:
                print(f"\n✓ Wells: {sorted(df['Well'].unique())}")
            
            if 'Metric' in df.columns:
                print(f"✓ Metrics: {sorted(df['Metric'].unique())}")
                
    except Exception as e:
        print(f"❌ Full load failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("DIAGNOSIS COMPLETE")
    print("="*80)


# ============================================================================
# USAGE
# ============================================================================
if __name__ == '__main__':
    # 🔧 여기에 진단할 경로 입력
    diagnose_data(r"D:\MyProjects\#4-1")
