# CLAUDE.md - MEA Analysis Pipeline

## Project Overview

This is an automated Multi-Electrode Array (MEA) data analysis pipeline designed to process neuronal recording data and generate publication-ready visualizations. The pipeline is optimized for **Nature, Cell, and Science** journal standards, providing comprehensive analysis from raw data to final figures in ~15 minutes.

**Project Type:** Scientific Data Analysis Pipeline
**Primary Language:** Python
**Domain:** Neuroscience / Electrophysiology
**Current Version:** v3.5 (Enhanced Burst Metrics Edition)

### Key Features
- Automated MEA recording analysis with multiple modes (basic, advanced, professional, full)
- Publication-quality visualizations with colorblind-safe palettes
- Advanced analytics: connectivity analysis, spatial pattern detection, hierarchical clustering
- Enhanced burst metrics (number, duration, frequency)
- Smart data detection and adaptive analysis
- Vector graphics output (PDF) for journals

---

## Codebase Structure

```
mea-analysis/
├── README.md                            # User-facing documentation
├── requirements.txt                      # Python dependencies
├── LICENSE                               # MIT License
├── .gitignore                           # Excludes data/output files
│
├── quick_visual.py                      # Fast 3-plot visualization (~30s)
├── diagnose_data.py                     # Data validation and troubleshooting
│
├── mea_complete_analyzer_v35.py         # Main orchestrator (v3.5)
├── mea_auto_analyzer_v32.py             # Core analysis engine (v3.2)
├── mea_advanced_analytics_v33.py        # Advanced analytics (v3.3)
└── mea_professional_visualizer_v34.py   # Publication-style visualizations (v3.4)
```

### Version Progression
- **v3.2**: Standard analyses foundation
- **v3.3**: Advanced analytics (connectivity, clustering)
- **v3.4**: Professional publication styling
- **v3.5**: Enhanced burst metrics (current)

---

## Architecture & Design Patterns

### 1. Modular Pipeline Architecture
The codebase follows a **progressive enhancement pattern** where each version builds upon previous versions:

```
v3.2 (Core) → v3.3 (Advanced) → v3.4 (Professional) → v3.5 (Enhanced)
     ↓              ↓                  ↓                      ↓
Base Analysis  Connectivity    Publication Style    Burst Metrics
```

### 2. Class-Based Components
Each major functionality is encapsulated in specialized classes:

**Data Loading:**
- `OptimizedFormatLoader`: Handles Excel file parsing and long-format conversion

**Analysis Modules (v3.2):**
- `SpontaneousAnalyzer`: Baseline activity analysis
- `LightResponseAnalyzer`: Photo-stimulation response
- `DrugEffectAnalyzer`: Pharmacological effects
- `PerWellAnalyzerEnhanced`: Individual well analysis

**Advanced Analytics (v3.3):**
- `ConnectivityAnalyzer`: Functional connectivity analysis
- `SpatialHeatmapAnalyzer`: Spatial activity distribution
- `AdvancedVisualizer`: Network graph analysis, clustering

**Professional Visualization (v3.4):**
- `ProfessionalPerWellAnalyzer`: Journal-quality per-well figures
- `ProfessionalSpatialHeatmap`: Publication-ready spatial plots
- `ProfessionalDashboard`: Master overview dashboard
- `ScientificPalette`: Colorblind-friendly color schemes

**Utilities:**
- `CombinedExcelCreator`: Excel report generation
- `DetailedReportGenerator`: Statistical text reports

### 3. Data Flow Pattern
```
Excel Files (Multi-sheet)
    ↓
OptimizedFormatLoader (Long-format conversion)
    ↓
DataFrame (Well × Metric × Value × Metadata)
    ↓
Analysis Modules (Parallel processing)
    ↓
Output Files (Figures, Excel, Reports)
```

### 4. Design Principles
- **Separation of Concerns**: Each version/module has distinct responsibilities
- **Error Resilience**: Extensive error handling with informative messages
- **Flexibility**: Optional columns (e.g., DIFF_DAY) handled gracefully
- **Progressive Disclosure**: Users can choose analysis depth via `mode` parameter

---

## Key Components Deep Dive

### mea_complete_analyzer_v35.py
**Purpose:** Main orchestrator that coordinates all analysis stages
**Entry Point:** `CompleteAnalyzerV35` class

**Key Method:**
```python
analyzer.run(mode='full')  # Options: 'basic', 'advanced', 'professional', 'full'
```

