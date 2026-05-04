# Napari Plugin

The `segmentation-measurement` napari plugin provides interactive widgets for
post-processing segmentation label layers and for computing and exploring per-segment
measurements – all without writing any Python code.

## Installation

```bash
pip install "segmentation-measurement[napari]"
```

After installation the plugin is automatically discovered by napari.

## Opening the Widgets

Open any widget from the napari menu:

**Plugins → Segmentation Measurement → Postprocessing**

**Plugins → Segmentation Measurement → Intensity Measurement → Intensity Measurement**

**Plugins → Segmentation Measurement → Morphology Measurement → Morphology Measurement**

**Plugins → Segmentation Measurement → Threshold Analysis → Threshold Analysis**

**Plugins → Segmentation Measurement → Cell-Nucleus Measurement → Cell-Nucleus Measurement**

**Plugins → Segmentation Measurement → Clustering Analysis → Clustering Analysis**

**Plugins → Segmentation Measurement → Classification Analysis → Classification Analysis**

**Plugins → Segmentation Measurement → Table Manipulation → Table Manipulation**

All widgets appear as dockable panels that can be placed anywhere in the napari window.

---

## Postprocessing Widget

The Postprocessing widget applies one of three post-processing operations to an existing
label layer and writes the result to a new layer or back to the same layer.

### Layout

```
┌─────────────────────────────────┐
│ Input segmentation: [combo]     │
│ Output name:        [combo]     │
│ Method:             [combo]     │
│ ┌ Parameters ──────────────┐   │
│ │  <method-specific param> │   │
│ └──────────────────────────┘   │
│ [Run]                           │
└─────────────────────────────────┘
```

### Controls

**Input segmentation**
: Dropdown list of all Labels layers currently loaded in napari.  Select the layer you
  want to process.

**Output name**
: Dropdown showing existing Labels layers plus the default entry `postprocessed`.  You
  can also type a new name directly.  If the chosen name matches an existing layer the
  data of that layer is updated in place; otherwise a new Labels layer is added.  Setting
  the output name equal to the input name processes the input layer in place.

**Method**
: Choose one of the three post-processing operations (see below).  The **Parameters**
  panel updates immediately to show the relevant controls.

**Run**
: Apply the selected method with the current parameters.

### Methods

#### Filter Small Segments

Removes segments whose pixel (2-D) or voxel (3-D) count is below the threshold.
Removed segments become background (`0`).

* **Min size** – Minimum number of pixels/voxels a segment must have to be retained
  (default: 100).

#### Remove Small Holes

Fills enclosed background holes within segments when the hole size does not exceed the
threshold.  Other segments are never overwritten.

* **Max hole size** – Maximum hole size in pixels/voxels to fill (default: 50).

#### Ring Mask

Creates an annular ring of a fixed width around each segment.  Rings are placed only on
background pixels; overlapping rings resolve in favour of the smaller label ID.  This is
commonly used to create pseudo-cytoplasm masks around segmented nuclei.

* **Ring width** – Width of the ring in pixels/voxels (default: 5).
* **Keep original** – When checked (default), the original segment pixels are retained in
  the output alongside the ring pixels.  Uncheck to produce a ring-only mask where the
  original segment interiors are set to `0`.

#### Watershed

Refines a segmentation using the watershed algorithm.  The selected input
segmentation is used as seed markers; a separate heatmap image layer provides
the topographic landscape.  The algorithm floods from low heatmap values
upward, so the heatmap should have **low values at segment boundaries**.  If
your heatmap instead has high values at object centres (e.g. a distance
transform or foreground-probability map), negate it before passing it to the
widget.

* **Heatmap** – Image layer used as the watershed landscape (low values flooded first).
* **Mask (optional)** – Label layer whose footprint restricts processing.
  Pixels outside the mask are set to 0 in the output.  Select **None** to
  process all pixels (default).

---

## Intensity Measurement Widget

The Intensity Measurement widget computes per-segment intensity statistics from a label
layer and a co-registered intensity image.

### Layout (scrollable)

```
┌─────────────────────────────────┐
│ Segmentation:    [combo]        │
│ Intensity image: [combo]        │
│ [Measure intensities]           │
│ ┌ Measurements ──────────────┐ │
│ │  <table>  [Save table]     │ │
│ └────────────────────────────┘ │
└─────────────────────────────────┘
```

