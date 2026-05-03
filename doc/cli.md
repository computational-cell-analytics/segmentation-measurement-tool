# Command Line Interface

The `segmentation-measurement` CLI provides utilities for post-processing segmentations and
measuring intensities directly from the terminal without writing any Python code.

## Installation

```bash
pip install segmentation-measurement
```

After installation the `segmentation-measurement` command is available in your shell.

## Overview

The CLI exposes two top-level commands:

| Command | Description |
|---------|-------------|
| `postprocess` | Apply post-processing operations to segmentation TIFF files |
| `measure` | Compute per-segment measurements from segmentation and intensity TIFF files |

Run any command with `--help` to see its full usage:

```bash
segmentation-measurement --help
segmentation-measurement postprocess --help
segmentation-measurement postprocess filter-small-segments --help
```

---

## Post-processing (`postprocess`)

The `postprocess` command provides three sub-commands that each read a segmentation TIFF,
apply a transformation, and write the result to a new TIFF.

### `filter-small-segments`

Remove segments whose size (in pixels for 2-D data, or voxels for 3-D data) is below a
minimum threshold.  Removed segments are replaced by the background label `0`.

```bash
segmentation-measurement postprocess filter-small-segments \
    --input  segmentation.tif \
    --output filtered.tif \
    --min-size 200
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--input` | path | yes | Input segmentation TIFF file |
| `--output` | path | yes | Output segmentation TIFF file |
| `--min-size` | int | yes | Minimum segment size in pixels/voxels; segments strictly smaller than this value are removed |

**Example** – keep only segments with at least 500 pixels:

```bash
segmentation-measurement postprocess filter-small-segments \
    --input nuclei.tif --output nuclei_filtered.tif --min-size 500
```

---

### `remove-small-holes`

Fill enclosed background holes inside segments when the hole is smaller than or equal to
the specified maximum size.  Pixels belonging to *other* segments are never overwritten.

```bash
segmentation-measurement postprocess remove-small-holes \
    --input  segmentation.tif \
    --output filled.tif \
    --max-hole-size 50
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--input` | path | yes | Input segmentation TIFF file |
| `--output` | path | yes | Output segmentation TIFF file |
| `--max-hole-size` | int | yes | Maximum hole size in pixels/voxels to fill |

**Example** – fill holes up to 100 pixels:

```bash
segmentation-measurement postprocess remove-small-holes \
    --input cells.tif --output cells_filled.tif --max-hole-size 100
```

---

### `ring-mask`

Compute a ring (annular hull) of a specified width around each segment.  The output
contains *only* the ring pixels; the original segment interiors are set to `0`.  This is
useful for creating pseudo-cytoplasm masks from segmented nuclei.

Rings are placed only on background pixels; if rings from different segments overlap,
the segment with the smaller label ID takes precedence.

```bash
segmentation-measurement postprocess ring-mask \
    --input  segmentation.tif \
    --output rings.tif \
    --ring-width 5
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--input` | path | yes | Input segmentation TIFF file |
| `--output` | path | yes | Output TIFF file for the ring mask |
| `--ring-width` | int | yes | Width of the ring in pixels/voxels |

**Example** – create 8-pixel-wide rings around nuclei:

```bash
segmentation-measurement postprocess ring-mask \
    --input nuclei.tif --output cytoplasm_rings.tif --ring-width 8
```

---

## Intensity Measurement (`measure`)

### `intensities`

Compute per-segment intensity statistics from a segmentation label image and a
co-registered intensity image.  Both files must be TIFF and must have identical shapes.

```bash
segmentation-measurement measure intensities \
    --segmentation segmentation.tif \
    --intensity    fluorescence.tif \
    --output       measurements.csv
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--segmentation` | path | yes | Segmentation TIFF file (integer labels) |
| `--intensity` | path | yes | Intensity image TIFF file |
| `--output` | path | yes | Output table file; format inferred from extension |

**Supported output formats**

| Extension | Format |
|-----------|--------|
| `.csv` (default) | Comma-separated values |
| `.tsv` | Tab-separated values |
| `.xlsx` | Excel workbook |

**Output columns**

| Column | Description |
|--------|-------------|
| `label` | Integer segment label |
| `mean_intensity` | Mean pixel intensity within the segment |
| `median_intensity` | Median pixel intensity |
| `max_intensity` | Maximum pixel intensity |
| `min_intensity` | Minimum pixel intensity |
| `std_intensity` | Standard deviation of pixel intensities |
| `percentile_10` | 10th percentile of pixel intensities |
| `percentile_25` | 25th percentile (first quartile) |
| `percentile_75` | 75th percentile (third quartile) |
| `percentile_90` | 90th percentile of pixel intensities |

**Example** – save results as an Excel file:

```bash
segmentation-measurement measure intensities \
    --segmentation cells.tif \
    --intensity    gfp_channel.tif \
    --output       intensity_stats.xlsx
```
