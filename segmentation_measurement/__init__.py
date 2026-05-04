"""
.. include:: ../doc/start.md
.. include:: ../doc/napari.md
.. include:: ../doc/cli.md
"""

from segmentation_measurement.postprocessing import (
    apply_watershed,
    compute_ring_mask,
    filter_small_segments,
    remove_small_holes,
)
from segmentation_measurement.intensity import measure_intensities
from segmentation_measurement.morphology import measure_morphology
from segmentation_measurement.cell_nucleus import measure_cell_nucleus
from segmentation_measurement.analysis import (
    apply_classifier,
    categorize_by_threshold,
    cluster_measurements,
    suggest_thresholds,
    train_classifier,
)

__all__ = [
    "filter_small_segments",
    "remove_small_holes",
    "compute_ring_mask",
    "apply_watershed",
    "measure_intensities",
    "measure_morphology",
    "measure_cell_nucleus",
    "suggest_thresholds",
    "categorize_by_threshold",
    "cluster_measurements",
    "train_classifier",
    "apply_classifier",
]

__version__ = "0.1.0"
