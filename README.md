# MEA Analysis Pipeline

Automated pipeline for Multi-Electrode Array (MEA) data analysis with publication-ready outputs.

## Overview

This pipeline processes MEA recordings and generates publication-quality figures suitable for Nature, Cell, and Science journals. The entire workflow—from raw data to final figures—is automated.

## Quick Start

### Installation
```bash
pip install -r requirements.txt
```

### Basic Usage
```python
from quick_visual import quick_visual

# Generate core visualizations (30 seconds)
quick_visual(r"D:\MyProjects\#7-1")
```

This produces three essential plots:
1. DIV timeline showing neuronal maturation
2. Drug response comparison
3. Integrated heatmap across all conditions

### Complete Analysis
```python
from mea_complete_analyzer_v35 import CompleteAnalyzerV35

analyzer = CompleteAnalyzerV35(
    input_dir=r"D:\MyProjects\#7-1\output\processed",
    output_dir=r"D:\MyProjects\#7-1\analysis_v35"
)

analyzer.run(mode='full')  # ~15 min
```

## Analysis Modes

| Mode | Time | Output |
|------|------|--------|
| `basic` | 5 min | Core metrics and statistics |
| `advanced` | 10 min | + Connectivity and clustering |
| `professional` | 7 min | + Publication-ready figures |
| `full` | 15 min | All analyses (recommended) |

## Output Files

### Publication-Ready Figures
- `*_professional.pdf` - Vector graphics for journals
- `MASTER_DASHBOARD_PROFESSIONAL.pdf` - Complete overview
- `spatial_heatmaps_professional/*.pdf` - Well plate distributions

All figures use:
- Colorblind-safe palettes
- Vector format (infinite resolution)
- Statistical annotations
- Nature/Cell/Science style guidelines

### Data Files
- `COMBINED_DATA.xlsx` - All metrics in one file
- `DETAILED_REPORT.txt` - Statistical summary
- Individual well CSV files with per-condition breakdowns

## Key Features

**Smart Detection**
- Automatically identifies available metrics
- Adapts analysis based on data structure
- Handles missing columns (e.g., DIFF_DAY)

**Robust Processing**
- Parquet and CSV format support
- Automatic file discovery
- Error recovery and diagnostics

**Advanced Analytics**
- Functional connectivity analysis
- Spatial pattern detection
- Hierarchical clustering
- Time-evolution tracking

## Troubleshooting

### Data not loading
```python
from diagnose_data import diagnose_data
diagnose_data(r"D:\MyProjects\#7-1")
```

This diagnostic tool identifies:
- Missing files or directories
- Incorrect data format
- Missing required columns

### Common Issues

**KeyError: 'DIFF_DAY'**
→ Use v3.2+. Optional columns are now handled automatically.

**Connectivity plot error**
→ Use v3.3+. Includes validation for insufficient data.

**No data loaded**
→ Check that processed files are in `output/processed/` or run diagnostics.

## File Organization

```
mea-analysis/
├── quick_visual.py                    # Fast visualization (30s)
├── mea_complete_analyzer_v35.py       # Main pipeline
├── mea_auto_analyzer_v32.py           # Core analysis engine
├── mea_advanced_analytics_v33.py      # Advanced methods
├── mea_professional_visualizer_v34.py # Publication styling
└── diagnose_data.py                   # Diagnostic tool
```

## Requirements

```
pandas >= 1.5.0
numpy >= 1.23.0
matplotlib >= 3.6.0
seaborn >= 0.12.0
scipy >= 1.9.0
openpyxl >= 3.0.0
pyarrow >= 10.0.0
```

## Version History

**v3.5** (Nov 2024)
- Smart burst metric detection
- Adaptive analysis pipeline
- Enhanced error handling

**v3.4** (Nov 2024)
- Professional publication styling
- Vector PDF outputs
- Colorblind-safe palettes

**v3.3** (Nov 2024)
- Advanced connectivity analysis
- Spatial pattern detection
- Hierarchical clustering

**v3.2** (Nov 2024)
- Core pipeline foundation
- Automated data processing

## Citation

```bibtex
@software{mea_analysis_pipeline,
  author = {skim75kr},
  title = {MEA Analysis Pipeline},
  year = {2024},
  url = {https://github.com/skim75kr-commits/mea-analysis}
}
```

## License

MIT License

## Contact

Report issues at: https://github.com/skim75kr-commits/mea-analysis/issues
