# Command Line Interface

The `segmentation-measurement` CLI provides utilities for post-processing segmentations,
computing measurements, and analyzing results directly from the terminal without writing
any Python code.

## Installation

```bash
pip install segmentation-measurement
```

After installation the `segmentation-measurement` command is available in your shell.

## Overview

The CLI exposes three top-level commands:

| Command | Description |
|---------|-------------|
| `postprocess` | Apply post-processing operations to segmentation TIFF files |
| `measure` | Compute per-segment measurements from segmentation TIFF files |
| `analyze` | Analyze measurement tables (threshold-based categorization) |

Run any command with `--help` to see its full usage:

```bash
segmentation-measurement --help
segmentation-measurement postprocess --help
segmentation-measurement measure morphology --help
segmentation-measurement analyze threshold --help
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

## Measurements (`measure`)

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

---

### `morphology`

Compute per-segment shape descriptors from a segmentation label image.  Supports
isotropic and anisotropic pixel/voxel sizes so that results are returned in physical
units.

```bash
segmentation-measurement measure morphology \
    --segmentation segmentation.tif \
    --output       morphology.csv
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--segmentation` | path | yes | Segmentation TIFF file (integer labels) |
| `--output` | path | yes | Output table file; format inferred from extension |
| `--scale` | float(s) | no | Physical pixel/voxel size (default: `1.0`) |

**Scale argument**

Pass a single value for isotropic spacing, or one value per spatial dimension for
anisotropic spacing.  Dimension order is `(Y, X)` for 2-D and `(Z, Y, X)` for 3-D.

```bash
# isotropic: 0.5 µm per pixel
--scale 0.5

# anisotropic 2-D: 0.5 µm in Y, 0.25 µm in X
--scale 0.5 0.25

# anisotropic 3-D: 2.0 µm in Z, 0.5 µm in Y and X
--scale 2.0 0.5 0.5
```

**Output columns – 2-D**

| Column | Description |
|--------|-------------|
| `label` | Integer segment label |
| `area` | Area in physical units |
| `perimeter` | Perimeter length in physical units |
| `sphericity` | Circularity (1.0 = perfect circle) |
| `solidity` | Area / convex hull area |
| `axis_major_length` | Major axis of the fitted ellipse |
| `axis_minor_length` | Minor axis of the fitted ellipse |
| `equivalent_diameter` | Diameter of a circle with the same area |

**Output columns – 3-D**

| Column | Description |
|--------|-------------|
| `label` | Integer segment label |
| `volume` | Volume in physical units |
| `surface_area` | Surface area via marching cubes |
| `sphericity` | Sphericity (1.0 = perfect sphere) |
| `solidity` | Volume / convex hull volume |
| `axis_major_length` | Major axis of the fitted ellipsoid |
| `axis_minor_length` | Minor axis of the fitted ellipsoid |
| `equivalent_diameter` | Diameter of a sphere with the same volume |

**Examples**

```bash
# 2-D, pixel units
segmentation-measurement measure morphology \
    --segmentation cells.tif --output morphology.csv

# 2-D, anisotropic scale
segmentation-measurement measure morphology \
    --segmentation cells.tif --output morphology.csv --scale 0.5 0.25

# 3-D, anisotropic scale (Z=2 µm, Y=X=0.5 µm)
segmentation-measurement measure morphology \
    --segmentation nuclei_3d.tif --output morphology_3d.csv --scale 2.0 0.5 0.5
