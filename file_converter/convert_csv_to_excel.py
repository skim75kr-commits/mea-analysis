import pandas as pd
import numpy as np
import json
import os
import glob
import re
import sys
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

# Get target directory from command line argument
if len(sys.argv) > 1:
    target_dir = os.path.abspath(sys.argv[1])
else:
    print("Usage: python convert_csv_to_excel.py <target_folder>")
    print("Example: python convert_csv_to_excel.py #7-1")
    sys.exit(1)

if not os.path.isdir(target_dir):
    print(f"Error: Directory '{target_dir}' does not exist!")
    sys.exit(1)

# Load configuration from target directory
config_file = os.path.join(target_dir, 'config.json')
if not os.path.exists(config_file):
    print(f"Error: config.json not found in '{target_dir}'!")
    sys.exit(1)

with open(config_file, 'r', encoding='utf-8') as f:
    config = json.load(f)

print(f"Loading configuration from {config_file}")
print(f"Target directory: {target_dir}")
print()

# Find all CSV files in subdirectories of target directory
csv_pattern = os.path.join(target_dir, '**', '*.csv')
csv_files = glob.glob(csv_pattern, recursive=True)

if not csv_files:
    print("No CSV files found in subdirectories!")
    sys.exit(1)

print(f"Found {len(csv_files)} CSV file(s) to process:")
for csv_file in csv_files:
    print(f"  - {csv_file}")
print()

# Create Well_Info dataframe from config
print("\n" + "="*80)
print("WELL INFORMATION (from config.json)")
print("="*80)

common_well_info_data = []
# All 24 wells
common_wells = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6',
                'B1', 'B2', 'B3', 'B4', 'B5', 'B6',
                'C1', 'C2', 'C3', 'C4', 'C5', 'C6',
                'D1', 'D2', 'D3', 'D4', 'D5', 'D6']

# Check if well_info exists in config
well_info_config = config.get('well_info', {})

for well in common_wells:
    if well in well_info_config:
        diff_day = well_info_config[well].get('Differentiation_Day', None)
    else:
        diff_day = None

    if diff_day == '':
        diff_day = np.nan

    common_well_info_data.append({
        'Well': well,
        'Differentiation_Day': diff_day,
        'DIV': None  # Will be calculated per file based on DAYS_POST_PLATING
    })

common_well_info_df = pd.DataFrame(common_well_info_data)

print("\n" + "="*80)
print("Well_Info Summary (will be applied to ALL files):")
print("="*80)
print(common_well_info_df)
print()

