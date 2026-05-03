# General Design

This repository provides common functionality for post-processing,  measurements, and analysis of instance segmentations for microscopy image analysis. The functionality is currently being implemented.

Specifically, it provides / will provide the following functionality:
- A utility for post-processing segmentations, such as size filtering, filling small holes, and computing a ring-mask across segments.
- A utility for measuring intensities.
- A utility for measuring cell to nucleus intensity ratios and related measures.
- A utility for measuring morphology, such as area / volume, surface, sphericity, etc.

For each utility the following entrypoints are provided:
- A python function in the `segmentation_measurement` python library.
- A napari plugin widget with in the `segmentation_measurement` napari plugin.
- A command line utility function.

Tests for the python function and CLI are written with `unittest` and `pytest`.

The library should be pip-installable, the functionality should be implemented with skimage, scipy, pandas and other standard scientific python libraries. All functions should support 2D and 3D inputs (or arbitrary dimensionality if possible).

All python functions are documented with doc strings according to google convention and use type annotations. The code should be PEP8 compliant.

The napari plugin should support visualizing the measurements as tables and support saving these to excel, csv, and tsv.

The documentation is built with pdoc. Extra documentation is written in the folder `doc/`, with `doc/start.md` containing a short description of the tool and the installation instructions, `doc/napari.md` a detailed documentation of the napari plugin, and `doc/cli.md` a detailed documentation of the CLI.

Below are details on the functionality.

## Post-processing utility

Should implement the following post-processing functionality:
- Filter out small segments below a certain size threshold and set these to zero (background label).
- Remove small holes from segments, below a given size threshold.
- Compute the "ring-mask" of all segments. I.e. the ring / hull around each segment of a specified pixel / voxel size that gets assigned the same ID as its respective segment.

Implementation guide:
- In the python library, each of these functionalities should be implemented as a specific function.
- In the CLI it should be a single top-level command that has individual sub-commands per functionality.
- In napari it should be a single widget that enables running the different post-processing methods with a specified input segmentation and (new) output segmentation. If input and output segmentation are the same the input segmentation should be post-processed in place.

## Intensity measurement widget

Takes as input a segmentation and an intensity image.

Should implement the following functionality:
- Computing intensity measurements: the mean, median, max, standard deviation and reasonable percentiles. Use skimage regionprops and represent the results as a pandas dataframe.
- Separating the cells into N different categories based on N-1 thresholds with respect to one of the measurements, e.g. 3 categories based on the mean intensity. The function should take the dataframe from the previous function as input.
- A function to suggest the thresholds for the N categories and a given column based on a suitable heuristics.

The napari plugin should provide these three features so that:
- Users can first select image and segmentation to measure the per object intensity table.
- The table and a histogram of a selected column are displayed in the widget. 
- The user can then either enter the number of categories and corresponding thresholds or just the number of categories and derive the thresholds via the heuristics. Categories can be named. It should be possible to modify the suggested thresholds; they should be shown in the histogram. The output should be a new segmentation layer that gives objects the category id and a new column in the intensity table with the category ID and name.

Implementation details on other functionality will follow.
