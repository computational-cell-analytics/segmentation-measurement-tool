# segmentation-measurement

`segmentation-measurement` is a Python library for post-processing, measuring, and analyzing instance segmentations from microscopy images. It provides:

- **Post-processing**: filter small segments, remove small holes, compute ring-masks around segments.
- **Intensity measurements**: per-object mean, median, max, standard deviation, and percentile statistics; threshold-based categorization of objects by intensity.
- **Napari plugin**: interactive widgets for all of the above, with table visualization and export to CSV, TSV, and Excel.
- **CLI**: command-line interface for all functionality.

All functions support 2D and 3D inputs.

## Installation

Install the core library with pip:

```bash
pip install segmentation-measurement
```

To also install the napari plugin and its dependencies:

```bash
pip install "segmentation-measurement[napari]"
```

To install from source:

```bash
git clone https://github.com/computational-cell-analytics/segmentation-measurement-tool
cd segmentation-measurement-tool
pip install -e .
# or with napari support:
pip install -e ".[napari]"
```

Requires Python 3.9 or later.