# Process each CSV file
for csv_file in csv_files:
    print(f"\n{'='*80}")
    print(f"Processing: {os.path.basename(csv_file)}")
    print(f"{'='*80}")

    csv_basename = os.path.splitext(os.path.basename(csv_file))[0]
    csv_dir = os.path.basename(os.path.dirname(csv_file))

    # Determine BASE or STIM from folder name
    base_stim = 'UNKNOWN'
    time_duration = None
    time_start = None

    # First, check config folder_mapping (this takes priority)
    for folder_key, folder_value in config.get('folder_mapping', {}).items():
        if folder_key in csv_dir:
            base_stim = folder_value
            break

    # Try to extract time range from folder name (format: XXX-YYY)
    time_match = re.search(r'(\d+)-(\d+)', csv_dir)
    if time_match:
        start_time = int(time_match.group(1))
        end_time = int(time_match.group(2))
        time_duration = end_time - start_time
        time_start = start_time

        if base_stim == 'UNKNOWN':
            if start_time == 0:
                base_stim = 'BASE'
            else:
                base_stim = 'STIM'

    # Extract plate number
    plate_matches = re.findall(r'P\d+', csv_basename)
    if plate_matches:
        plate_id = max(plate_matches, key=len)
    else:
        plate_id = config['metadata'].get('PLATE_ID', 'UNKNOWN')

    # Extract color
    color_map = {'Blue': 'BL', 'Green': 'GR', 'Orange': 'OG', 'Red': 'RD'}
    color = 'UNKNOWN'
    for full_name, abbr in color_map.items():
        if full_name in csv_basename:
            color = abbr
            break

    # Determine treatment and experiment type based on filename prefix
    # Priority: Check specific prefixes first, then fall back to config
    if 'KCl' in csv_basename:
        exp_type = 'DRUG'
        drug = 'KCL'
        concentration = 0.5
    elif 'Washout' in csv_basename or csv_basename.startswith('(Washout)'):
        # Washout files: exp_type=WASHOUT, drug from config (the drug being washed out)
        exp_type = 'WASHOUT'
        drug = config['metadata'].get('DRUG', 'NONE')
        concentration = config['metadata'].get('CONCENTRATION (uM)', 0)
    elif '8BcGMP' in csv_basename or '8-Br-cGMP' in csv_basename or '8-Br-cGAMP' in csv_basename:
        # Drug treatment files (e.g., (1000uM-8BcGMP)...)
        exp_type = 'DRUG'
        drug = '8-Br-cGAMP'
        concentration = config['metadata'].get('CONCENTRATION (uM)', 1000)
    elif csv_basename.startswith('(') and ')' in csv_basename:
        # Parse drug info from filename prefix: (XXuM_DRUGNAME) or (XXuM-DRUGNAME)
        prefix_match = re.match(r'\((\d+)uM[_-]([^)]+)\)', csv_basename)
        if prefix_match:
            exp_type = 'DRUG'
            concentration = float(prefix_match.group(1))
            drug = prefix_match.group(2).strip()
        else:
            # Fallback to config values if pattern doesn't match
            exp_type = 'DRUG'
            drug = config['metadata'].get('DRUG', 'UNKNOWN')
            concentration = config['metadata'].get('CONCENTRATION (uM)', 0)
    else:
        # No prefix = Control files
        exp_type = 'CONTROL'
        drug = 'NONE'
        concentration = 0

    # Extract day info
    day_info = re.search(r'D(\d+)', csv_dir)
    day = day_info.group(1) if day_info else str(config['metadata'].get('DAYS_POST_PLATING', '0'))
    day_label = f'D{day}'

    intensity = config['metadata'].get('INTENSITY(%)', 10)

    # Create file-specific well_info_df with DIV calculated
    file_well_info_df = common_well_info_df.copy()
    days_post_plating = int(day)
    file_well_info_df['DIV'] = file_well_info_df['Differentiation_Day'].apply(
        lambda x: x + days_post_plating if pd.notna(x) else np.nan
    )

    # Create output folder
    output_folder_name = f"dataset_{plate_id}_{day}"
    output_folder = os.path.join(target_dir, output_folder_name)
    os.makedirs(output_folder, exist_ok=True)

    # Create filename with exp_type distinction
    # Include concentration for DRUG type to differentiate between different concentrations
    if exp_type == 'WASHOUT':
        simplified_name = f"{plate_id}({day_label}_{base_stim})_{color}_{intensity}_WASHOUT.xlsx"
    elif exp_type == 'DRUG' and concentration > 0:
        # Format concentration: use integer if whole number, otherwise keep decimal
        conc_str = str(int(concentration)) if concentration == int(concentration) else str(concentration)
        simplified_name = f"{plate_id}({day_label}_{base_stim})_{color}_{intensity}_{drug}_{conc_str}uM.xlsx"
    else:
        simplified_name = f"{plate_id}({day_label}_{base_stim})_{color}_{intensity}_{drug}.xlsx"
    output_file = os.path.join(output_folder, simplified_name)

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        data = []
        for line in lines:
            data.append(line.strip().split(','))

        max_cols = max(len(row) for row in data)
        for row in data:
            while len(row) < max_cols:
                row.append('')

        df_full = pd.DataFrame(data)

        # Find the "Well Averages" row dynamically
        well_header_row = None
        for idx, row in df_full.iterrows():
            if row[0] == 'Well Averages':
                well_header_row = idx
                break

        if well_header_row is None:
            raise ValueError("Could not find 'Well Averages' row in CSV file")

        print(f"Found 'Well Averages' at row {well_header_row}")

        # Data starts 2 rows after Well Averages header
        data_start_row = well_header_row + 2

        # Find end of data (empty row or Measurement section)
        data_end_row = data_start_row
        for idx in range(data_start_row, len(df_full)):
            cell_value = str(df_full.iloc[idx, 0]).strip()
            if cell_value == '' or cell_value.startswith('Measurement'):
                break
            data_end_row = idx + 1

        print(f"Data rows: {data_start_row} to {data_end_row}")

        # Dynamically detect wells from the Well Averages row
        wells_row = df_full.iloc[well_header_row, 1:].tolist()
        actual_wells = [str(w).strip() for w in wells_row if pd.notna(w) and str(w).strip() and str(w).strip() != '']
        num_wells = len(actual_wells)
        print(f"Detected {num_wells} wells: {actual_wells}")

        # Extract wells
        wells_series = df_full.iloc[well_header_row, 1:num_wells+1]
        wells = [str(w).strip() if pd.notna(w) and str(w).strip() else f"Unknown_{i}" for i, w in enumerate(wells_series, 1)]
        print("Wells:", wells)

        # Extract metric names
        metrics_series = df_full.iloc[data_start_row:data_end_row, 0]
        metrics = [str(m).strip() if pd.notna(m) else f"Metric_{i}" for i, m in enumerate(metrics_series)]
        print(f"Number of metrics: {len(metrics)}")

        # Extract data values
        data_values = df_full.iloc[data_start_row:data_end_row, 1:num_wells+1].values
        print(f"Data shape: {data_values.shape}")

        if len(data_values.shape) == 1:
            data_values = data_values.reshape(-1, len(wells))

        # Create Template dataframe
        template_df = pd.DataFrame(data_values, columns=wells)
        template_df.insert(0, 'Metric', metrics)

        # Convert numeric strings to numbers
        for col in wells:
            if col in template_df.columns:
                template_df[col] = pd.to_numeric(template_df[col], errors='coerce')

        # Filter out wells with low spike count
        min_spike_count = config.get('filtering', {}).get('min_spike_count', 10)
        for col in wells:
            if col in template_df.columns:
                num_spikes = template_df[col].iloc[0] if pd.notna(template_df[col].iloc[0]) else 0
                if num_spikes < min_spike_count:
                    print(f"Filtering out {col}: spikes={num_spikes}")
                    template_df[col] = np.nan

        # Reorder columns
        ordered_cols = ['Metric'] + [w for w in common_wells if w in wells]
        for w in wells:
            if w not in ordered_cols:
                ordered_cols.append(w)

        for col in ordered_cols:
            if col != 'Metric' and col not in template_df.columns:
                template_df[col] = np.nan

        final_cols = [col for col in ordered_cols if col in template_df.columns]
        template_df = template_df[final_cols]

        template_df['Unit'] = np.nan
        template_df['Condition'] = np.nan

        print("\nTemplate preview:")
        print(template_df.head())

        # Set time settings
        if time_duration is None or time_start is None:
            base_stim_lower = base_stim.lower()
            if base_stim_lower in config.get('time_settings', {}):
                time_key = base_stim_lower
            else:
                time_key = 'base'

            if time_key in config.get('time_settings', {}):
                time_duration = config['time_settings'][time_key]['TIME_DURATION(sec)']
                time_start = config['time_settings'][time_key]['TIME_START']
            else:
                time_duration = 60
                time_start = 0

        metadata_df = pd.DataFrame({
            'PLATE_ID': [plate_id],
            'BASE_STIM': [base_stim],
            'TIME_DURATION(sec)': [time_duration],
            'TIME_START': [time_start],
            'PLATING_DATE': [config['metadata'].get('PLATING_DATE', '')],
            'EXPERIMENT_DATE': [config['metadata'].get('EXPERIMENT_DATE', '')],
            'DAYS_POST_PLATING': [int(day)],
            'LIGHT_CODE': [color],
            'INTENSITY(%)': [intensity],
            'EXP_TYPE': [exp_type],
            'DRUG': [drug],
            'CONCENTRATION (uM)': [concentration]
        })

        print("\nMetadata:")
        print(metadata_df)

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
            template_df.to_excel(writer, sheet_name='Template', index=False)
            file_well_info_df.to_excel(writer, sheet_name='Well_Info', index=False)

        print(f"\n[SUCCESS] File saved: {output_file}")

    except Exception as e:
        print(f"\n[ERROR] Failed to process {csv_file}: {str(e)}")
        import traceback
        traceback.print_exc()
        continue

print(f"\n{'='*80}")
print(f"All CSV files processed!")
print(f"{'='*80}")
