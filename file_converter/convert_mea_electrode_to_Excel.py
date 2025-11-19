import pandas as pd
import numpy as np
import json
import os
import glob
import re
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

# Load configuration
config_file = 'config.json'
with open(config_file, 'r', encoding='utf-8') as f:
    config = json.load(f)

print(f"Loading configuration from {config_file}")
print()

# Get the base directory
base_dir = os.path.dirname(os.path.abspath(__file__))

# Find all CSV files in subdirectories
csv_pattern = os.path.join(base_dir, '**', '*.csv')
csv_files = glob.glob(csv_pattern, recursive=True)

if not csv_files:
    print("No CSV files found in subdirectories!")
    exit(1)

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

# Check if well_info exists in config, otherwise use default Plating DAY
well_info_config = config.get('well_info', {})
default_plating_day = config['metadata'].get('Plating DAY', '')

for well in common_wells:
    # Get values from config
    if well in well_info_config:
        diff_day = well_info_config[well].get('Differentiation_Day', default_plating_day)
        notes = well_info_config[well].get('Notes', '')
    else:
        diff_day = default_plating_day
        notes = ''

    # Convert empty strings to NaN for consistency
    if diff_day == '':
        diff_day = np.nan
    if notes == '':
        notes = np.nan

    common_well_info_data.append({
        'Well': well,
        'Differentiation_Day': diff_day,
        'Notes': notes
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

    # Generate simplified output filename
    csv_basename = os.path.splitext(os.path.basename(csv_file))[0]
    csv_dir = os.path.basename(os.path.dirname(csv_file))

    # Determine BASE or STIM from folder name by parsing time range
    # Expected format: "0-300" (seconds), "300-600" (seconds), etc.
    base_stim = 'UNKNOWN'
    time_duration = None
    time_start = None

    # First, check config folder_mapping (this takes priority)
    for folder_key, folder_value in config['folder_mapping'].items():
        if folder_key in csv_dir:
            base_stim = folder_value
            break

    # Try to extract time range from folder name (format: XXX-YYY)
    time_match = re.search(r'(\d+)-(\d+)', csv_dir)
    if time_match:
        start_time = int(time_match.group(1))
        end_time = int(time_match.group(2))

        # Calculate duration and start time
        time_duration = end_time - start_time
        time_start = start_time

        # Only set base_stim if it wasn't already set by folder_mapping
        if base_stim == 'UNKNOWN':
            # If start time is 0, it's BASE; otherwise it's STIM
            if start_time == 0:
                base_stim = 'BASE'
            else:
                base_stim = 'STIM'

    # Extract plate number (P214, P217, P227, P911 etc) - use from config if available
    # Find all P followed by digits and choose the longest one (e.g., P911 over P4)
    plate_matches = re.findall(r'P\d+', csv_basename)
    if plate_matches:
        # Sort by length descending to get the longest match (P911 > P4)
        plate_id = max(plate_matches, key=len)
    else:
        plate_id = config['metadata'].get('PLATE_ID', 'UNKNOWN')

    # Extract color (Blue, Green, Orange, Red)
    color_map = {
        'Blue': 'BL',
        'Green': 'GR',
        'Orange': 'OG',
        'Red': 'RD'
    }
    color = 'UNKNOWN'
    for full_name, abbr in color_map.items():
        if full_name in csv_basename:
            color = abbr
            break

    # Determine treatment and experiment type from config and filename
    if 'KCl' in csv_basename:
        exp_type = 'DRUG'
        drug = 'KCL'
        concentration = 0.5  # default KCl concentration
    else:
        exp_type = config['metadata'].get('EXP_TYPE', 'CONTROL')
        drug = config['metadata'].get('DRUG', 'NONE')
        concentration = config['metadata'].get('CONCENTRATION (mM)', 0)

    # Create simplified filename: P911(D19_STIM)_OG_10_NONE.xlsx
    day_info = re.search(r'D(\d+)', csv_dir)
    day = day_info.group(1) if day_info else str(config['metadata'].get('Plating DAY', '0'))  # Extract from folder or config
    day_label = f'D{day}'  # For filename use D19 format

    intensity = config['metadata'].get('INTENSITY(%)', 10)  # Get from config

    # Create output folder: dataset_PlateID_PlatingDay
    output_folder_name = f"dataset_{plate_id}_{day}_electrode"
    output_folder = os.path.join(base_dir, output_folder_name)

    # Create folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    simplified_name = f"{plate_id}({day_label}_{base_stim})_{color}_{intensity}_{drug}_electrode.xlsx"
    output_file = os.path.join(output_folder, simplified_name)

    try:
        # Read the entire CSV line by line to handle variable column counts
        with open(csv_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Parse lines into a list of lists
        data = []
        for line in lines:
            data.append(line.strip().split(','))

        # Convert to dataframe
        max_cols = max(len(row) for row in data)
        # Pad rows with fewer columns
        for row in data:
            while len(row) < max_cols:
                row.append('')

        df_full = pd.DataFrame(data)

        # Find row 171 (0-indexed: row 170) which is the header
        header_row = 170
        data_start_row = 171  # Row 172 in Excel (0-indexed: 171)
        data_end_row = 188  # Row 189 in Excel (0-indexed: 188)

        # Extract electrode IDs from header row (columns B to NU = columns 1 to 572)
        # Each well has 16 electrodes: A1_11, A1_12, ..., A1_44, A2_11, ...
        electrode_ids_series = df_full.iloc[header_row, 1:573]
        electrode_ids = electrode_ids_series.tolist() if hasattr(electrode_ids_series, 'tolist') else list(electrode_ids_series)
        # Clean up electrode IDs
        electrode_ids = [str(e).strip() if pd.notna(e) and str(e).strip() else f"Unknown_{i}" for i, e in enumerate(electrode_ids, 1)]
        print(f"Number of electrodes: {len(electrode_ids)}")

        # Extract metric names from column A (rows 172-189, 0-indexed: 171-188)
        metrics_series = df_full.iloc[data_start_row:data_end_row+1, 0]
        metrics = metrics_series.tolist() if hasattr(metrics_series, 'tolist') else list(metrics_series)
        # Clean up metrics list
        metrics = [str(m).strip() if pd.notna(m) else f"Metric_{i}" for i, m in enumerate(metrics)]
        print(f"Number of metrics: {len(metrics)}")

        # Extract data values (rows 172-189, columns B-NU)
        data_values = df_full.iloc[data_start_row:data_end_row+1, 1:573].values
        print(f"Data shape: {data_values.shape}")

        # Ensure data_values is 2D array
        if len(data_values.shape) == 1:
            data_values = data_values.reshape(-1, len(electrode_ids))

        # Create the Template dataframe
        template_df = pd.DataFrame(data_values, columns=electrode_ids)

        # Insert metrics column - ensure metrics is a list/Series
        if isinstance(metrics, (list, tuple, pd.Series)):
            template_df.insert(0, 'Metric', metrics)
        else:
            raise ValueError(f"metrics must be a list, tuple, or Series, got {type(metrics)}")

        # Convert numeric strings to numbers
        for col in electrode_ids:
            if col in template_df.columns:
                template_df[col] = pd.to_numeric(template_df[col], errors='coerce')

        # Filter out electrodes with low spike count
        min_spike_count = config['filtering']['min_spike_count']

        # Assume first metric is "Number of Spikes"
        spike_row_idx = 0

        for col in electrode_ids:
            if col in template_df.columns:
                # Get Number of Spikes value (first row)
                num_spikes = template_df[col].iloc[spike_row_idx] if pd.notna(template_df[col].iloc[spike_row_idx]) else 0

                # If very low spike count, remove the electrode data
                if num_spikes <= min_spike_count:
                    print(f"Filtering out {col}: spikes={num_spikes}")
                    template_df[col] = np.nan

        # Add Unit and Condition columns
        template_df['Unit'] = np.nan
        template_df['Condition'] = np.nan

        print("\nTemplate preview:")
        print(template_df.head())

        # Create Metadata from config (override BASE_STIM from folder name)
        # Use time settings from folder parsing if available, otherwise use config
        if time_duration is None or time_start is None:
            # Map BASE_STIM to time_settings key (case-insensitive)
            base_stim_lower = base_stim.lower()

            # Check if the key exists in time_settings, otherwise use default
            if base_stim_lower in config.get('time_settings', {}):
                time_key = base_stim_lower
            elif base_stim_lower == 'base':
                time_key = 'base'
            elif base_stim_lower == 'stim':
                time_key = 'stim'
            else:
                time_key = 'base'  # default fallback

            # Safely get time settings
            if time_key in config.get('time_settings', {}):
                time_duration = config['time_settings'][time_key]['TIME_DURATION(sec)']
                time_start = config['time_settings'][time_key]['TIME_START']
            else:
                # Fallback to base settings if requested key doesn't exist
                time_duration = config['time_settings']['base']['TIME_DURATION(sec)']
                time_start = config['time_settings']['base']['TIME_START']

        metadata_df = pd.DataFrame({
            'PLATE_ID': [plate_id],
            'BASE_STIM': [base_stim],
            'TIME_DURATION(sec)': [time_duration],
            'TIME_START': [time_start],
            'Plating DAY': [int(day)],  # Use extracted day value
            'LIGHT_CODE': [color],
            'INTENSITY(%)': [intensity],
            'EXP_TYPE': [exp_type],
            'DRUG': [drug],
            'CONCENTRATION (mM)': [concentration]
        })

        print("\nMetadata:")
        print(metadata_df)

        # Write to Excel file (using common well_info for all files)
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
            template_df.to_excel(writer, sheet_name='Template', index=False)
            common_well_info_df.to_excel(writer, sheet_name='Well_Info', index=False)

        print(f"\n[SUCCESS] File saved: {output_file}")

    except Exception as e:
        print(f"\n[ERROR] Failed to process {csv_file}: {str(e)}")
        continue

print(f"\n{'='*80}")
print(f"All CSV files processed!")
print(f"{'='*80}")
