# Napari Plugin

The `segmentation-measurement` napari plugin provides interactive widgets for
post-processing segmentation label layers and for computing and exploring per-segment
intensity measurements – all without writing any Python code.

## Installation

```bash
pip install "segmentation-measurement[napari]"
```

After installation the plugin is automatically discovered by napari.

## Opening the Widgets

Open either widget from the napari menu:

**Plugins → segmentation-measurement → Postprocessing**

**Plugins → segmentation-measurement → Intensity Measurement**

Both widgets appear as dockable panels that can be placed anywhere in the napari window.

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

Creates an annular ring of a fixed width around each segment.  The output contains only
the ring pixels; the original segment interiors are set to `0`.  Rings are placed only on
background pixels; overlapping rings resolve in favour of the smaller label ID.  This is
commonly used to create pseudo-cytoplasm masks around segmented nuclei.

* **Ring width** – Width of the ring in pixels/voxels (default: 5).

---

## Intensity Measurement Widget

The Intensity Measurement widget follows a three-step workflow: measure per-segment
intensities, explore the distribution with a histogram, then optionally classify segments
into named categories based on thresholds.

### Layout (scrollable)

```
┌─────────────────────────────────┐
│ Segmentation:    [combo]        │
│ Intensity image: [combo]        │
│ [Measure intensities]           │
│ ┌ Measurements ──────────────┐ │
│ │  <table>  [Save table]     │ │
│ └────────────────────────────┘ │
│ ┌ Histogram ──────────────────┐ │
│ │ Column: [combo]             │ │
│ │  <histogram plot>           │ │
│ └────────────────────────────┘ │
│ ┌ Categorization ─────────────┐ │
│ │ Number of categories: [spin]│ │
│ │ Threshold 1: [spin]         │ │
│ │ ...                         │ │
│ │ Name 1: [edit]  ...         │ │
│ │ [Suggest thresholds]        │ │
│ │ Output layer: [edit]        │ │
│ │ [Categorize]                │ │
│ └────────────────────────────┘ │
└─────────────────────────────────┘
```

### Step 1 – Measure Intensities

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

#### Saving the table

Click **Save table** to export the measurements to a file.  A file-save dialog opens
and lets you choose the location and format:

* **CSV** (`.csv`) – comma-separated values
* **TSV** (`.tsv`) – tab-separated values
* **Excel** (`.xlsx`) – Excel workbook

### Step 2 – Explore with Histogram

The **Histogram** section shows the distribution of any numeric column in the
measurements table.

* Use the **Column** dropdown to switch between intensity statistics.
* Threshold lines (see Step 3) are drawn in red so you can evaluate the split visually.

> **Note:** The histogram requires `matplotlib`.  Install it with
> `pip install matplotlib` if it is not already available.

### Step 3 – Categorize Segments (optional)

Segments can be grouped into named categories based on one or more intensity thresholds.

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

* The measurements table gains two new columns: `category_id` (integer, 1-based) and
  `category_name` (string).
* A new Labels layer is created (or updated) in napari where each segment is assigned its
  category ID as the label value.  Use napari's built-in colormap controls to distinguish
  the categories visually.

#### How thresholds are applied

Segments with a value **below** the first threshold are assigned category 1, segments
between the first and second threshold are assigned category 2, and so on.  Thresholds
need not be sorted; the widget sorts them internally.