### Workflow

1. Select a **Segmentation** layer (Labels) from the first dropdown.
2. Select an **Intensity image** layer (Image) from the second dropdown.
3. Click **Measure intensities**.

The **Measurements** table is filled with one row per segment.  The columns are:

| Column | Description |
|--------|-------------|
| `label` | Integer segment label ID |
| `mean_intensity` | Mean pixel intensity |
| `median_intensity` | Median pixel intensity |
| `max_intensity` | Maximum pixel intensity |
| `min_intensity` | Minimum pixel intensity |
| `std_intensity` | Standard deviation |
| `percentile_10` | 10th percentile |
| `percentile_25` | 25th percentile (Q1) |
| `percentile_75` | 75th percentile (Q3) |
| `percentile_90` | 90th percentile |

The table is also registered internally so that the **Threshold Analysis**,
**Clustering Analysis**, and **Classification Analysis** widgets can access it directly
(see below).

### Saving the table

Click **Save table** to export the measurements to a file.  A file-save dialog opens
and lets you choose the location and format:

* **CSV** (`.csv`) – comma-separated values
* **TSV** (`.tsv`) – tab-separated values
* **Excel** (`.xlsx`) – Excel workbook

---

## Morphology Measurement Widget

The Morphology Measurement widget computes per-segment shape descriptors from a label
layer.  Physical pixel/voxel sizes can be specified per axis to obtain measurements in
real-world units.

### Layout (scrollable)

```
┌─────────────────────────────────┐
│ Segmentation: [combo]           │
│ ┌ Physical pixel/voxel size ─┐ │
│ │ Y: [spinbox]               │ │
│ │ X: [spinbox]               │ │
│ └────────────────────────────┘ │
│ [Measure morphology]            │
│ ┌ Measurements ──────────────┐ │
│ │  <table>  [Save table]     │ │
│ └────────────────────────────┘ │
└─────────────────────────────────┘
```

For 3-D data a third spinbox **Z** is added automatically.

### Workflow

1. Select a **Segmentation** layer (Labels) from the dropdown.  The scale spinboxes are
   pre-populated from the layer's `scale` attribute if it has been set; otherwise they
   default to `1.0`.
2. Adjust the per-axis scale values if needed.  For isotropic data a single value applies
   to all axes; for anisotropic data set each axis independently.
3. Click **Measure morphology**.

The **Measurements** table is filled with one row per segment.

**2-D columns**

| Column | Description |
|--------|-------------|
| `label` | Integer segment label ID |
| `area` | Area in physical units (px² or µm² etc.) |
| `perimeter` | Perimeter length in physical units |
| `sphericity` | Circularity: 1.0 for a perfect circle, <1 for elongated or irregular shapes |
| `solidity` | Ratio of segment area to convex hull area |
| `axis_major_length` | Length of the major axis of the fitted ellipse |
| `axis_minor_length` | Length of the minor axis of the fitted ellipse |
| `equivalent_diameter` | Diameter of a circle with the same area |

**3-D columns**

| Column | Description |
|--------|-------------|
| `label` | Integer segment label ID |
| `volume` | Volume in physical units (vx³ or µm³ etc.) |
| `surface_area` | Surface area computed via marching cubes |
| `sphericity` | 1.0 for a perfect sphere, <1 for elongated or irregular shapes |
| `solidity` | Ratio of segment volume to convex hull volume |
| `axis_major_length` | Length of the major axis of the fitted ellipsoid |
| `axis_minor_length` | Length of the minor axis of the fitted ellipsoid |
| `equivalent_diameter` | Diameter of a sphere with the same volume |

The table is also registered internally so that the **Threshold Analysis**,
**Clustering Analysis**, and **Classification Analysis** widgets can access it directly.

### Saving the table

Click **Save table** to export the measurements (same formats as Intensity Measurement).

---

## Threshold Analysis Widget

The Threshold Analysis widget categorizes segments into named groups based on one or more
thresholds applied to any numeric column in a previously computed measurement table.

### Layout (scrollable)