```

---

### `cell-nucleus`

Compute per-cell measurements that combine a cell segmentation with a nucleus
segmentation.  For each cell, the command reports how many nuclei it contains,
the cell and nucleus area/volume in physical units, and their ratio.  When an
optional intensity image is supplied, it also reports intensity statistics for
the cytoplasmic region (cell minus nucleus) and the nuclear region, together
with their ratios.

```bash
segmentation-measurement measure cell-nucleus \
    --cell-segmentation   cells.tif \
    --nucleus-segmentation nuclei.tif \
    --output              cell_nucleus.csv
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--cell-segmentation` | path | yes | Cell segmentation TIFF file (integer labels) |
| `--nucleus-segmentation` | path | yes | Nucleus segmentation TIFF file (integer labels); must have the same shape as the cell segmentation |
| `--output` | path | yes | Output table file; format inferred from extension |
| `--scale` | float(s) | no | Physical pixel/voxel size (default: `1.0`); same syntax as `morphology` |
| `--intensity` | path | no | Intensity image TIFF file; when provided, per-region intensity statistics and their ratios are included |

**Scale argument**

Identical to the `morphology` sub-command: pass a single value for isotropic
spacing, or one value per spatial dimension for anisotropic spacing in
`(Y, X)` / `(Z, Y, X)` order.

**Output columns – without intensity image (2-D)**

| Column | Description |
|--------|-------------|
| `label` | Integer cell label |
| `n_nuclei` | Number of nucleus labels overlapping with this cell |
| `cell_area` | Area of the cell in physical units (nucleus included) |
| `nucleus_area` | Total area of nuclei within this cell in physical units |
| `area_ratio` | `cell_area / nucleus_area`; `NaN` if the cell contains no nucleus |

For 3-D data the columns are `cell_volume`, `nucleus_volume`, and `volume_ratio`
instead.

**Additional columns – with intensity image**

When `--intensity` is given, the following columns are added for each statistic
`{stat}` in `mean`, `median`, `max`, `min`, `percentile_10`, `percentile_25`,
`percentile_75`, `percentile_90`:

| Column | Description |
|--------|-------------|
| `cell_{stat}_intensity` | Statistic over the cytoplasmic region (cell pixels where no nucleus is present) |
| `nucleus_{stat}_intensity` | Statistic over all nuclear pixels within this cell |
| `{stat}_intensity_ratio` | `cell_{stat}_intensity / nucleus_{stat}_intensity`; `NaN` when either region is empty or the nucleus value is zero |

**Supported output formats** – same as `intensities` (`.csv`, `.tsv`, `.xlsx`).

**Examples**

```bash
# Basic measurements, pixel units
segmentation-measurement measure cell-nucleus \
    --cell-segmentation cells.tif \
    --nucleus-segmentation nuclei.tif \
    --output cell_nucleus.csv

# With physical scale (0.5 µm/px, isotropic)
segmentation-measurement measure cell-nucleus \
    --cell-segmentation cells.tif \
    --nucleus-segmentation nuclei.tif \
    --output cell_nucleus.csv \
    --scale 0.5

# With intensity ratios
segmentation-measurement measure cell-nucleus \
    --cell-segmentation cells.tif \
    --nucleus-segmentation nuclei.tif \
    --intensity gfp_channel.tif \
    --output cell_nucleus_intensity.csv

# Anisotropic 3-D (Z=2 µm, Y=X=0.5 µm) with intensity
segmentation-measurement measure cell-nucleus \
    --cell-segmentation cells_3d.tif \
    --nucleus-segmentation nuclei_3d.tif \
    --intensity gfp_3d.tif \
    --output cell_nucleus_3d.csv \
    --scale 2.0 0.5 0.5
```

---

## Analysis (`analyze`)

### `threshold`

Categorize segments into N named groups based on N-1 thresholds applied to one column of
a measurement table.  Thresholds can be provided explicitly or suggested automatically
from the data distribution.

```bash
segmentation-measurement analyze threshold \
    --table      measurements.csv \
    --column     mean_intensity \
    --n-categories 3 \
    --output     categorized.csv
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--table` | path | yes | Input measurement table (CSV, TSV, or XLSX) |
| `--column` | str | yes | Column name to threshold |
| `--n-categories` | int | yes | Number of output categories |
| `--thresholds` | float(s) | no | Explicit threshold values (`n_categories - 1` values); auto-suggested if omitted |
| `--category-names` | str(s) | no | Names for each category (`n_categories` values); defaults to `category_1`, `category_2`, … |
| `--output` | path | yes | Output table file (CSV, TSV, or XLSX) |
| `--segmentation` | path | no | Segmentation TIFF; required when `--output-segmentation` is used |
| `--output-segmentation` | path | no | Output TIFF where each segment is assigned its category ID |

**Output**

The output table is the input table with two additional columns:

| Column | Description |
|--------|-------------|
| `category_id` | Integer category (1-based) |
| `category_name` | Human-readable category name |

Segments with a value below the first threshold are category 1; segments between the
first and second threshold are category 2; and so on.

**Examples**

```bash
# Auto-suggest thresholds for 3 categories
segmentation-measurement analyze threshold \
    --table intensity.csv \
    --column mean_intensity \
    --n-categories 3 \
    --output categorized.csv

# Explicit thresholds with custom names
segmentation-measurement analyze threshold \
    --table morphology.csv \
    --column area \
    --n-categories 3 \
    --thresholds 500 1500 \
    --category-names small medium large \
    --output categorized.csv

# Also write a category segmentation TIFF
segmentation-measurement analyze threshold \
    --table intensity.csv \
    --column mean_intensity \
    --n-categories 2 \
    --thresholds 100 \
    --output categorized.csv \
    --segmentation cells.tif \
    --output-segmentation categories.tif
```
