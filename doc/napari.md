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

**Plugins → Segmentation Measurement → Group Manager → Group Manager**

All widgets appear as dockable panels that can be placed anywhere in the napari window.

### Working with measurement tables

Measurement and analysis results are stored as the `features` table of the source
Labels layer.  napari ships a built-in **Features Table** dock
(**Layers → Visualize → Features table widget**) that displays this table for the
currently selected layer.  Whenever a widget in this plugin writes to a layer's
features (after a measurement, after applying a threshold/cluster/classifier, after
loading or editing a table), the dock is opened automatically and the source layer
is selected so the result is visible immediately.  The dock supports sorting,
in-place editing, copy/paste, CSV save, and bidirectional row ↔ viewer selection
sync.

### Working with groups (batch processing)

A **group** is a named bundle of layers that you batch over.  Each group lists
ordered layers under three roles:

* `segmentation` (required, ≥1 layer) — the primary label layers to process
* `nucleus_segmentation` (optional) — paired nucleus segmentations for the
  Cell-Nucleus widget
* `intensity_image` (optional) — paired intensity images for the Intensity
  widget and (optionally) the Cell-Nucleus widget

Within a group, layers across roles are paired **by position**:
`segmentation[i]` is matched with `nucleus_segmentation[i]` and
`intensity_image[i]`.  An optional role's list must either be empty or have
exactly the same length as the segmentation list.