```
┌──────────────────────────────────────┐
│ ┌ Measurement table ───────────────┐ │
│ │ Table: [combo]  [Refresh]        │ │
│ │  <table>  [Save table]           │ │
│ └──────────────────────────────────┘ │
│ Segmentation: [combo]                │
│ ┌ Column histogram ────────────────┐ │
│ │ Column: [combo]                  │ │
│ │  <histogram plot>                │ │
│ └──────────────────────────────────┘ │
│ ┌ Categorization ──────────────────┐ │
│ │ Number of categories: [spin]     │ │
│ │ Threshold 1: [spin]  ...         │ │
│ │ Name 1: [edit]  ...              │ │
│ │ [Suggest thresholds]             │ │
│ │ Output layer: [edit]             │ │
│ │ [Categorize]                     │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

### Workflow

#### Step 1 – Select a measurement table

The widget operates on tables produced by the **Intensity Measurement** or **Morphology
Measurement** widgets in the same napari session.

1. Run one of the measurement widgets first.
2. Click **Refresh** to populate the **Table** dropdown with all available tables.
3. Select the desired table from the dropdown.  The table is displayed and the
   **Column** dropdown is filled with its numeric columns (excluding `label`).

#### Step 2 – Explore the histogram

The **Column histogram** section shows the distribution of the currently selected column.
Threshold lines are drawn in red so you can evaluate the split visually before applying
it.

> **Note:** The histogram requires `matplotlib`.  Install it with
> `pip install matplotlib` if it is not already available.

#### Step 3 – Set thresholds and categorize

1. Set **Number of categories** (2–10).  The threshold and name fields update
   automatically.
2. Enter threshold values in the **Threshold** spin-boxes, or click
   **Suggest thresholds** to auto-populate them using equally-spaced quantiles of the
   selected column.  The threshold lines on the histogram update in real time.
3. Optionally rename each category in the **Name** fields (defaults:
   `category_1`, `category_2`, …).
4. Select the **Segmentation** layer to use for the output label layer.
5. Enter an **Output layer** name (default: `categories`).
6. Click **Categorize**.

Two things happen:

* The measurements table gains two new columns: `category_id` (integer, 1-based) and
  `category_name` (string).
* A new Labels layer is created (or updated) in napari where each segment is assigned its
  category ID as the label value.  Use napari's built-in colormap controls to distinguish
  the categories visually.

#### How thresholds are applied

Segments with a value **below** the first threshold are assigned category 1, segments
between the first and second threshold are assigned category 2, and so on.  Thresholds
need not be sorted; the widget sorts them internally.

---

## Cell-Nucleus Measurement Widget

The Cell-Nucleus Measurement widget computes per-cell features that combine a cell
segmentation with a nucleus segmentation.  It reports the number of nuclei per cell,
cell-to-nucleus area/volume ratios, and optionally cytoplasmic vs. nuclear intensity
statistics.

### Layout (scrollable)

```
┌─────────────────────────────────────┐
│ Cell segmentation:      [combo]     │
│ Nucleus segmentation:   [combo]     │
│ Intensity image (optional): [combo] │
│ ┌ Physical pixel/voxel size ──────┐ │
│ │ Y: [spinbox]                    │ │
│ │ X: [spinbox]                    │ │
│ └─────────────────────────────────┘ │
│ [Measure cell-nucleus]              │
│ ┌ Measurements ─────────────────┐  │
│ │  <table>  [Save table]        │  │
│ └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

For 3-D data a third spinbox **Z** is added automatically.

### Workflow

1. Select a **Cell segmentation** layer (Labels) from the first dropdown.  The scale
   spinboxes are pre-populated from the layer's `scale` attribute if it has been set;
   otherwise they default to `1.0`.
2. Select a **Nucleus segmentation** layer (Labels) from the second dropdown.  This layer
   must have the same spatial dimensions as the cell segmentation.
3. Optionally select an **Intensity image** layer (Image) from the third dropdown.
   Choose `(none)` to skip intensity measurements.
4. Adjust the per-axis scale values if needed (same convention as the Morphology widget).
5. Click **Measure cell-nucleus**.

The **Measurements** table is filled with one row per cell.

**Columns – without intensity image (2-D)**

| Column | Description |
|--------|-------------|
| `label` | Integer cell label ID |
| `n_nuclei` | Number of nucleus labels overlapping with this cell |
| `cell_area` | Area of the whole cell in physical units (nucleus included) |
| `nucleus_area` | Total area of nuclei within this cell in physical units |
| `area_ratio` | `cell_area / nucleus_area`; `NaN` for cells with no nucleus |

