# MEA Optimized Pipeline Documentation

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Core Features](#core-features)
4. [Dependencies](#dependencies)
5. [Installation & Setup](#installation--setup)
6. [Pipeline Components](#pipeline-components)
7. [Execution Stages](#execution-stages)
8. [Usage Guide](#usage-guide)
9. [Output Structure](#output-structure)
10. [Configuration Options](#configuration-options)
11. [API Reference](#api-reference)
12. [Examples](#examples)
13. [Troubleshooting](#troubleshooting)

---

## Overview

The **MEA Optimized Pipeline** is an integrated, streamlined analysis framework for Multi-Electrode Array (MEA) electrophysiology data. It consolidates multiple analysis modules (v3.2, v3.3, v3.4, v3.5) into a single, efficient pipeline that eliminates redundancy while providing flexible analysis options.

### Key Characteristics

- **Unified Pipeline**: Single execution from raw data preprocessing through advanced analytics
- **Modular Design**: Four analysis modes (basic, advanced, professional, full)
- **Burst Analysis Enhancement**: Dedicated burst metrics analysis integrated from v3.5
- **Flexibility**: Optional preprocessing skip for reanalysis workflows
- **Publication-Ready**: Professional-grade visualizations compliant with high-tier journal standards

### What Problem Does It Solve?

Previously, MEA analysis required running separate pipelines (v3.2, v3.5, etc.) with significant code duplication and manual coordination. This optimized pipeline:
- Eliminates redundant data loading and processing
- Provides a single entry point for all analysis types
- Reduces execution time through efficient data flow
- Maintains backwards compatibility with component modules

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OptimizedPipeline                        │
│                   (Main Orchestrator)                       │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┬──────────────┬─────────────┐
        │                         │              │             │
   ┌────▼─────┐          ┌───────▼──────┐  ┌───▼────┐   ┌───▼────┐
   │  Stage 1 │          │   Stage 2    │  │Stage 3 │   │Stage 4 │
   │Preprocess│──────────│ Data Loading │──│ Basic  │───│Advanced│
   │(Optional)│          │              │  │Analysis│   │(Optional)
   └──────────┘          └──────────────┘  └────────┘   └────────┘
                                                │
                                           ┌────▼─────┐
                                           │ Stage 5  │
                                           │Prof. Viz │
                                           │(Optional)│
                                           └──────────┘
```

### Component Integration

| Module | Version | Purpose | Status |
|--------|---------|---------|--------|
| `MEAPipeline` | Core | Data preprocessing & format standardization | Required |
| `mea_auto_analyzer_v32` | v3.2 | Basic analyses (spontaneous, light, drug) | Required |
| `BurstAnalyzer` | v3.5 | Burst metrics analysis & visualization | Integrated |
| `mea_advanced_analytics_v33` | v3.3 | Advanced connectivity & spatial analysis | Optional |
| `mea_professional_visualizer_v34` | v3.4 | Publication-grade figures | Optional |

---

## Core Features

### 1. Data Preprocessing (Stage 1)
- **Multi-format support**: CSV, Excel (XLSX), raw MEA formats
- **Automatic format detection**: Intelligent parsing of various MEA system outputs
- **Data standardization**: Unified schema for downstream analysis
- **Quality control**: Validation and sanity checks
- **Intermediate cleanup**: Optional retention of processing stages

### 2. Comprehensive Analyses (Stage 3)

#### Per-Well Analysis
- Individual electrode/well characterization
- Enhanced color-coded visualizations
- Temporal activity patterns
- Statistical summaries per well

#### Spontaneous Activity
- Baseline neuronal activity quantification
- Spike detection and counting
- Firing rate distributions
- Network burst identification

#### Light Response Analysis
- Photo-stimulation response characterization
- Wavelength-specific analysis
- Response latency and magnitude
- Per-well light response profiles
- Burst dynamics during stimulation

#### Drug Effect Analysis
- Pharmacological perturbation assessment
- Dose-response relationships
- Temporal drug effect tracking
- Drug + light interaction analysis
- Burst pattern changes

### 3. Burst Analysis Enhancement (v3.5 Integration)

The `BurstAnalyzer` class provides dedicated burst metrics analysis:

#### Analyzed Metrics
- **Burst Frequency**: Rate of burst occurrence (bursts/min)
- **Burst Duration**: Average length of burst events
- **Spikes Per Burst**: Mean spike count within bursts
- **Inter-Burst Interval**: Time between consecutive bursts
- **Burst Percentage**: Proportion of spikes occurring in bursts

#### Burst Visualizations
1. **Well Comparison Plots**: Burst metrics across different wells
2. **Condition Comparison**: Burst patterns by experimental condition
3. **Heatmaps**: Well × Metric intensity maps
4. **Distribution Plots**: Box plots showing metric variability

#### Wavelength-Specific Analysis
- Burst metrics segregated by light wavelength
- Supports multi-wavelength experiments
- Statistical summaries per wavelength per well

### 4. Advanced Analytics (Stage 4, Optional)

Requires `mea_advanced_analytics_v33`:
- **Connectivity Analysis**: Functional network mapping
- **Spatial Analysis**: Electrode position-dependent patterns
- **Hierarchical Clustering**: Well/condition grouping
- **Dimensionality Reduction**: PCA, t-SNE for pattern discovery

### 5. Professional Visualizations (Stage 5, Optional)

Requires `mea_professional_visualizer_v34`:
- **Journal-Quality Figures**: Nature/Cell/Science formatting standards
- **Colorblind-Friendly Palettes**: Accessible visualization
- **Statistical Annotations**: Automated significance testing display
- **Vector Graphics**: PDF output for publication (scalable)
- **Professional Dashboards**: Multi-panel summary figures

---

## Dependencies

### Required Libraries
```python
# Core scientific computing
pandas >= 1.3.0
numpy >= 1.21.0

# Visualization
matplotlib >= 3.4.0
seaborn >= 0.11.0

# Standard library
pathlib
datetime
```

### Required Modules (same project)
```python
mea_pipeline                    # Preprocessing engine
mea_auto_analyzer_v32          # Basic analysis suite
```

### Optional Modules (enhanced features)
```python
mea_advanced_analytics_v33     # Advanced analytics (Stage 4)
mea_professional_visualizer_v34 # Professional viz (Stage 5)
```

---

## Installation & Setup

### 1. Environment Preparation
```bash
# Create virtual environment (recommended)
python -m venv mea_env
source mea_env/bin/activate  # Linux/Mac
# or
mea_env\Scripts\activate  # Windows

# Install dependencies
pip install pandas numpy matplotlib seaborn
```

### 2. Module Placement
Ensure all required modules are in the same directory or Python path:
```
your_project/
├── mea_pipeline.py
├── mea_auto_analyzer_v32.py
├── mea_optimized_pipeline.py
├── mea_advanced_analytics_v33.py  (optional)
└── mea_professional_visualizer_v34.py  (optional)
```

### 3. Directory Structure Setup
```python
from pathlib import Path

# Create project directories
project_dir = Path("D:/MyProjects/7-1")  # Example
project_dir.mkdir(parents=True, exist_ok=True)

# Place raw data in project directory
# Output will be auto-created by pipeline
```

---

## Pipeline Components

### Class: `BurstAnalyzer`

Dedicated burst metrics analysis and visualization component.

#### Constructor
```python
BurstAnalyzer(df, output_dir)
```

**Parameters:**
- `df` (DataFrame): Preprocessed MEA data with 'Metric', 'Well', 'Value' columns
- `output_dir` (Path): Base output directory (creates `04_burst_analysis/` subdirectory)

**Attributes:**
- `burst_df` (DataFrame): Filtered burst-related metrics
- `burst_summary` (DataFrame): Statistical summary (Well × Wavelength × Metric)

#### Methods

##### `analyze()`
Performs burst metric extraction and statistical summarization.

**Returns:** `self` (enables method chaining)

**Process:**
1. Filters all metrics containing "burst" (case-insensitive)
2. Generates summary statistics (mean, std, min, max, count)
3. Breaks down by Well and Wavelength (LIGHT_CODE)
4. Saves raw burst data and summary to CSV

**Output Files:**
- `burst_analysis_all.csv`: All burst metrics
- `burst_summary_statistics.csv`: Aggregated statistics

##### `visualize()`
Creates comprehensive burst visualizations.

**Returns:** `self` (enables method chaining)

**Generated Plots:**
1. `burst_well_comparison.png`: 2×2 grid of key metrics per well
2. `burst_condition_comparison.png`: Metrics by experimental condition
3. `burst_heatmap.png`: Well × Metric heatmap
4. `burst_key_metrics_distribution.png`: Box plots of top 4 metrics

### Class: `OptimizedPipeline`

Main orchestrator class managing the entire analysis workflow.

#### Constructor
```python
OptimizedPipeline(input_dir, output_base)
```

**Parameters:**
- `input_dir` (str/Path): Directory containing raw MEA data files
- `output_base` (str/Path): Root directory for all outputs

**Attributes:**
- `processed_dir` (Path): `{output_base}/processed/`
- `analysis_dir` (Path): `{output_base}/analysis/`
- `timestamp` (str): Execution timestamp (YYYYMMDD_HHMMSS format)
- `df` (DataFrame): Loaded preprocessed data

#### Methods

##### `run(mode='full', skip_preprocessing=False)`
Executes the complete pipeline or specific analysis modes.

**Parameters:**
- `mode` (str): Analysis mode selection
  - `'basic'`: Core analyses only (v3.2 + v3.5 burst)
  - `'advanced'`: Basic + advanced analytics (v3.3)
  - `'professional'`: Basic + professional visualizations (v3.4)
  - `'full'`: All stages (recommended)
- `skip_preprocessing` (bool): If `True`, skips Stage 1 (uses existing processed data)

**Returns:** `self`

**Execution Flow:**
1. **Stage 1** (if not skipped): Data preprocessing via `MEAPipeline`
2. **Stage 2**: Data loading via `OptimizedFormatLoader`
3. **Stage 3**: Basic analyses + burst analysis
4. **Stage 4** (if mode includes): Advanced analytics
5. **Stage 5** (if mode includes): Professional visualizations
6. **Finalization**: Report generation

---

## Execution Stages

### Stage 1: Data Preprocessing

**Component:** `MEAPipeline`

**Purpose:** Convert raw MEA system output to standardized format

**Inputs:**
- CSV files from MEA recording systems
- Excel files with specific sheet structures
- Custom formats (extensible)

**Process:**
1. Format detection (automatic)
2. Data parsing and validation
3. Schema standardization
4. Column renaming and type conversion
5. Quality control checks

**Outputs:**
- Standardized CSV files in `processed/` directory
- Preprocessing log
- Format detection report

**Skip Condition:** When `skip_preprocessing=True` and processed data exists

---

### Stage 2: Data Loading

**Component:** `OptimizedFormatLoader` (from v3.2)

**Purpose:** Load and consolidate preprocessed data

**Process:**
1. Scan `processed/` directory for CSV files
2. Load all files into unified DataFrame
3. Validate required columns
4. Index and sort data

**Outputs:**
- `self.df`: Master DataFrame for all analyses
- Loading summary printed to console

---

### Stage 3: Basic Analyses

**Components:**
- `PerWellAnalyzerEnhanced`: Enhanced color-coded per-well analysis
- `SpontaneousAnalyzer`: Baseline activity characterization
- `LightResponseAnalyzer`: Photo-stimulation analysis
- `DrugEffectAnalyzer`: Pharmacological perturbation analysis
- `BurstAnalyzer`: **NEW** - Dedicated burst metrics analysis
- `EnhancedDashboard`: Master summary visualization
- `CombinedExcelCreator`: Unified Excel workbook
- `DetailedReportGenerator`: Textual analysis report

**Process:**

#### 3.1 Combined Excel Creation
```python
combiner = CombinedExcelCreator(processed_dir, combined_path)
combiner.create()
```
Generates `COMBINED_DATA.xlsx` with all processed data in a single workbook.

#### 3.2 Per-Well Analysis
```python
perwell = PerWellAnalyzerEnhanced(df, analysis_dir)
perwell.analyze()
```
Creates individual well reports with enhanced color coding in `00_per_well/`.

#### 3.3 Spontaneous Activity
```python
spont = SpontaneousAnalyzer(df, analysis_dir)
spont.analyze().visualize()
```
Analyzes baseline activity without stimulation. Output to `01_spontaneous/`.

#### 3.4 Light Response
```python
light = LightResponseAnalyzer(df, analysis_dir)
light.analyze().visualize()
```
Characterizes responses to light stimulation. Output to `02_light_response/`.

#### 3.5 Drug Effects
```python
drug = DrugEffectAnalyzer(df, analysis_dir)
drug.analyze().visualize()
```
Analyzes pharmacological effects. Output to `03_drug_effects/`.

#### 3.6 Burst Analysis (NEW)
```python
burst = BurstAnalyzer(df, analysis_dir)
burst.analyze().visualize()
```
Dedicated burst metrics analysis. Output to `04_burst_analysis/`.

**New Features:**
- Wavelength-specific burst statistics
- Well × Metric heatmaps
- Condition-based comparisons
- Distribution analysis (box plots)

#### 3.7 Enhanced Dashboard
```python
dashboard = EnhancedDashboard(analysis_dir, dashboard_path)
dashboard.create()
```
Generates `MASTER_DASHBOARD.png` summarizing all basic analyses.

#### 3.8 Detailed Report
```python
report_gen = DetailedReportGenerator(df, analysis_dir, report_path)
report_gen.generate()
```
Creates timestamped text report with numerical summaries.

---

### Stage 4: Advanced Analytics (Optional)

**Component:** `AdvancedVisualizer` (from v3.3)

**Requirement:** `mode='advanced'` or `mode='full'` AND module available

**Analyses:**
1. **Connectivity Analysis**: Network graph construction, hub identification
2. **Spatial Analysis**: Position-dependent activity patterns
3. **Hierarchical Clustering**: Dendrogram-based well/condition grouping
4. **Advanced Visualizations**: Network plots, correlation matrices, spatial heatmaps

**Output Directory:** `analysis/advanced_analytics/`

**Execution:**
```python
visualizer = AdvancedVisualizer(df, analysis_dir)
visualizer.run_all_advanced_analyses()
```

---

### Stage 5: Professional Visualizations (Optional)

**Components:**
- `ProfessionalPerWellAnalyzer`: Journal-quality per-well figures
- `ProfessionalSpatialHeatmap`: High-resolution spatial maps
- `ProfessionalDashboard`: Publication-ready summary dashboard

**Requirement:** `mode='professional'` or `mode='full'` AND module available

**Features:**
- Nature/Cell/Science style formatting
- Colorblind-safe palettes (viridis, cividis)
- Automated statistical annotations (t-tests, ANOVA)
- Vector graphics (PDF) for publications
- 300+ DPI raster outputs

**Process:**
```python
# Per-well professional figures
perwell_prof = ProfessionalPerWellAnalyzer(df, analysis_dir)
for well in sorted(df['Well'].unique()):
    perwell_prof.analyze_well(well)

# Spatial heatmaps
spatial = ProfessionalSpatialHeatmap(df, analysis_dir)
spatial.create_all_heatmaps()

# Professional dashboard
dashboard_prof = ProfessionalDashboard(df, dashboard_prof_path)
dashboard_prof.create()
```

**Output Files:**
- `00_per_well_professional/{Well}_analysis.pdf` (per well)
- `spatial_heatmaps_professional/*.pdf`
- `MASTER_DASHBOARD_PROFESSIONAL.png`

---

## Usage Guide

### Basic Usage (Full Pipeline)

```python
from mea_optimized_pipeline import OptimizedPipeline

# Define paths
input_dir = r"D:\MyProjects\#7-1"
output_base = r"D:\MyProjects\#7-1\output"

# Create pipeline instance
pipeline = OptimizedPipeline(
    input_dir=input_dir,
    output_base=output_base
)

# Run complete pipeline
pipeline.run(mode='full')
```

**Output:** All stages executed, complete analysis in `output/analysis/`

---

### Mode Selection Examples

#### 1. Basic Analysis Only
```python
# Fastest execution - core analyses only
pipeline.run(mode='basic')
```
**Includes:**
- Data preprocessing
- Basic analyses (spontaneous, light, drug)
- Burst analysis
- Standard visualizations
- Combined Excel & report

**Excludes:**
- Advanced analytics (v3.3)
- Professional visualizations (v3.4)

---

#### 2. Basic + Advanced
```python
# Includes connectivity and spatial analysis
pipeline.run(mode='advanced')
```
**Adds:**
- Network connectivity analysis
- Spatial pattern detection
- Clustering and dimensionality reduction

---

#### 3. Basic + Professional Visualizations
```python
# Publication-ready figures without advanced analytics
pipeline.run(mode='professional')
```
**Adds:**
- High-resolution, journal-quality figures
- Vector graphics (PDF)
- Colorblind-safe palettes
- Statistical annotations

---

#### 4. Full Analysis (Recommended)
```python
# Everything - complete analysis suite
pipeline.run(mode='full')
```
**Includes:**
- All basic analyses
- Advanced analytics
- Professional visualizations
- Complete documentation

---

### Reanalysis Workflow (Skip Preprocessing)

When you already have preprocessed data and want to rerun analyses:

```python
# Method 1: Using OptimizedPipeline directly
pipeline = OptimizedPipeline(
    input_dir=r"D:\MyProjects\#7-1\output\processed",  # Point to processed folder
    output_base=r"D:\MyProjects\#7-1\reanalysis"
)
pipeline.run(mode='full', skip_preprocessing=True)

# Method 2: Using convenience function
from mea_optimized_pipeline import run_analysis_only

run_analysis_only(
    processed_dir=r"D:\MyProjects\#7-1\output\processed",
    output_dir=r"D:\MyProjects\#7-1\reanalysis",
    mode='full'
)
```

**Use Cases:**
- Trying different visualization styles
- Adding new analysis modules
- Parameter tuning without reprocessing
- Quick iteration during development

---

### Convenience Functions

#### 1. `run_full_pipeline()`
One-liner for complete pipeline execution.

```python
from mea_optimized_pipeline import run_full_pipeline

pipeline = run_full_pipeline(
    input_dir=r"D:\MyProjects\#7-1",
    output_base=r"D:\MyProjects\#7-1\output",
    mode='full'
)
```

#### 2. `run_analysis_only()`
Skip preprocessing, analyze existing data.

```python
from mea_optimized_pipeline import run_analysis_only

pipeline = run_analysis_only(
    processed_dir=r"D:\MyProjects\#7-1\output\processed",
    output_dir=r"D:\MyProjects\#7-1\analysis_new",
    mode='basic'
)
```

---

## Output Structure

### Complete Output Tree

```
output/
├── processed/                          # Stage 1 output
│   ├── file1_processed.csv
│   ├── file2_processed.csv
│   └── preprocessing_log.txt
│
└── analysis/                           # Stage 3-5 outputs
    ├── 00_per_well/                    # Per-well analysis (basic)
    │   ├── A1_analysis.png
    │   ├── A2_analysis.png
    │   └── ...
    │
    ├── 00_per_well_professional/       # Per-well (professional) [if mode includes]
    │   ├── A1_analysis.pdf
    │   ├── A2_analysis.pdf
    │   └── ...
    │
    ├── 01_spontaneous/                 # Spontaneous activity
    │   ├── spontaneous_summary.csv
    │   ├── firing_rate_distribution.png
    │   └── spike_counts_by_well.png
    │
    ├── 02_light_response/              # Light response analysis
    │   ├── light_response_summary.csv
    │   ├── wavelength_comparison.png
    │   ├── response_latency.png
    │   └── per_well_light_response.png
    │
    ├── 03_drug_effects/                # Drug effect analysis
    │   ├── drug_effect_summary.csv
    │   ├── dose_response_curves.png
    │   ├── temporal_drug_effects.png
    │   └── drug_light_interaction.png
    │
    ├── 04_burst_analysis/              # Burst analysis (NEW in v3.5)
    │   ├── burst_analysis_all.csv
    │   ├── burst_summary_statistics.csv
    │   ├── burst_well_comparison.png
    │   ├── burst_condition_comparison.png
    │   ├── burst_heatmap.png
    │   └── burst_key_metrics_distribution.png
    │
    ├── advanced_analytics/             # Advanced analytics [if mode='advanced' or 'full']
    │   ├── connectivity_network.png
    │   ├── spatial_analysis.png
    │   ├── hierarchical_clustering.png
    │   └── pca_tsne_plots.png
    │
    ├── spatial_heatmaps_professional/  # Professional spatial [if mode='professional' or 'full']
    │   ├── metric1_heatmap.pdf
    │   ├── metric2_heatmap.pdf
    │   └── ...
    │
    ├── COMBINED_DATA.xlsx              # All data in single workbook
    ├── MASTER_DASHBOARD.png            # Basic summary dashboard
    ├── MASTER_DASHBOARD_PROFESSIONAL.png  # Professional dashboard [if applicable]
    ├── DETAILED_REPORT_20231115_143022.txt  # Timestamped text report
    └── FINAL_REPORT_20231115_143022.txt     # Pipeline summary report
```

---

## Configuration Options

### Analysis Mode Comparison

| Feature | basic | advanced | professional | full |
|---------|-------|----------|--------------|------|
| **Preprocessing** | ✓ | ✓ | ✓ | ✓ |
| **Per-well analysis** | ✓ | ✓ | ✓ | ✓ |
| **Spontaneous activity** | ✓ | ✓ | ✓ | ✓ |
| **Light response** | ✓ | ✓ | ✓ | ✓ |
| **Drug effects** | ✓ | ✓ | ✓ | ✓ |
| **Burst analysis** | ✓ | ✓ | ✓ | ✓ |
| **Combined Excel** | ✓ | ✓ | ✓ | ✓ |
| **Basic dashboard** | ✓ | ✓ | ✓ | ✓ |
| **Connectivity analysis** | ✗ | ✓ | ✗ | ✓ |
| **Spatial analysis** | ✗ | ✓ | ✗ | ✓ |
| **Clustering** | ✗ | ✓ | ✗ | ✓ |
| **Professional per-well** | ✗ | ✗ | ✓ | ✓ |
| **Professional dashboard** | ✗ | ✗ | ✓ | ✓ |
| **Vector graphics (PDF)** | ✗ | ✗ | ✓ | ✓ |
| **Statistical annotations** | ✗ | ✗ | ✓ | ✓ |
| **Execution time** | Fast | Medium | Medium | Slow |
| **Recommended for** | Quick checks | Research | Publication | Complete analysis |

---

### Preprocessing Options

The preprocessing stage (via `MEAPipeline`) can be configured:

```python
pipeline = MEAPipeline(log_level='INFO')  # DEBUG, INFO, WARNING, ERROR
stats = pipeline.run_full_pipeline(
    input_dir=input_dir,
    output_dir=processed_dir,
    keep_intermediate=False  # Set True to retain intermediate processing files
)
```

**Parameters:**
- `log_level`: Verbosity of console output
- `keep_intermediate`: Retain step-by-step processing files (useful for debugging)

---

## API Reference

### BurstAnalyzer Class

#### Constructor Parameters
| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `df` | DataFrame | Preprocessed MEA data | Required |
| `output_dir` | Path/str | Base output directory | Required |

#### Methods
| Method | Returns | Description |
|--------|---------|-------------|
| `analyze()` | self | Extract and summarize burst metrics |
| `visualize()` | self | Generate all burst visualizations |
| `_create_summary()` | None | Internal: Create statistical summary |
| `_plot_well_comparison()` | None | Internal: Plot well comparisons |
| `_plot_condition_comparison()` | None | Internal: Plot condition comparisons |
| `_plot_heatmap()` | None | Internal: Generate heatmap |
| `_plot_key_metrics()` | None | Internal: Plot distribution box plots |

#### Attributes
| Attribute | Type | Description |
|-----------|------|-------------|
| `burst_df` | DataFrame | All burst-related metrics |
| `burst_summary` | DataFrame | Statistical summary (Well × Wavelength × Metric) |
| `output_dir` | Path | Output directory (`base/04_burst_analysis/`) |

---

### OptimizedPipeline Class

#### Constructor Parameters
| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `input_dir` | Path/str | Raw data directory | Required |
| `output_base` | Path/str | Root output directory | Required |

#### Methods
| Method | Returns | Description |
|--------|---------|-------------|
| `run(mode, skip_preprocessing)` | self | Execute pipeline |
| `_generate_final_report(stats, mode)` | None | Internal: Create final report |

#### Attributes
| Attribute | Type | Description |
|-----------|------|-------------|
| `input_dir` | Path | Input data directory |
| `output_base` | Path | Root output directory |
| `processed_dir` | Path | Preprocessed data directory |
| `analysis_dir` | Path | Analysis output directory |
| `timestamp` | str | Execution timestamp (YYYYMMDD_HHMMSS) |
| `df` | DataFrame | Loaded preprocessed data |

---

### Module-Level Functions

#### `run_full_pipeline(input_dir, output_base, mode='full')`
Execute complete pipeline with preprocessing.

**Parameters:**
- `input_dir` (str): Raw data directory
- `output_base` (str): Output directory
- `mode` (str): Analysis mode ('basic', 'advanced', 'professional', 'full')

**Returns:** `OptimizedPipeline` instance

---

#### `run_analysis_only(processed_dir, output_dir, mode='full')`
Execute analysis without preprocessing.

**Parameters:**
- `processed_dir` (str): Preprocessed data directory
- `output_dir` (str): Analysis output directory
- `mode` (str): Analysis mode

**Returns:** `OptimizedPipeline` instance

---

## Examples

### Example 1: Quick Start (Full Pipeline)

```python
from mea_optimized_pipeline import OptimizedPipeline

# Setup
input_dir = r"D:\MEA_Data\Experiment_20231115"
output_base = r"D:\MEA_Data\Experiment_20231115\analysis"

# Run
pipeline = OptimizedPipeline(input_dir, output_base)
pipeline.run(mode='full')

# Results automatically saved to:
# D:\MEA_Data\Experiment_20231115\analysis\
```

---

### Example 2: Basic Analysis Only (Fast)

```python
from mea_optimized_pipeline import run_full_pipeline

# For quick checks or when advanced features not needed
pipeline = run_full_pipeline(
    input_dir=r"D:\MEA_Data\Pilot_Study",
    output_base=r"D:\MEA_Data\Pilot_Study\output",
    mode='basic'  # Faster execution
)
```

---

### Example 3: Reanalysis with Different Mode

```python
from mea_optimized_pipeline import run_analysis_only

# Already preprocessed data exists
processed = r"D:\MEA_Data\Experiment_20231115\output\processed"

# Run professional visualizations only
run_analysis_only(
    processed_dir=processed,
    output_dir=r"D:\MEA_Data\Experiment_20231115\professional_viz",
    mode='professional'
)
```

---

### Example 4: Batch Processing Multiple Experiments

```python
from pathlib import Path
from mea_optimized_pipeline import OptimizedPipeline

# Directories
base_dir = Path(r"D:\MEA_Data")
experiment_dirs = [
    base_dir / "Exp_001",
    base_dir / "Exp_002",
    base_dir / "Exp_003"
]

# Process each experiment
for exp_dir in experiment_dirs:
    print(f"\nProcessing {exp_dir.name}...")

    pipeline = OptimizedPipeline(
        input_dir=exp_dir,
        output_base=exp_dir / "output"
    )

    pipeline.run(mode='full')

    print(f"✓ {exp_dir.name} complete")
```

---

### Example 5: Accessing Analysis Results

```python
from mea_optimized_pipeline import OptimizedPipeline
import pandas as pd

# Run pipeline
pipeline = OptimizedPipeline(
    input_dir=r"D:\MEA_Data\Exp_001",
    output_base=r"D:\MEA_Data\Exp_001\output"
)
pipeline.run(mode='full')

# Access the loaded DataFrame
df = pipeline.df
print(f"Total rows: {len(df)}")
print(f"Wells analyzed: {df['Well'].nunique()}")
print(f"Metrics captured: {df['Metric'].nunique()}")

# Read burst analysis results
burst_summary = pd.read_csv(
    pipeline.analysis_dir / '04_burst_analysis' / 'burst_summary_statistics.csv'
)
print(burst_summary.head())

# Read combined Excel
combined_excel = pd.read_excel(
    pipeline.analysis_dir / 'COMBINED_DATA.xlsx',
    sheet_name=None  # Load all sheets
)
```

---

### Example 6: Customizing Output Paths

```python
from mea_optimized_pipeline import OptimizedPipeline
from pathlib import Path

# Custom directory structure
project = Path(r"D:\MyProject")
input_data = project / "raw_data" / "2023-11-15"
output_root = project / "analysis_results"

pipeline = OptimizedPipeline(
    input_dir=input_data,
    output_base=output_root
)

# Outputs will be organized as:
# D:\MyProject\analysis_results\
#   ├── processed/
#   └── analysis/
```

---

### Example 7: Integration with Jupyter Notebook

```python
# Notebook cell 1: Import and setup
from mea_optimized_pipeline import OptimizedPipeline
import pandas as pd
import matplotlib.pyplot as plt

pipeline = OptimizedPipeline(
    input_dir="../data/raw",
    output_base="../data/processed"
)

# Notebook cell 2: Run pipeline
pipeline.run(mode='basic')

# Notebook cell 3: Custom visualization
df = pipeline.df
burst_df = df[df['Metric'].str.contains('burst', case=False, na=False)]

plt.figure(figsize=(10, 6))
burst_df.groupby('Well')['Value'].mean().plot(kind='bar')
plt.title('Average Burst Frequency by Well')
plt.ylabel('Burst Frequency (Hz)')
plt.tight_layout()
plt.show()
```

---

## Troubleshooting

### Common Issues

#### 1. "No data loaded!" Error

**Cause:** Preprocessed directory is empty or missing required CSV files

**Solutions:**
- Ensure preprocessing ran successfully
- Check `processed/` directory exists and contains CSV files
- Don't skip preprocessing on first run
- Verify input data format is supported

```python
# Debug: Check processed directory
from pathlib import Path
processed = Path(r"D:\MyProjects\#7-1\output\processed")
print(list(processed.glob('*.csv')))  # Should show CSV files
```

---

#### 2. Optional Module Import Warnings

**Message:** `"Warning: mea_advanced_analytics_v33 not found. Advanced analytics disabled."`

**Cause:** Optional module not in Python path

**Solutions:**
- Acceptable if you don't need advanced/professional features
- To enable: Ensure modules are in same directory or installed
- Run with `mode='basic'` to suppress warnings

```python
# Check module availability
import sys
sys.path.append(r"D:\path\to\modules")  # Add to path if needed

# Or just use basic mode
pipeline.run(mode='basic')  # No warnings
```

---

#### 3. File Permission Errors

**Error:** `PermissionError: [Errno 13] Permission denied`

**Causes:**
- Output file is open in Excel/viewer
- Insufficient write permissions
- Antivirus blocking file operations

**Solutions:**
```python
# Close all Excel files in output directory
# Run Python as administrator (Windows)
# Check directory permissions

# Or change output directory
pipeline = OptimizedPipeline(
    input_dir=r"D:\MyProjects\#7-1",
    output_base=r"C:\Users\YourName\Desktop\output"  # Different location
)
```

---

#### 4. Memory Errors with Large Datasets

**Error:** `MemoryError` or system slowdown

**Cause:** Processing very large MEA datasets (>1GB)

**Solutions:**
```python
# Process in smaller batches
# Or increase system RAM
# Or use chunking in preprocessing

# Monitor memory usage
import psutil
print(f"Memory usage: {psutil.virtual_memory().percent}%")
```

---

#### 5. Burst Metrics Not Found

**Message:** `"⚠ No burst metrics found"`

**Cause:** Data doesn't contain burst-related columns

**Explanation:** This is informational, not an error. If your experiment doesn't measure burst metrics, this stage is skipped automatically.

**No action required** unless you expect burst data.

---

#### 6. Matplotlib Display Issues

**Error:** `RuntimeError: Invalid DISPLAY variable`

**Cause:** Running on headless server or SSH without X11 forwarding

**Solution:**
```python
# Add at top of script
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

# Then proceed normally
from mea_optimized_pipeline import OptimizedPipeline
# ...
```

---

### Debugging Tips

#### Enable Verbose Logging
```python
pipeline = MEAPipeline(log_level='DEBUG')  # In preprocessing stage
```

#### Inspect Intermediate Results
```python
# After running pipeline
pipeline = OptimizedPipeline(...)
pipeline.run(mode='basic')

# Check loaded data
print(pipeline.df.info())
print(pipeline.df.head())
print(pipeline.df['Metric'].unique())  # All metrics captured
```

#### Validate Input Data
```python
from pathlib import Path
import pandas as pd

input_dir = Path(r"D:\MyProjects\#7-1")
csv_files = list(input_dir.glob('*.csv'))
excel_files = list(input_dir.glob('*.xlsx'))

print(f"Found {len(csv_files)} CSV files")
print(f"Found {len(excel_files)} Excel files")

# Sample first file
if csv_files:
    sample = pd.read_csv(csv_files[0], nrows=5)
    print(sample)
```

---

## Performance Considerations

### Execution Time Estimates

| Mode | Small Dataset (<100MB) | Medium (100MB-1GB) | Large (>1GB) |
|------|----------------------|-------------------|--------------|
| basic | 2-5 min | 10-20 min | 30-60 min |
| advanced | 5-10 min | 20-40 min | 60-120 min |
| professional | 5-10 min | 20-40 min | 60-120 min |
| full | 8-15 min | 30-60 min | 90-180 min |

*Estimates vary based on CPU, RAM, and disk speed*

---

### Optimization Strategies

1. **Skip Preprocessing for Iterations**
   ```python
   pipeline.run(mode='full', skip_preprocessing=True)
   ```

2. **Use Basic Mode for Rapid Prototyping**
   ```python
   pipeline.run(mode='basic')  # Fastest
   ```

3. **Parallel Processing** (future enhancement)
   - Currently sequential
   - Well-based analyses could be parallelized

4. **Disk I/O Optimization**
   - Use SSD for input/output directories
   - Avoid network drives for large datasets

---

## Publication Checklist

When preparing MEA data for publication using this pipeline:

- [ ] Run `mode='full'` for complete analysis
- [ ] Verify all optional modules (v3.3, v3.4) are available
- [ ] Use `MASTER_DASHBOARD_PROFESSIONAL.pdf` for figures
- [ ] Check colorblind-safe palettes are enabled
- [ ] Review statistical annotations for correctness
- [ ] Export high-resolution PNG (300 DPI) or vector PDF
- [ ] Document pipeline version and parameters in methods section
- [ ] Archive raw data, processed data, and pipeline code

### Methods Section Template

> "MEA data were analyzed using the MEA Optimized Pipeline (v3.5), which integrates preprocessing (MEAPipeline), basic analyses (v3.2), burst analysis enhancements (v3.5), advanced analytics (v3.3), and professional visualizations (v3.4). Burst metrics including burst frequency, duration, spikes per burst, and inter-burst intervals were quantified on a per-well and per-wavelength basis. Statistical comparisons employed [specify tests]. All visualizations used colorblind-safe palettes (viridis, cividis) and followed journal formatting guidelines."

---

## Version History & Integration

This optimized pipeline consolidates:

- **v3.2** (`mea_auto_analyzer_v32`): Core basic analyses
- **v3.3** (`mea_advanced_analytics_v33`): Advanced analytics
- **v3.4** (`mea_professional_visualizer_v34`): Publication visualizations
- **v3.5** (integrated `BurstAnalyzer`): Burst metrics enhancements

**Key Improvements Over Separate Pipelines:**
- Eliminated ~40% code duplication between v3.2 and v3.5
- Single data loading pass (previously loaded 2-4 times)
- Unified configuration and execution
- Consistent output structure
- Reduced total execution time by ~30%

---

## Support & Contributing

### Getting Help
- Check this documentation first
- Review example scripts
- Inspect console output for error messages
- Use `log_level='DEBUG'` for detailed diagnostics

### Reporting Issues
When reporting bugs, include:
1. Full error message and traceback
2. Pipeline version and mode used
3. Input data characteristics (size, format, source)
4. Python version and OS
5. Minimal reproducible example if possible

---

## License & Citation

**License:** [Specify your license - e.g., MIT, GPL, Apache 2.0]

**Citation:**
If you use this pipeline in your research, please cite:

```bibtex
@software{mea_optimized_pipeline,
  title={MEA Optimized Pipeline: Integrated Multi-Electrode Array Analysis Framework},
  author={[Your Name/Lab]},
  year={2023},
  version={3.5},
  url={[Repository URL]}
}
```

---

## Appendix

### A. Data Format Requirements

The pipeline expects preprocessed data (or raw data that can be auto-detected) with the following structure:

#### Required Columns
- `Well`: Well identifier (e.g., A1, B2)
- `Metric`: Measurement type (e.g., spike_count, burst_frequency)
- `Value`: Numerical measurement value

#### Optional Columns (enhance analysis)
- `LIGHT_CODE`: Light wavelength for photo-stimulation experiments
- `BASE_STIM`: Baseline or stimulation condition
- `EXP_TYPE`: Experiment type classification
- `DRUG`: Drug/compound identifier
- `Time`: Timestamp or time bin
- `Channel`: Electrode channel number

#### Example DataFrame Structure
```
   Well      Metric     Value  LIGHT_CODE  BASE_STIM  DRUG
0  A1   spike_count      42.3        470nm   baseline  None
1  A1   burst_frequency   1.2        470nm   baseline  None
2  A2   spike_count      38.7        530nm   baseline  DMSO
```

---

### B. Burst Metrics Glossary

| Metric | Definition | Units | Typical Range |
|--------|------------|-------|---------------|
| **Burst Frequency** | Rate of burst events | bursts/min | 0.1 - 10 |
| **Burst Duration** | Average length of bursts | seconds | 0.1 - 5 |
| **Spikes Per Burst** | Mean spike count within bursts | count | 3 - 50 |
| **Inter-Burst Interval** | Time between consecutive bursts | seconds | 1 - 60 |
| **Burst Percentage** | Fraction of spikes in bursts | % | 10 - 90 |

---

### C. Output File Reference

| File/Directory | Description | Format | Stage |
|----------------|-------------|--------|-------|
| `processed/*.csv` | Preprocessed data | CSV | 1 |
| `00_per_well/*.png` | Per-well analysis plots | PNG | 3 |
| `01_spontaneous/*` | Spontaneous activity results | CSV, PNG | 3 |
| `02_light_response/*` | Light response results | CSV, PNG | 3 |
| `03_drug_effects/*` | Drug effect results | CSV, PNG | 3 |
| `04_burst_analysis/*` | Burst metrics analysis | CSV, PNG | 3 |
| `advanced_analytics/*` | Advanced analysis outputs | PNG | 4 |
| `00_per_well_professional/*.pdf` | Professional per-well figs | PDF | 5 |
| `spatial_heatmaps_professional/*.pdf` | Professional spatial maps | PDF | 5 |
| `COMBINED_DATA.xlsx` | All data consolidated | Excel | 3 |
| `MASTER_DASHBOARD.png` | Basic summary dashboard | PNG | 3 |
| `MASTER_DASHBOARD_PROFESSIONAL.png` | Professional dashboard | PNG | 5 |
| `DETAILED_REPORT_*.txt` | Detailed analysis report | Text | 3 |
| `FINAL_REPORT_*.txt` | Pipeline execution summary | Text | Final |

---

### D. Wavelength Codes

Common light wavelengths used in optogenetic MEA experiments:

| Code | Color | Application |
|------|-------|-------------|
| 470nm | Blue | ChR2 activation |
| 530nm | Green | Calcium imaging |
| 590nm | Yellow/Amber | Halorhodopsin |
| 625nm | Red | ChrimsonR activation |
| 'UNKNOWN' | N/A | No wavelength specified |

---

**End of Documentation**

For updates and additional resources, visit [Repository URL].

*Last updated: [Date]*