**Execution Flow:**
1. Load data via `OptimizedFormatLoader`
2. Create combined Excel report
3. **Stage 1:** Basic analyses (spontaneous, light, drug)
4. **Stage 2:** Advanced analytics (if mode includes 'advanced' or 'full')
5. **Stage 3:** Professional visualizations (if mode includes 'professional' or 'full')

**Important Location:** Lines 226-239 contain hardcoded paths for Windows (`D:\MyProjects\`)

---

### mea_auto_analyzer_v32.py
**Purpose:** Core analysis engine with data loading and basic analytics
**Size:** ~2000+ lines (largest file)

**Critical Classes:**

1. **OptimizedFormatLoader** (lines 38-134)
   - Loads Excel files with 3 required sheets: `Metadata`, `Template`, `Well_Info`
   - Converts wide format to long format
   - Handles optional `DIFF_DAY` column gracefully (lines 100-104)
   - Returns DataFrame with standardized columns

2. **PerWellAnalyzerEnhanced** (lines 140+)
   - Enhanced color palette (lines 148-151)
   - Creates individual well figures

**Expected Data Format:**
```
Excel File Structure:
├── Metadata sheet (1 row)
│   ├── PLATE_ID
│   ├── BASE_STIM
│   ├── TIME_START, TIME_DURATION_SEC
│   ├── PLATING_DAY
│   ├── LIGHT_CODE, INTENSITY_PCT
│   ├── EXP_TYPE (CONTROL/DRUG)
│   └── DRUG, CONCENTRATION_MM
│
├── Template sheet (Metric × Wells matrix)
│   └── Columns: Metric, A1, A2, B1, B2, ...
│
└── Well_Info sheet (Optional metadata per well)
    └── Columns: Well, DIFF_DAY, ...
```

**Output Locations:**
- `00_per_well/`: Individual well analysis
- `01_spontaneous/`: Baseline activity
- `02_light_response/`: Light stimulation responses
- `03_drug_effects/`: Drug effect analysis

---

### mea_advanced_analytics_v33.py
**Purpose:** Cutting-edge visualizations based on 2022-2024 research
**Key Features:** Connectivity, spatial patterns, clustering

**Main Classes:**

1. **ConnectivityAnalyzer** (lines 35-108)
   - Functional connectivity via correlation analysis
   - Handles insufficient data gracefully (lines 80-83)
   - Creates connectivity heatmaps

2. **SpatialHeatmapAnalyzer** (lines 113+)
   - Well layout mapping (e.g., A1→(0,0), A2→(0,1))
   - Creates 3 types of spatial heatmaps

3. **AdvancedVisualizer**
   - Orchestrates all advanced analyses
   - Circular connectivity plots (chord diagrams)
   - Time-evolution heatmaps
   - Hierarchical clustering

**Research References:**
- MEA-ToolBox (2022)
- Graph Neural Networks in Brain Connectivity (2024)
- Brain Modulyzer

---

### mea_professional_visualizer_v34.py
**Purpose:** Publication-ready visualizations following journal guidelines
**Standards:** Nature, Cell, Science, PLOS guidelines

**Key Components:**

1. **ScientificPalette** (lines 39-77)
   - Colorblind-safe palettes (Wong 2011, ColorBrewer)
   - 8 categorical colors for conditions
   - Sequential and diverging schemes

2. **Professional Styling Functions:**
   - `set_professional_style()`: Typography, spacing
   - `remove_chartjunk()`: Removes unnecessary visual elements (Tufte's principle)

3. **Professional Analyzers:**
   - Vector graphics (PDF) with TrueType fonts
   - Statistical annotations
   - Error bars and significance markers
   - High DPI (300+) outputs

**Design Principles:**
- Minimal & clean design
- Professional typography (Arial/DejaVu Sans)
- Statistical rigor
- Accessibility (colorblind-friendly)

---

### quick_visual.py
**Purpose:** Rapid visualization for quick data assessment (~30 seconds)
**Use Case:** Initial data exploration before full analysis

**Generates 3 Core Plots:**
1. **DIV Timeline**: Neuronal maturation over differentiation days
2. **Drug Comparison**: Direct control vs. drug comparison with % change
3. **Integrated Heatmap**: DIV × Drug condition matrix

**Key Function:**
```python
quick_visual(project_path, output_name='quick_visual')
```

**Data Discovery:** Auto-searches in priority order:
1. `output/processed/*.parquet`
2. `output/analysis/*_data.csv`
3. `DATASET/**/*.csv`
4. `**/*_data.csv`

**Features:**
- Auto-loads data from project folder
- Handles missing DIV or DRUG columns
- Color-coded by condition (control=blue, drug=red)
- Professional styling even for quick plots

---

### diagnose_data.py
**Purpose:** Troubleshooting tool for data loading issues
**Usage:** `diagnose_data(r"D:\MyProjects\#4-1")`

**Diagnostic Checks:**
1. Directory existence
2. Excel file discovery
3. Sheet structure validation (Metadata, Template, Well_Info)
4. Column presence verification
5. Data conversion test
6. Full load test with detailed output

**Helpful for:**
- Missing files or directories
- Incorrect data format
- Missing required columns
- Debugging data loading failures

---

## Development Workflows

### 1. Adding New Analysis Features

**Where to add:**
- **Basic metrics**: Extend `mea_auto_analyzer_v32.py` analyzers
- **Advanced analytics**: Add to `mea_advanced_analytics_v33.py`
- **Visualization style**: Modify `mea_professional_visualizer_v34.py`
- **New orchestration**: Update `mea_complete_analyzer_v35.py`

**Pattern to follow:**
```python
class NewAnalyzer:
    def __init__(self, df, output_dir):
        self.df = df
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def analyze(self):
        print('\n[NEW_ANALYSIS] Starting...')
        # Analysis logic
        return self

    def visualize(self):
        # Visualization logic
        return self
```

### 2. Handling New Data Columns

**Optional Column Pattern** (see mea_auto_analyzer_v32.py:100-104):
```python
if 'NEW_COLUMN' in df.columns:
    new_data = dict(zip(df['Well'], df['NEW_COLUMN']))
else:
    new_data = {}
```

### 3. Testing Workflow

**Recommended steps:**
1. Use `diagnose_data.py` to validate data format
2. Run `quick_visual.py` for rapid sanity check (~30s)
3. Run basic mode: `analyzer.run(mode='basic')` (~5 min)
4. Run full mode after validation: `analyzer.run(mode='full')` (~15 min)

### 4. Adding New Visualizations

**Professional Style Checklist:**
- Use `ScientificPalette` colors
- Call `set_professional_style()` before plotting
- Use `remove_chartjunk(ax)` on axes
- Save as both PNG (300 DPI) and PDF (vector)
- Include error bars for statistical data
- Add significance annotations where applicable

---

## Key Conventions

### 1. File Naming
- Analysis scripts: `mea_<component>_v<version>.py`
- Output files: `<descriptor>_<condition>.png/pdf`
- Professional outputs: `*_professional.pdf`

### 2. Well Naming
- Format: `A1`, `A2`, `B1`, `C3`, etc.
- Pattern: Row (letter) + Column (number)
- Sorted alphabetically in outputs

### 3. Metrics
Core metrics processed (case-sensitive):
- `mean_firing_rate_hz`: Primary metric
- `burst_frequency_hz`: Burst rate
- `number_of_bursts`: Total burst count (v3.5)
- `burst_duration_ms`: Burst duration (v3.5)
- `synchrony_index`: Network synchronization
- `network_burst_frequency`: Population bursts

### 4. Experimental Conditions
- `EXP_TYPE`: `'CONTROL'` or `'DRUG'`
- `BASE_STIM`: `'BASE'` or `'STIM'`
- `DRUG`: Specific drug name or `'NONE'`
- `LIGHT_CODE`: Stimulation protocol identifier

### 5. Output Organization
```
analysis_v35/
├── 00_per_well/              # Individual well figures
├── 00_per_well_professional/ # Publication-ready per-well
├── 01_spontaneous/           # Baseline analysis
├── 02_light_response/        # Photo-stimulation
├── 03_drug_effects/          # Pharmacology
├── advanced_analytics/       # Connectivity, clustering
├── spatial_heatmaps_professional/
├── COMBINED_DATA.xlsx        # All data in one file
├── DETAILED_REPORT_*.txt     # Statistical summary
└── MASTER_DASHBOARD_PROFESSIONAL.png/pdf
```

### 6. Color Palette Standards
Always use colorblind-safe palettes from `ScientificPalette`:
- **Categorical**: 8-color palette for conditions
- **Sequential**: Blue or Red for intensity
- **Diverging**: Blue-Red for bidirectional effects
- **Never use**: Rainbow, Jet, or non-accessible palettes

### 7. Error Handling Philosophy
- **Graceful degradation**: Skip unavailable analyses rather than crash
- **Informative messages**: Clear ⚠ warnings with actionable advice
- **Data validation**: Check for required columns before processing
- **Partial success**: Generate what's possible, report what's missing

---

## Dependencies

### Core Scientific Stack
```
pandas >= 1.5.0      # Data manipulation
numpy >= 1.23.0      # Numerical computing
scipy >= 1.9.0       # Scientific algorithms (stats, clustering)
```

### Visualization
```
matplotlib >= 3.6.0  # Plotting engine
seaborn >= 0.12.0    # Statistical visualizations
```

### Data I/O
```
openpyxl >= 3.0.0    # Excel file handling
pyarrow >= 10.0.0    # Parquet format support
```

### Important Notes
- **Font rendering**: Uses Arial/DejaVu Sans (ensure installed)
- **PDF fonts**: TrueType embedding enabled (`pdf.fonttype = 42`)
- **Platform**: Primarily Windows-oriented (see path conventions)
- **Python version**: Developed on Python 3.8+

---

## Common Tasks for AI Assistants

### Task 1: Analyze New Dataset
```python
from mea_complete_analyzer_v35 import CompleteAnalyzerV35

analyzer = CompleteAnalyzerV35(
    input_dir="/path/to/data/processed",
    output_dir="/path/to/output/analysis_v35"
)
analyzer.run(mode='full')
```

### Task 2: Quick Data Check
```python
from quick_visual import quick_visual
quick_visual("/path/to/project")
```

### Task 3: Troubleshoot Data Loading
```python
from diagnose_data import diagnose_data
diagnose_data("/path/to/data")
```

### Task 4: Batch Process Multiple Projects
```python
from quick_visual import quick_visual_batch
quick_visual_batch([
    "/path/to/project1",
    "/path/to/project2",
    "/path/to/project3"
])
```

### Task 5: Custom Analysis
When adding custom analysis:
1. Determine appropriate module (v3.2, v3.3, or v3.4)
2. Create analyzer class following existing patterns
3. Register in `CompleteAnalyzerV35.run()` method
4. Update README.md with new features

---

## Important Implementation Details

### 1. Data Loading Quirks
- **Excel sheets must exist**: `Metadata`, `Template`, `Well_Info`
- **Optional columns handled**: `DIFF_DAY` can be missing (v3.2+)
- **File filtering**: Temporary Excel files (`~$*.xlsx`) automatically skipped
- **Empty data handling**: Returns empty DataFrame, doesn't crash

### 2. Well Layout Assumptions
- Default layout in `SpatialHeatmapAnalyzer`: 4×3 grid (A1-D3)
- Modify `well_positions` dict for different plate formats
- Spatial plots adapt to available wells

### 3. Hardcoded Paths (Windows-specific)
**Lines to modify for different environments:**
- `mea_complete_analyzer_v35.py:230`: Default project path
- `quick_visual.py:403`: Example project path
- `diagnose_data.py:161`: Example diagnostic path

**Pattern:** `r"D:\MyProjects\#<number>"`

### 4. Analysis Modes
| Mode | Time | Stages | Use Case |
|------|------|--------|----------|
| `basic` | 5 min | v3.2 only | Quick metrics |
| `advanced` | 10 min | v3.2 + v3.3 | + Connectivity |
| `professional` | 7 min | v3.2 + v3.4 | + Publication figs |
| `full` | 15 min | v3.2 + v3.3 + v3.4 | Complete analysis |

### 5. Memory Considerations
- Large datasets: Use parquet format over CSV
- Matplotlib figures closed after saving to prevent memory leaks
- Per-well analysis processes sequentially (not parallel)

### 6. Statistical Methods
- **Correlation**: Pearson correlation for connectivity
- **Clustering**: Hierarchical clustering via scipy
- **Comparisons**: Percentage change calculations for drug effects
- **Error bars**: Standard error of mean (SEM)

### 7. Figure Output Formats
- **PNG**: 300 DPI for presentations
- **PDF**: Vector graphics for publications
- **Both saved** when using professional visualizer

---

## Troubleshooting Guide

### Issue: "No data loaded!"
**Causes:**
1. Excel files not in correct directory
2. Missing required sheets
3. Empty data files

**Solution:**
```python
from diagnose_data import diagnose_data
diagnose_data("/path/to/data")
```

### Issue: "KeyError: 'DIFF_DAY'"
**Cause:** Using older version (< v3.2)
**Solution:** Use v3.2+ which handles optional columns

### Issue: "Connectivity plot error"
**Cause:** Insufficient data points (< 2)
**Solution:** v3.3+ includes validation; error is now gracefully handled

### Issue: "Skipping connectivity plot for {well} (insufficient data)"
**Cause:** Normal behavior for wells with limited measurements
**Action:** No action needed; other wells will process normally

### Issue: Figures look different than expected
**Check:**
1. Using professional visualizer? (`mode='professional'` or `mode='full'`)
2. Fonts installed? (Arial or DejaVu Sans)
3. Correct color palette? (Use `ScientificPalette`)

### Issue: Path errors on non-Windows systems
**Solution:** Modify hardcoded paths in:
- `mea_complete_analyzer_v35.py:230`
- `quick_visual.py:403`
- Change `r"D:\..."` to appropriate Unix paths

---

## Git Workflow

### Current Branch
Working on: `claude/claude-md-mi3wqlhevctg0zu8-012YLdV8bWQz8hqSp4oLWwPK`

### Recent Commits
```
0915e70 - Update README.md
0a9ac92 - Initial commit: MEA analysis pipeline
7ddd511 - Initial commit
```

### Ignored Files (.gitignore)
- Data files: `*.csv`, `*.xlsx`, `*.parquet`, `*.h5`
- Output directories: `output/`, `analysis*/`, `quick_visual/`
- Python artifacts: `__pycache__/`, `*.pyc`
- IDE files: `.vscode/`, `.idea/`

### Important Notes
- **Never commit data files** - they're large and user-specific
- **Never commit output files** - they're generated, not source
- **Do commit**: Python scripts, README, requirements, documentation

---

## Quick Reference Card

### One-Liner for Most Common Use
```python
from mea_complete_analyzer_v35 import CompleteAnalyzerV35
CompleteAnalyzerV35("input/path", "output/path").run(mode='full')
```

### File Roles at a Glance
| File | Role | When to Use |
|------|------|-------------|
| `quick_visual.py` | Fast 3-plot check | First look at data |
| `diagnose_data.py` | Debug data issues | Data won't load |
| `mea_complete_analyzer_v35.py` | Main orchestrator | Full analysis |
| `mea_auto_analyzer_v32.py` | Core engine | Understanding basics |
| `mea_advanced_analytics_v33.py` | Advanced viz | Connectivity needs |
| `mea_professional_visualizer_v34.py` | Publication style | Paper figures |

### Key Class Hierarchy
```
CompleteAnalyzerV35 (orchestrator)
    ├─→ OptimizedFormatLoader
    ├─→ SpontaneousAnalyzer
    ├─→ LightResponseAnalyzer
    ├─→ DrugEffectAnalyzer
    ├─→ AdvancedVisualizer
    │    ├─→ ConnectivityAnalyzer
    │    └─→ SpatialHeatmapAnalyzer
    └─→ Professional Analyzers
         ├─→ ProfessionalPerWellAnalyzer
         ├─→ ProfessionalSpatialHeatmap
         └─→ ProfessionalDashboard
```

---

## Version Evolution Summary

| Version | Date | Key Feature | Impact |
|---------|------|-------------|--------|
| v3.2 | Nov 2024 | Core pipeline | Foundation |
| v3.3 | Nov 2024 | Advanced analytics | Connectivity |
| v3.4 | Nov 2024 | Professional styling | Publications |
| v3.5 | Nov 2024 | Enhanced burst metrics | Current |

### v3.5 Enhancements
- Number of bursts analysis
- Burst duration analysis
- 9-panel per-well figures (was 6-panel)
- Enhanced burst statistics in all reports

---

## Best Practices for AI Assistants

1. **Always validate data first**: Use `diagnose_data.py` before analysis
2. **Start with quick_visual**: 30-second sanity check saves time
3. **Choose appropriate mode**: Don't run 'full' for quick tests
4. **Check for optional columns**: DIFF_DAY, custom metadata may be missing
5. **Use proper color palettes**: Only ScientificPalette for publications
6. **Handle errors gracefully**: Print warnings, continue processing
7. **Document new features**: Update README.md and this file
8. **Test incrementally**: basic → advanced → professional → full
9. **Respect .gitignore**: Never commit data or output files
10. **Platform awareness**: Adjust Windows paths for Unix systems

---

## Contact & Support

**Repository**: https://github.com/skim75kr-commits/mea-analysis
**Issues**: https://github.com/skim75kr-commits/mea-analysis/issues
**License**: MIT

---

*Last Updated: 2024-11-18*
*For: MEA Analysis Pipeline v3.5*
*Document Version: 1.0*