For 3-D data the columns are `cell_volume`, `nucleus_volume`, and `volume_ratio`
instead.

**Additional columns – with intensity image**

When an intensity image is selected, columns are added for each statistic `{stat}` in
`mean`, `median`, `max`, `min`, `percentile_10`, `percentile_25`, `percentile_75`,
`percentile_90`:

| Column | Description |
|--------|-------------|
| `cell_{stat}_intensity` | Statistic over the cytoplasmic region (cell pixels where no nucleus is present) |
| `nucleus_{stat}_intensity` | Statistic over all nuclear pixels within this cell |
| `{stat}_intensity_ratio` | `cell_{stat}_intensity / nucleus_{stat}_intensity`; `NaN` when either region is empty or the nucleus value is zero |

The table is also registered internally so that the **Threshold Analysis**,
**Clustering Analysis**, and **Classification Analysis** widgets can access it directly.

### Saving the table

Click **Save table** to export the measurements (same formats as Intensity Measurement:
CSV, TSV, Excel).

---

## Clustering Analysis Widget

The Clustering Analysis widget groups segments into clusters based on all numeric columns
in a previously computed measurement table.  After clustering, a 2-D feature-reduction
scatter plot visualises the result, and a new label layer is created where each segment is
painted with its cluster ID.  The scatter-plot colours and the label-layer colours are
kept in sync.

### Layout (scrollable)

```
┌──────────────────────────────────────┐
│ ┌ Measurement table ───────────────┐ │
│ │ Table: [combo]  [Refresh]        │ │
│ │  <table>  [Save table]           │ │
│ └──────────────────────────────────┘ │
│ Segmentation: [combo]                │
│ ┌ Feature reduction ───────────────┐ │
│ │ Method: [UMAP▾]  [Reduce]        │ │
│ │  <2-D scatter plot>              │ │
│ └──────────────────────────────────┘ │
│ ┌ Clustering ──────────────────────┐ │
│ │ Method: [K-Means▾]               │ │
│ │  <method-specific parameters>    │ │
│ │ Output layer: [edit]             │ │
│ │ [Cluster]                        │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

### Workflow

#### Step 1 – Select a measurement table

The widget operates on tables produced by the **Intensity Measurement**,
**Morphology Measurement**, or **Cell-Nucleus Measurement** widgets in the same napari
session.

1. Run one of the measurement widgets first.
2. Click **Refresh** to populate the **Table** dropdown with all available tables.
3. Select the desired table.  The table is displayed in the widget.

#### Step 2 – Explore the feature space (optional)

1. Choose a **Feature reduction** method: **UMAP** (default), **TSNE**, or **PCA**.
2. Click **Reduce** to compute a 2-D embedding of the features and display an uncoloured
   scatter plot.

> **Note:** UMAP requires the optional `umap-learn` package
> (`pip install umap-learn`).  If it is not installed the widget falls back to PCA
> automatically.  Changing the reduction method clears the cached embedding so the next
> **Reduce** or **Cluster** call recomputes it.

#### Step 3 – Cluster

1. Select a **Clustering method** from the dropdown (see table below).
2. Adjust the method-specific parameters shown below the dropdown.
3. Enter an **Output layer** name (default: `clusters`).
4. Select the **Segmentation** layer to use for the output.
5. Click **Cluster**.

Three things happen simultaneously:

* The measurements table gains a new `cluster_id` column (1-based; `-1` for noise).
* The scatter plot is redrawn with each point coloured by its cluster.
* A new Labels layer is created (or updated) where each segment is painted with its
  `cluster_id`.  The layer colours are set to **exactly match** the scatter-plot colours.

If you re-run clustering, the existing `cluster_id` column is excluded from the feature
set so it does not affect the new result.

#### Clustering methods and parameters

| Method | Widget label | Key parameters (defaults) |
|--------|-------------|--------------------------|
| scikit-learn KMeans | **K-Means** | **N clusters** (3) |
| scikit-learn DBSCAN | **DBSCAN** | **Eps** (0.5), **Min samples** (5) |
| scikit-learn HDBSCAN | **HDBSCAN** | **Min cluster size** (5) |
| scikit-learn MeanShift | **Mean Shift** | **Bandwidth** (0 = auto) |

#### Cluster IDs and label values

Cluster IDs are **1-based**: the first cluster found is 1, the second is 2, and so on.
Segments that are classified as noise by DBSCAN or HDBSCAN receive `cluster_id = -1` and
remain as background (0) in the output label layer.

#### Color matching

The widget uses matplotlib's `tab10` (or `tab20` when there are more than 10 clusters)
colormap to assign one colour per cluster.  The same colour array is applied to the
Labels layer via `DirectLabelColormap`, so the scatter-plot legend and the segmentation
overlay always show identical colours.

### Saving the table

Click **Save table** to export the measurements with the cluster column (CSV, TSV, or
Excel).

---

## Classification Analysis Widget

The Classification Analysis widget lets you interactively annotate a small number of
segments with class labels using napari's paint tools, train a random forest or logistic
regression classifier on those annotations, and then apply it to every segment in the
table.  The result is written to a new label layer and two new columns in the measurement
table.  Trained classifiers can be exported to disk and reloaded later.

### Layout (scrollable)

```
┌──────────────────────────────────────┐
│ ┌ Measurement table ───────────────┐ │
│ │ Table: [combo]  [Refresh]        │ │
│ │  <table>  [Save table]           │ │
│ └──────────────────────────────────┘ │
│ ┌ Layers ──────────────────────────┐ │
│ │ Segmentation: [combo]            │ │
│ │ Annotation layer: [combo] [Create new] │
│ │ [Project annotations to table]   │ │
│ └──────────────────────────────────┘ │
│ ┌ Class names ─────────────────────┐ │
│ │  Label ID │ Class Name           │ │
│ │  <editable rows>                 │ │
│ └──────────────────────────────────┘ │
│ ┌ Classifier ──────────────────────┐ │
│ │ Method: [Random Forest▾]         │ │
│ │  <method-specific parameters>    │ │
│ │ Output layer: [edit]             │ │
│ │ [Train & Apply]                  │ │
│ │ [Load classifier] [Apply] [Export classifier] │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

