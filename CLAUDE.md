# General Design

This repository provides common functionality for post-processing, measurements, and analysis of instance segmentations for microscopy image analysis. The functionality is currently being implemented.

Specifically, it provides / will provide the following functionality:
- Post-processing segmentations, such as size filtering, filling small holes, and computing a ring-mask across segments.
- Common post-processing operations such as size filtering and hole-closing.
- Common measurements, such as morphology, intensity, and combined cytosol and nucleus features.
- Analysis functionality such as thresholding, clustering, and classification, based on the measureents.

For each utility the following entrypoints are provided:
- A python function in the `segmentation_measurement` python library.
- A napari plugin widget with in the `segmentation_measurement` napari plugin.
- A command line utility function.

Tests for the python function and CLI are written with `unittest` and `pytest`.

The library should be pip-installable, the functionality should be implemented with skimage, scipy, pandas and other standard scientific python libraries. All functions should support 2D and 3D inputs (or arbitrary dimensionality if possible).

All python functions are documented with doc strings according to google convention and use type annotations. The code should be PEP8 compliant.

The napari plugin should support visualizing the measurements as tables and support saving these to excel, csv, and tsv.

The documentation is built with pdoc. Extra documentation is written in the folder `doc/`, with `doc/start.md` containing a short description of the tool and the installation instructions, `doc/napari.md` a detailed documentation of the napari plugin, and `doc/cli.md` a detailed documentation of the CLI.

The functionality is divided into three categories:
- Segmentation post-processing
- Segmentation-derived measurements
- Analysis of measurements

Below is a description of the respective functionality. Some of it is not yet implemented.

# Post-processing

Implements the following post-processing functionality:
- Filter out small segments below a certain size threshold and set these to zero (background label).
- Remove small holes from segments, below a given size threshold.
- Compute the "ring-mask" of all segments. I.e. the ring / hull around each segment of a specified pixel / voxel size that gets assigned the same ID as its respective segment.

Implementation guide:
- In the python library, each of these functionalities should be implemented as a specific function.
- In the CLI it should be a single top-level command that has individual sub-commands per functionality.
- In napari it should be a single widget that enables running the different post-processing methods with a specified input segmentation and (new) output segmentation. If input and output segmentation are the same the input segmentation should be post-processed in place.

# Measurements

Measurements are implemented via `skimage.measure.regionprops`. 
The measurement python functions return a pandas dataframe with the measurement result. 
The CLI saves the results to an excel, csv, or tsv table, derived from the output filename, with csv as default if no extension is given.

The napari plugin widgets add the respective widget to the left interface. With a button for saving the result to a csv, tsv, or excel file.

Common functionality, such as table saving and table representation in napari, should be re-used between functions and plugin widgets.

## Intensity measurement

Takes as input a segmentation and an intensity image.

Implements the following functionality: compute intensity measurements: the mean, median, max, standard deviation and reasonable percentiles.

The napari plugin provides these feature:
- Users can select image and segmentation to measure the per object intensity table.
- The table is then displayed in the widget.

## Morphology measurement

Takes as input a segmentation. Also the physical scale / pixel size of the segmentation. The default for the scale is 1 (isotropic) but it can be anisotropic with 2 / 3 values in 2d / 3d.

Computes the following morphological features for 2d / 3d:
volume / area, surface area / circumference, sphericity, solidity, extent of the major axes (ellipsoidal fit), radius of a fit sphere

The napari plugin widget derives the default values for physical scale from the scale of the label layer (if available, otherwise defaults to 1).

## Cell-nucleus measurement

Takes as input a cell segmentation and nucleus segmentation as well as the physical scale / pixel size (see morphology measurement for details on pixel size). Takes an intensity image as optinal input.

Computes the following features:
- The number of nuclei per cell (= nuber of unique nucleus IDs per cell ID, or zero if there are no nuclei in there)
- The ratio of cell area / volume to nuclear area / volume for each cell ID, respecting the physical scale. Here, the cell area / volume encompasses the nucleus, i.e. the nuclear mask is not excluded.
- If the intensity image is given: the ratio of mean, median, max, min, percentile intensities between cell and nucleus. For these measurements, the nuclear mask is excluded from the cellular intensities.

The napari plugin implements tis measurement logic as in the other measurement widgets.

# Analysis

The python functions take a pandas dataframe as input, the CLI the path to a saved table. The napari plugin widgets operate on a table that was produced by one of the measurement widgets.

## Filter

Filter outliers from the table based on defined criteria. Not yet implemented.

## Threshold-based analysis

This functionality operates on one of the measurement results (from above) and enables the following:
- Separating the objects into N different categories based on N-1 thresholds with respect to one of the measurements, e.g. 3 categories based on the mean intensity.
- A function to suggest the thresholds for the N categories and a given column based on a suitable heuristics.
- If thresholds are not provided for the main function, the heuristics are used.

The napari plugin works as follows:
- The table (output from a measurement tool) can be selected.
- A histogram of a selected column is displayed in the widget. 
- The user can then either enter the number of categories and corresponding thresholds or just the number of categories and derive the thresholds via the heuristics. Categories can be named. It should be possible to modify the suggested thresholds; they should be shown in the histogram. The output should be a new segmentation layer that gives objects the category id and a new column in the intensity table with the category ID and name.

## Clustering analysis

Not yet implemented.

## Classification analysis

Not yet implemented
