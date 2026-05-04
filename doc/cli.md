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

The CLI exposes four top-level commands:

| Command | Description |
|---------|-------------|
| `postprocess` | Apply post-processing operations to segmentation TIFF files |
| `measure` | Compute per-segment measurements from segmentation TIFF files |
| `table` | Manipulate measurement tables (merge tables, drop columns) |
| `analyze` | Analyze measurement tables (threshold-based categorization, clustering, classification) |

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

Compute a ring (annular hull) of a specified width around each segment.  By default the
original segment pixels are retained in the output alongside the ring pixels.  Pass
`--remove-original` to produce a ring-only mask (original segment interiors set to `0`).
This is useful for creating pseudo-cytoplasm masks from segmented nuclei.

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
| `--remove-original` | flag | no | Remove original segment pixels; output contains only ring pixels |

**Example** – create 8-pixel-wide rings around nuclei (original segments kept):

```bash
segmentation-measurement postprocess ring-mask \
    --input nuclei.tif --output cytoplasm_rings.tif --ring-width 8
```

**Example** – ring-only mask (original segments removed):

```bash
segmentation-measurement postprocess ring-mask \
    --input nuclei.tif --output rings_only.tif --ring-width 8 --remove-original
```

---

### `watershed`

Refine a segmentation using the watershed algorithm.  The input segmentation
is used as seed markers; the heatmap is the topographic landscape that the
algorithm floods.  Because `skimage.segmentation.watershed` floods from low
values upward, the heatmap should have **low values at desired segment
boundaries and high values in the interior**.  If your heatmap has the
opposite convention (e.g. a distance transform or foreground-probability map
where high values indicate cell centres), pass the negated image.

An optional binary mask restricts processing to a subset of pixels; unmasked
pixels are set to 0 in the output.

```bash
segmentation-measurement postprocess watershed \
    --input  seeds.tif \
    --heatmap landscape.tif \
    --output refined.tif
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--input` | path | yes | Input segmentation TIFF file used as seed markers |
| `--heatmap` | path | yes | Heatmap image TIFF (low values flooded first) |
| `--output` | path | yes | Output segmentation TIFF file |
| `--mask` | path | no | Binary mask TIFF; only masked pixels are processed |

**Example** – watershed refinement with a foreground-probability heatmap
(negated so high-probability regions are flooded first):

```bash
# Negate the probability map beforehand, then run watershed
segmentation-measurement postprocess watershed \
    --input seeds.tif --heatmap neg_prob.tif --output refined.tif
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

## Table manipulation (`table`)

The `table` command operates on saved measurement tables (CSV / TSV / XLSX).

### `merge`

Merge one or more saved measurement tables on a shared key column (`label` by
default) and optionally drop columns from the merged result.  The merge is an
outer join: label IDs that appear in only some inputs are kept, with NaNs in
the missing columns.  Non-key columns must be disjoint between input tables —
drop conflicts beforehand or via `--drop-columns`.

When only one input is given the command becomes a column-drop utility,
useful for cleaning up an existing table.  The `label` column is the segment
identifier and is always preserved — passing it to `--drop-columns` raises an
error.

```bash
segmentation-measurement table merge \
    --inputs intensity.csv morphology.csv \
    --output combined.csv
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--inputs` | path… | yes | One or more input table files (CSV, TSV, XLSX) |
| `--output` | path | yes | Output table file (extension picks the format) |
| `--on` | str | no | Key column shared between input tables (default: `label`) |
| `--drop-columns` | str… | no | Columns to drop from the merged table |

**Example** — merge intensity and morphology tables and drop a column:

```bash
segmentation-measurement table merge \
    --inputs intensity.csv morphology.csv \
    --output combined.csv \
    --drop-columns std_intensity
```

**Example** — drop a column from a single existing table:

```bash
segmentation-measurement table merge \
    --inputs combined.csv \
    --output trimmed.csv \
    --drop-columns std_intensity max_intensity
```

---

## Analysis (`analyze`)

### `cluster`

Cluster segments using their measurement features.  All numeric columns are used as
features (excluding `label`, `cluster_id`, `category_id`, and `category_name`).
Features are z-score standardised before clustering.

The output table is the input table with an added `cluster_id` column.  Cluster IDs are
**1-based** (1, 2, 3, …).  Noise points — segments that no cluster claims, as produced by
DBSCAN and HDBSCAN — are assigned `cluster_id = -1`.

```bash
segmentation-measurement analyze cluster \
    --table      measurements.csv \
    --method     kmeans \
    --n-clusters 4 \
    --output     clustered.csv
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--table` | path | yes | Input measurement table (CSV, TSV, or XLSX) |
| `--method` | str | no | Clustering method: `kmeans` (default), `dbscan`, `hdbscan`, or `mean_shift` |
| `--n-clusters` | int | no | K-Means: number of clusters (default: 3) |
| `--eps` | float | no | DBSCAN: neighbourhood radius (default: 0.5) |
| `--min-samples` | int | no | DBSCAN / HDBSCAN: minimum samples in a neighbourhood (default: 5) |
| `--min-cluster-size` | int | no | HDBSCAN: minimum cluster size (default: 5) |
| `--bandwidth` | float | no | Mean Shift: bandwidth; omit or set to 0 for automatic estimation |
| `--output` | path | yes | Output table file (CSV, TSV, or XLSX) |
| `--segmentation` | path | no | Segmentation TIFF; required when `--output-segmentation` is used |
| `--output-segmentation` | path | no | Output TIFF where each segment is painted with its `cluster_id`; noise segments are left as background (0) |

**Output**

The output table is the input table with one additional column:

| Column | Description |
|--------|-------------|
| `cluster_id` | Integer cluster label (1-based); `-1` for noise (DBSCAN / HDBSCAN only) |

When `--output-segmentation` is specified, each segment pixel is set to the `cluster_id`
of that segment (background and noise segments remain 0).

**Method defaults**

| Method | Key parameters and defaults |
|--------|----------------------------|
| `kmeans` | `--n-clusters 3` |
| `dbscan` | `--eps 0.5`, `--min-samples 5` |
| `hdbscan` | `--min-cluster-size 5` |
| `mean_shift` | bandwidth estimated automatically |

**Examples**

```bash
# K-Means with 5 clusters
segmentation-measurement analyze cluster \
    --table morphology.csv --method kmeans --n-clusters 5 --output clustered.csv