### Workflow

#### Step 1 – Select a measurement table

The widget operates on tables produced by the **Intensity Measurement**,
**Morphology Measurement**, or **Cell-Nucleus Measurement** widgets in the same napari
session.

1. Run one of the measurement widgets first.
2. Click **Refresh** to populate the **Table** dropdown with all available tables.
3. Select the desired table.  The table is displayed in the widget.

#### Step 2 – Create an annotation layer

1. Select the **Segmentation** layer that the table was derived from.
2. Click **Create new** next to the **Annotation layer** dropdown.  A new, empty Labels
   layer called `annotations` is added to napari and automatically selected.
3. Alternatively, select an existing Labels layer from the **Annotation layer** dropdown
   if you already have annotations you want to use.

#### Step 3 – Paint annotations

Use napari's built-in label painting tools to draw brushstrokes on the annotation layer.

* Each label value you paint (1, 2, 3, …) represents a different class.
* You can use napari's color picker and label selector to switch between classes.
* Paint at least a few representative segments from each class.  You do not need to
  annotate every segment — the classifier will be applied to the rest automatically.

#### Step 4 – Project annotations to the table

Click **Project annotations to table**.  The widget:

1. Reads the pixel-level brushstrokes from the annotation layer.
2. For each segment in the segmentation, takes the **majority-vote** annotation label
   across all annotated pixels that overlap that segment.  Segments with no annotation
   overlap receive annotation `0` (unannotated).
3. Writes an `annotation` column to the measurement table (displayed in the widget).
4. Populates the **Class names** table with all annotation label IDs detected.

> **Tip:** Repeat steps 3 and 4 as many times as needed.  Each click of **Project
> annotations to table** re-reads the current state of the annotation layer.

#### Step 5 – Name the classes (optional)

The **Class names** table lists each detected annotation label ID with an editable name
field.  Click a name cell and type to rename a class (e.g. change `class_1` to
`mitotic`, `class_2` to `interphase`).  These names are written to the
`classification_name` output column.

#### Step 6 – Train and apply the classifier

1. Choose a **Method** (default: **Random Forest**) and adjust the parameters if needed
   (see table below).