Groups are defined in the [Group Manager Widget](#group-manager-widget).
Once defined, every measurement and analysis widget exposes a **Target**
combo at the top with two options:

* `<single layer>` (default) — original single-layer behaviour.  Pick one
  segmentation (and optional pair partners) via the existing combos.
* a group name — operate on the group's members.  Measurement widgets
  iterate over members and write results into each member's `features`.
  Analysis widgets concatenate features across members for joint
  computation, then split results back to each member's `features` and
  emit one output label layer per member named `{output}_{layer}` (or
  just `{output}` for a single-member group).

Renaming a layer that is referenced by a group automatically updates the
group definition.

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

### Layout

```
┌─────────────────────────────────┐
│ Target:          [combo]        │
│ Segmentation:    [combo]        │
│ Intensity image: [combo]        │
│ [Measure intensities]           │
└─────────────────────────────────┘
```

### Workflow

1. Pick a **Target**: `<single layer>` (default) for the original
   single-pair behaviour, or a previously defined group name to batch
   over its members.  In group mode the **Segmentation** and **Intensity
   image** combos become read-only and show the first member; the group
   must define a non-empty `intensity_image` role.
2. Select a **Segmentation** layer (Labels) from the first dropdown.
3. Select an **Intensity image** layer (Image) from the second dropdown.
4. Click **Measure intensities**.

In group mode the measurement is run on every
`(segmentation[i], intensity_image[i])` pair in turn, writing results into
each segmentation layer's `features`.  See the
[Working with groups](#working-with-groups-batch-processing) section for
the broader pattern.

The result is merged into the segmentation layer's `features` table and the napari
**Features Table** dock is opened automatically with the segmentation layer selected.
Re-running the measurement on the same layer silently overwrites the existing
intensity columns; running a different measurement (e.g. Morphology) on the same
layer adds its columns alongside.

The columns added to `layer.features` are:

| Column | Description |
|--------|-------------|
| `index` | Integer segment label ID |
| `mean_intensity` | Mean pixel intensity |
| `median_intensity` | Median pixel intensity |
| `max_intensity` | Maximum pixel intensity |
| `min_intensity` | Minimum pixel intensity |
| `std_intensity` | Standard deviation |
| `percentile_10` | 10th percentile |
| `percentile_25` | 25th percentile (Q1) |
| `percentile_75` | 75th percentile (Q3) |
| `percentile_90` | 90th percentile |

### Saving the table

Use the **Save as CSV** button in the napari Features Table dock to export the
features.  For TSV / XLSX export, use the **Save table** button in the
[Table Manipulation Widget](#table-manipulation-widget) below.

---

## Morphology Measurement Widget

The Morphology Measurement widget computes per-segment shape descriptors from a label
layer.  Physical pixel/voxel sizes can be specified per axis to obtain measurements in
real-world units.

### Layout (scrollable)

```
┌─────────────────────────────────┐
│ Target:       [combo]           │
│ Segmentation: [combo]           │
│ ┌ Physical pixel/voxel size ─┐ │
│ │ Y: [spinbox]               │ │
│ │ X: [spinbox]               │ │
│ └────────────────────────────┘ │
│ [Measure morphology]            │
└─────────────────────────────────┘
```

For 3-D data a third spinbox **Z** is added automatically.

### Workflow

1. Pick a **Target**: `<single layer>` (default) for the original
   single-layer behaviour, or a previously defined group name to batch
   over its segmentation members.  In group mode the **Segmentation**
   combo becomes read-only and shows the first member; the same scale
   settings apply to every member.
2. Select a **Segmentation** layer (Labels) from the dropdown.  The scale spinboxes are
   pre-populated from the layer's `scale` attribute if it has been set; otherwise they
   default to `1.0`.
3. Adjust the per-axis scale values if needed.  For isotropic data a single value applies
   to all axes; for anisotropic data set each axis independently.
4. Click **Measure morphology**.

The result is merged into the segmentation layer's `features` table and the napari
**Features Table** dock is opened automatically with the segmentation layer selected.
Re-running the measurement on the same layer silently overwrites the morphology
columns; running a different measurement on the same layer adds its columns
alongside.

The columns added to `layer.features` (one row per segment) are:

**2-D columns**

| Column | Description |
|--------|-------------|
| `index` | Integer segment label ID |
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
| `index` | Integer segment label ID |
| `volume` | Volume in physical units (vx³ or µm³ etc.) |
| `surface_area` | Surface area computed via marching cubes |
| `sphericity` | 1.0 for a perfect sphere, <1 for elongated or irregular shapes |
| `solidity` | Ratio of segment volume to convex hull volume |
| `axis_major_length` | Length of the major axis of the fitted ellipsoid |
| `axis_minor_length` | Length of the minor axis of the fitted ellipsoid |
| `equivalent_diameter` | Diameter of a sphere with the same volume |

### Saving the table

Use the **Save as CSV** button in the napari Features Table dock, or the
**Save table** button in the [Table Manipulation Widget](#table-manipulation-widget)
for TSV / XLSX output.

---

## Threshold Analysis Widget

The Threshold Analysis widget categorizes segments into named groups based on one or more
thresholds applied to any numeric column of the selected layer's `features` table.

### Layout (scrollable)

```
┌──────────────────────────────────────┐
│ Target:       [combo]                │
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

#### Step 1 – Select the segmentation layer or group

The widget operates on the `features` table of the selected Labels layer (populated
by **Intensity Measurement**, **Morphology Measurement**, **Cell-Nucleus
Measurement**, or by loading a CSV via the [Table Manipulation
Widget](#table-manipulation-widget)).

1. Run one of the measurement widgets first (or load a CSV).
2. Pick a **Target**: `<single layer>` (default) for the original
   single-layer behaviour, or a previously defined group name.  In group
   mode the **Segmentation** combo becomes read-only.  The histogram and
   threshold suggestion are computed on the **concatenation** of all
   members' `features` so a single set of thresholds can be applied
   consistently across the batch.
3. In single-layer mode, pick the layer from the **Segmentation**
   dropdown.  The **Column** dropdown is filled with its numeric columns
   (excluding `index` and `category_id`).

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
4. Enter an **Output layer** name (default: `categories`).
5. Click **Categorize**.

Two things happen:

* The source layer's `features` gains two new columns: `category_id` (integer,
  1-based) and `category_name` (string).  The Features Table dock is opened
  automatically with the source layer selected so you can inspect them.
* A new Labels layer is created (or updated) in napari where each segment is assigned its
  category ID as the label value.  Use napari's built-in colormap controls to distinguish
  the categories visually.

In group mode every member's `features` receives the new columns and one
output Labels layer is created per member named `{output}_{layer_name}`
(or just `{output}` when the group has a single member).

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
│ Target:                 [combo]     │
│ Cell segmentation:      [combo]     │
│ Nucleus segmentation:   [combo]     │
│ Intensity image (optional): [combo] │
│ ┌ Physical pixel/voxel size ──────┐ │
│ │ Y: [spinbox]                    │ │
│ │ X: [spinbox]                    │ │
│ └─────────────────────────────────┘ │
│ [Measure cell-nucleus]              │
└─────────────────────────────────────┘
```

For 3-D data a third spinbox **Z** is added automatically.

### Workflow

1. Pick a **Target**: `<single layer>` (default) for the original
   per-pair behaviour, or a previously defined group name to batch over
   its members.  In group mode the cell, nucleus, and intensity-image
   combos become read-only and show the first member; the group must
   define a non-empty `nucleus_segmentation` role, while
   `intensity_image` is optional and is used when present.
2. Select a **Cell segmentation** layer (Labels) from the first dropdown.  The scale
   spinboxes are pre-populated from the layer's `scale` attribute if it has been set;
   otherwise they default to `1.0`.
3. Select a **Nucleus segmentation** layer (Labels) from the second dropdown.  This layer
   must have the same spatial dimensions as the cell segmentation.
4. Optionally select an **Intensity image** layer (Image) from the third dropdown.
   Choose `(none)` to skip intensity measurements.
5. Adjust the per-axis scale values if needed (same convention as the Morphology widget).
6. Click **Measure cell-nucleus**.

In group mode the measurement is run on every
`(segmentation[i], nucleus_segmentation[i], intensity_image[i] or None)`
triple in turn, writing results into each cell-segmentation layer's
`features`.

The result is merged into the **cell** segmentation layer's `features` table and the
napari **Features Table** dock is opened automatically with that layer selected.
One row per cell.

**Columns – without intensity image (2-D)**

| Column | Description |
|--------|-------------|
| `index` | Integer cell label ID |
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

### Saving the table

Use the **Save as CSV** button in the napari Features Table dock, or the
**Save table** button in the [Table Manipulation Widget](#table-manipulation-widget)
for TSV / XLSX output.

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
│ Target:       [combo]                │
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

#### Step 1 – Select the segmentation layer or group

The widget operates on the `features` table of the selected Labels layer.  Run a
measurement widget first (or load a CSV via the Table Manipulation widget), then
either pick the layer from the **Segmentation** dropdown or pick a group
from the **Target** dropdown.

In group mode the **Segmentation** combo becomes read-only.  Features
across the group's members are concatenated for joint clustering and the
2-D feature-reduction scatter plot, and one output Labels layer is
created per member named `{output}_{layer_name}` (or just `{output}` for
a single-member group).  The same cluster colours are applied across all
output layers so cluster IDs match visually.

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
4. Click **Cluster**.

Three things happen simultaneously:

* The source layer's `features` gains a new `cluster_id` column (1-based; `-1` for
  noise) and the napari Features Table dock is opened automatically with that layer
  selected.
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

Use the **Save as CSV** button in the napari Features Table dock, or the
**Save table** button in the [Table Manipulation Widget](#table-manipulation-widget)
for TSV / XLSX output.

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
│ Target: [combo]                      │
│ ┌ Layers ──────────────────────────┐ │
│ │ Segmentation: [combo]            │ │
│ │ Annotation layer: [combo] [Create new] │
│ │ [Project annotations to features]│ │
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

#### Step 1 – Select the segmentation layer or group

The widget operates on the `features` table of the selected Labels layer.  Run a
measurement widget first (or load a CSV via the Table Manipulation widget), then
pick a **Target**: `<single layer>` (default) for the original
single-layer behaviour, or a previously defined group name to classify
across the group's segmentation members.

In group mode the **Segmentation** combo is restricted to the group's
members so you can step through them one at a time to annotate each.
The class-names table pools detected annotation IDs across **every**
member of the group, so detected classes are not lost as you switch
members.  See [Per-member annotation persistence](#per-member-annotation-persistence)
below for how brushstrokes survive member switches.

#### Step 2 – Create an annotation layer

The **Annotation layer** combo defaults to `(none)` so per-member
persistence cannot accidentally overwrite an unrelated label layer.

1. Click **Create new** next to the **Annotation layer** dropdown.  A new, empty Labels
   layer called `annotations` is added to napari and automatically selected.
2. Alternatively, select an existing Labels layer from the **Annotation layer** dropdown
   if you already have annotations you want to use.

#### Step 3 – Paint annotations

Use napari's built-in label painting tools to draw brushstrokes on the annotation layer.

* Each label value you paint (1, 2, 3, …) represents a different class.
* You can use napari's color picker and label selector to switch between classes.
* Paint at least a few representative segments from each class.  You do not need to
  annotate every segment — the classifier will be applied to the rest automatically.

#### Step 4 – Project annotations into features

Click **Project annotations to features**.  The widget:

1. Reads the pixel-level brushstrokes from the annotation layer.
2. For each segment in the segmentation, takes the **majority-vote** annotation label
   across all annotated pixels that overlap that segment.  Segments with no annotation
   overlap receive annotation `0` (unannotated).
3. Merges an `annotation` column into the source layer's `features` (overwriting any
   previous annotation values).  The Features Table dock is opened automatically.
4. Populates the **Class names** table with all annotation label IDs detected.

> **Tip:** Repeat steps 3 and 4 as many times as needed.  Each click of **Project
> annotations to features** re-reads the current state of the annotation layer.

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
  numeric measurement columns as features (excluding `index`, `annotation`,
  `classification_id`, `classification_name`, `cluster_id`, `category_id`, and
  `category_name`).  Features are z-score standardised internally.
* The classifier is applied to **every** row in the layer's features (including
  unannotated ones).  Results are merged back into the source layer's `features` as
  two new columns: `classification_id` (1-based integer) and `classification_name`
  (string).  The Features Table dock is opened automatically with that layer
  selected.
* A new Labels layer is created (or updated) in napari where each segment is painted with
  its `classification_id`.  Colours are keyed off the class ID itself
  (using `tab10` for ≤10 classes and `tab20` beyond that), so the same
  class always renders in the same colour even when other classes are
  absent from a particular layer.

If you re-run **Train & Apply**, existing `classification_id` and `classification_name`
columns are excluded from the feature set so they do not affect the new result.

In group mode the classifier is trained on the **concatenation** of all
members' `features` (using each member's projected `annotation` column)
and then applied per-member.  One output Labels layer is created per
member named `{output}_{layer_name}` (or just `{output}` for a
single-member group).  Class colours are keyed off the class ID, so the
same class always renders in the same colour across all member outputs
even if a particular member only contains a subset of classes.

#### Per-member annotation persistence

In group mode the widget keeps a per-member cache of your brushstrokes
so they survive switching between members:

* When you switch the **Segmentation** combo to a different member, the
  current annotation layer's contents are saved (sparse-compressed) for
  the previously-active member, and the cached annotations for the new
  member are loaded into the same annotation layer.  If the new member
  has no cache yet, the layer is reset to zeros.
* Switching the **Target** combo back to `<single layer>` (or to another
  group) saves the current member's annotations first so they are
  available again when you re-enter the group.
* The cache is kept only as long as the widget is open and is keyed off
  the segmentation-layer name; renaming a member-layer mid-session
  decouples its cache.

The single-layer mode is unaffected: switching segmentation layers there
does not alter the annotation layer.

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

Use the **Save as CSV** button in the napari Features Table dock, or the
**Save table** button in the [Table Manipulation Widget](#table-manipulation-widget)
for TSV / XLSX output.

---

## Group Manager Widget

The Group Manager is the single place where you define and edit the layer
**groups** consumed by every measurement and analysis widget's *Target*
combo.  See [Working with groups](#working-with-groups-batch-processing)
for the underlying data model and pairing semantics.

### Layout (scrollable)

```
┌────────────────────────────────────────┐
│ ┌ Defined groups ────────────────────┐ │
│ │  exp_1  (3 seg, 3 nuc)             │ │
│ │  exp_2  (5 seg)                    │ │
│ │  ...                               │ │
│ │ [Delete selected]                  │ │
│ └────────────────────────────────────┘ │
│ ┌ Group editor ──────────────────────┐ │
│ │ Name: [edit]                       │ │
│ │ ┌ Segmentation layers (required)─┐ │ │
│ │ │  cells_01                      │ │ │
│ │ │  cells_02                      │ │ │
│ │ │ [Add selected][Remove][Up][Down] │ │
│ │ └────────────────────────────────┘ │ │
│ │ ┌ Nucleus layers (optional)──────┐ │ │
│ │ │  nuclei_01                     │ │ │
│ │ │  nuclei_02                     │ │ │
│ │ │ [Add selected][Remove][Up][Down] │ │
│ │ └────────────────────────────────┘ │ │
│ │ ┌ Intensity images (optional)────┐ │ │
│ │ │  raw_01                        │ │ │
│ │ │  raw_02                        │ │ │
│ │ │ [Add selected][Remove][Up][Down] │ │
│ │ └────────────────────────────────┘ │ │
│ │ ┌ Pairing preview ───────────────┐ │ │
│ │ │ Seg       Nucleus   Intensity  │ │ │
│ │ │ cells_01  nuclei_01 raw_01     │ │ │
│ │ │ cells_02  nuclei_02 raw_02     │ │ │
│ │ └────────────────────────────────┘ │ │
│ │ [Save]                             │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

### Workflow

1. **Select** layers in napari's main layer list (you can multi-select
   with Ctrl/Shift).
2. In the **Segmentation layers** section click **Add selected** to add
   the selected Labels layers to the role.  Layers are appended in
   napari layer-panel order; non-Labels layers in the selection are
   skipped, as are duplicates already in the list.
3. Optionally repeat for **Nucleus layers** (also Labels-only) and
   **Intensity images** (Image-only).
4. Reorder entries with **Up** / **Down** so each row of the
   **Pairing preview** at the bottom matches the segmentation–nucleus–
   image triple you actually want.  Within a group, layers across roles
   are paired by position.
5. Optional roles must be either empty or have the same length as the
   segmentation list — saving with mismatched lengths is rejected.
6. Type a **Name** and click **Save**.  If a group with that name
   already exists it is replaced.

Selecting a group in the top list loads its current members back into
the editor for editing.  Click **Delete selected** to remove the
highlighted group.

Renaming a layer that a group references automatically updates the
group's stored layer name.  Removing a layer leaves the dangling
reference in place; running a measurement or analysis widget that
targets the group will raise an informative error if a member layer is
missing.

---

## Table Manipulation Widget

The Table Manipulation widget edits the `features` table of a Labels layer.  It can
load an external CSV / TSV / XLSX file (which must contain an `index` column) and
merge it into the layer's features, drop a column from the layer's features, and
save the layer's features to a CSV / TSV / XLSX file.

### Layout

```
┌────────────────────────────────────────┐
│ Segmentation: [combo]                  │
│ ┌ Load table from file ──────────────┐ │
│ │ [Load file…]                       │ │
│ └────────────────────────────────────┘ │
│ ┌ Drop column ───────────────────────┐ │
│ │ Column: [combo]   [Drop]           │ │
│ └────────────────────────────────────┘ │
│ [Save table]                            │
└────────────────────────────────────────┘
```

### Loading a table from file

Click **Load file…** to read a CSV, TSV, or XLSX file.  The file must contain an
`index` column whose values are the segment label IDs; loading is rejected
otherwise.  The columns of the loaded file are merged into the selected layer's
`features` (outer join on `index`).  Columns present in both the file and the
existing features are overwritten with the values from the file.  The Features
Table dock is opened automatically after the merge.

> **Tip:** Multiple measurement widgets writing to the same layer follow the same
> merge rules — running Intensity then Morphology on the same Labels layer leaves
> all columns from both measurements in the layer's `features`.

### Dropping a column

Select a column from the **Drop column** dropdown and click **Drop**.  The column
is removed from the selected layer's `features`.  The `index` column is the
segment identifier and is never offered for dropping.

### Saving the table

Click **Save table** to export the selected layer's `features` to a CSV, TSV, or
XLSX file.  This complements the napari Features Table dock's CSV-only save by
also supporting TSV and Excel output.
