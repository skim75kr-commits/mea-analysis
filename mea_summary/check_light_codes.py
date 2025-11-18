import pandas as pd
from pathlib import Path

files = list(Path(r'D:\MyProjects\summary\Data_LightResponse').glob('*.xlsx'))
files = [f for f in files if not f.name.startswith('~$')]
print('Files found:', len(files))

all_codes = set()
for f in files:
    df = pd.read_excel(f, sheet_name='Overall')
    codes = df['Light_Code'].unique()
    all_codes.update(codes)
    print(f'{f.name}: {codes}')

print('\nAll Light Codes:', sorted(all_codes))