2. Enter an **Output layer** name (default: `classification`).
3. Click **Train & Apply**.

Three things happen:

* A scikit-learn classifier is trained on all rows where `annotation > 0`, using all
  numeric measurement columns as features (excluding `label`, `annotation`,
  `classification_id`, `classification_name`, `cluster_id`, `category_id`, and
  `category_name`).  Features are z-score standardised internally.
* The classifier is applied to **every** row in the table (including unannotated ones).
  Results are written to two new columns: `classification_id` (1-based integer) and
  `classification_name` (string).
* A new Labels layer is created (or updated) in napari where each segment is painted with
  its `classification_id`.  Distinct colours are assigned per class using the `tab10`
  colormap.

If you re-run **Train & Apply**, existing `classification_id` and `classification_name`
columns are excluded from the feature set so they do not affect the new result.

#### Classification methods and parameters

| Method | Widget label | Key parameters (defaults) |
|--------|-------------|--------------------------|
| scikit-learn RandomForestClassifier | **Random Forest** | **N estimators** (100), **Max depth** (0 = unlimited) |
| scikit-learn LogisticRegression | **Logistic Regression** | **C** (1.0), **Max iterations** (1000) |

#### Class IDs

Classification IDs are **1-based** and match the annotation label values painted in the
annotation layer.  A segment that could not be classified (e.g. because all its feature
values were NaN) receives `classification_id = 0` and an empty `classification_name`.

#### Applying a pre-trained classifier

To apply a classifier that was saved in a previous session:

1. Click **Load classifier** and select a `.joblib` file.
2. Click **Apply** (without retraining).

The loaded classifier is applied to the current table immediately.

### Exporting the classifier

Click **Export classifier** to save the trained pipeline (StandardScaler +
classifier) to a `.joblib` file.  The exported file can be reloaded in the widget (see
above) or used with the `analyze classify` CLI command to apply it to new tables in batch.

### Saving the table

Click **Save table** to export the measurement table with the `classification_id` and
`classification_name` columns (CSV, TSV, or Excel).

---

## Table Manipulation Widget

The Table Manipulation widget loads, edits, and combines measurement tables.  It is
useful for stitching together independently produced measurements (e.g. intensity and
morphology) into one table that can then be passed to a downstream analysis widget,
and for cleaning up tables before analysis or export.

### Layout

```
┌────────────────────────────────────────┐
│ ┌ Load table ────────────────────────┐ │
│ │ From plugin: [combo] [Refresh] [Load] │
│ │ From file:   [Load file…]          │ │
│ └────────────────────────────────────┘ │
│ ┌ Current table ─────────────────────┐ │
│ │ Loaded: <name>                     │ │
│ │ [QTableWidget]                     │ │
│ └────────────────────────────────────┘ │
│ ┌ Drop column ───────────────────────┐ │
│ │ Column: [combo]   [Drop]           │ │
│ └────────────────────────────────────┘ │
│ ┌ Merge with table ──────────────────┐ │
│ │ Other table: [combo]   [Merge]     │ │
│ └────────────────────────────────────┘ │
│ [Save table]                            │
└────────────────────────────────────────┘
```

### Loading a table

Two sources are supported:

* **From plugin** — Pick a table that was produced by another widget
  (Intensity, Morphology, Cell-Nucleus, …).  Click **Refresh** if a recently
  produced table does not yet appear in the dropdown, then **Load** to
  display it.
* **From file** — Click **Load file…** to read a CSV, TSV, or XLSX file.
  The widget verifies that the file contains a `label` column and refuses
  to load it otherwise.

After loading, the widget registers the table in the in-memory registry under
the source name (or the file stem) so that downstream analysis widgets can
pick it up immediately.

### Dropping a column

Select a column from the **Drop column** dropdown and click **Drop**.  The
displayed table is updated in place; the change is also propagated back to
the registered table.  The `label` column is the segment identifier and is
never offered for dropping.

### Merging another table

Select a registered measurement table from the **Other table** dropdown and
click **Merge**.  The widget performs an outer join on the `label` column.
If the other table contains columns that are also in the current table the
merge is rejected with a dialog — drop the conflicting columns first.

### Saving the table

Click **Save table** to export the current table to CSV, TSV, or Excel.