# DBSCAN – also write a cluster segmentation TIFF
segmentation-measurement analyze cluster \
    --table intensity.csv \
    --method dbscan --eps 1.0 --min-samples 3 \
    --output clustered.csv \
    --segmentation cells.tif \
    --output-segmentation clusters.tif

# HDBSCAN
segmentation-measurement analyze cluster \
    --table morphology.csv --method hdbscan --min-cluster-size 10 --output clustered.csv

# Mean Shift with automatic bandwidth
segmentation-measurement analyze cluster \
    --table intensity.csv --method mean_shift --output clustered.csv
```

---

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

---

### `train-classifier`

Train a random forest or logistic regression classifier from one or more annotated
measurement tables and save the fitted pipeline to a `.joblib` file.

An *annotated* table is a measurement table that contains an integer `annotation` column
(or whichever column name you specify with `--annotation-column`).  Rows with a value of
`0` in that column are treated as unannotated and excluded from training.  Annotated rows
are typically exported from the **Classification Analysis** napari widget, but you can
also create the column manually.

All numeric columns are used as features (excluding `label`, `annotation`,
`classification_id`, `classification_name`, `cluster_id`, `category_id`, and
`category_name`).  Features are z-score standardised inside the saved pipeline so no
separate pre-processing step is needed when applying the classifier.

```bash
segmentation-measurement analyze train-classifier \
    --tables  annotated.csv \
    --method  random_forest \
    --output  classifier.joblib
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--tables` | path(s) | yes | One or more annotated measurement tables (CSV, TSV, or XLSX); when multiple files are given they are concatenated before training |
| `--output` | path | yes | Output classifier file (`.joblib`) |
| `--method` | str | no | Classifier type: `random_forest` (default) or `logistic_regression` |
| `--annotation-column` | str | no | Column containing integer annotation labels (default: `annotation`) |
| `--n-estimators` | int | no | RF: number of trees (default: 100) |
| `--max-depth` | int | no | RF: maximum tree depth; omit or set to 0 for unlimited |
| `--c` | float | no | LR: regularisation strength C (default: 1.0) |
| `--max-iter` | int | no | LR: maximum number of solver iterations (default: 1000) |

**Examples**

```bash
# Train a random forest from a single annotated CSV
segmentation-measurement analyze train-classifier \
    --tables annotated.csv \
    --output classifier.joblib

# Train from two experiments combined, with 200 trees
segmentation-measurement analyze train-classifier \
    --tables experiment1.csv experiment2.csv \
    --n-estimators 200 \
    --output classifier.joblib

# Train a logistic regression classifier
segmentation-measurement analyze train-classifier \
    --tables annotated.csv \
    --method logistic_regression \
    --c 0.1 \
    --output classifier.joblib
```

---

### `classify`

Apply a previously trained classifier (saved with `train-classifier` or exported from the
napari widget) to a measurement table.  The output table gains two new columns:
`classification_id` (1-based integer) and `classification_name` (string).

```bash
segmentation-measurement analyze classify \
    --table      measurements.csv \
    --classifier classifier.joblib \
    --output     classified.csv
```

**Arguments**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--table` | path | yes | Input measurement table (CSV, TSV, or XLSX) |
| `--classifier` | path | yes | Trained classifier file (`.joblib`) |
| `--output` | path | yes | Output table file (CSV, TSV, or XLSX) |
| `--class-names` | str(s) | no | Names for each class in ascending class-label order (e.g. `--class-names mitotic interphase`); defaults to `class_1`, `class_2`, … |
| `--segmentation` | path | no | Segmentation TIFF; required when `--output-segmentation` is used |
| `--output-segmentation` | path | no | Output TIFF where each segment is painted with its `classification_id`; unclassified segments remain background (0) |

**Output columns**

| Column | Description |
|--------|-------------|
| `classification_id` | Integer class label (1-based); 0 for rows whose features were all NaN |
| `classification_name` | Human-readable class name |

**Examples**

```bash
# Apply classifier and save results as CSV
segmentation-measurement analyze classify \
    --table new_measurements.csv \
    --classifier classifier.joblib \
    --output classified.csv

# Apply and assign human-readable names to classes
segmentation-measurement analyze classify \
    --table new_measurements.csv \
    --classifier classifier.joblib \
    --class-names mitotic interphase apoptotic \
    --output classified.csv

# Also write a classification segmentation TIFF
segmentation-measurement analyze classify \
    --table new_measurements.csv \
    --classifier classifier.joblib \
    --output classified.csv \
    --segmentation cells.tif \
    --output-segmentation classified_seg.tif
```
