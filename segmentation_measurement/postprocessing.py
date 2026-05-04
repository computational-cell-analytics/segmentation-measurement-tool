"""Post-processing utilities for instance segmentations."""

from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.ndimage import binary_dilation
from skimage.morphology import remove_small_holes as _remove_small_holes


def filter_small_segments(segmentation: np.ndarray, min_size: int) -> np.ndarray:
    """Filter out segments below a minimum size threshold.

    Segments with fewer pixels/voxels than ``min_size`` are set to zero
    (background label).

    Args:
        segmentation (np.ndarray): Integer-valued label array where 0 is
            background and each positive integer represents a distinct segment.
            Supports arbitrary dimensionality.
        min_size (int): Minimum segment size in pixels/voxels. Segments
            strictly smaller than this threshold are removed.

    Returns:
        np.ndarray: Label array with small segments set to zero, same shape
            and dtype as input.
    """
    result = segmentation.copy()
    label_ids, counts = np.unique(segmentation, return_counts=True)
    for label_id, count in zip(label_ids, counts):
        if label_id == 0:
            continue
        if count < min_size:
            result[segmentation == label_id] = 0
    return result


def remove_small_holes(segmentation: np.ndarray, max_hole_size: int) -> np.ndarray:
    """Remove small holes from segments.

    For each segment, enclosed background regions (holes) smaller than or
    equal to ``max_hole_size`` pixels/voxels are filled with the segment's
    label. Pixels belonging to other segments are never overwritten.

    Args:
        segmentation (np.ndarray): Integer-valued label array where 0 is
            background and each positive integer represents a distinct segment.
            Supports arbitrary dimensionality.
        max_hole_size (int): Maximum hole size in pixels/voxels. Holes smaller
            than or equal to this threshold are filled.

    Returns:
        np.ndarray: Label array with small holes filled, same shape and dtype
            as input.
    """
    result = segmentation.copy()
    for label_id in np.unique(segmentation):
        if label_id == 0:
            continue
        binary_mask = segmentation == label_id
        filled_mask = _remove_small_holes(binary_mask, area_threshold=max_hole_size)
        new_pixels = filled_mask & ~binary_mask
        # Only fill background pixels; do not overwrite other segments.
        new_pixels &= (segmentation == 0)
        result[new_pixels] = label_id
    return result


def compute_ring_mask(
    segmentation: np.ndarray, ring_width: int, keep_original: bool = True
) -> np.ndarray:
    """Compute the ring mask around each segment.

    For each segment, a ring of specified width is computed by dilating the
    segment mask by ``ring_width`` iterations and subtracting the original
    mask. Ring pixels are only placed on background pixels of the original
    segmentation. If rings from different segments overlap, the segment with
    the smaller label ID takes precedence.

    This is useful for creating pseudo-cytosol masks around segmented nuclei.

    Args:
        segmentation (np.ndarray): Integer-valued label array where 0 is
            background and each positive integer represents a distinct segment.
            Supports arbitrary dimensionality.
        ring_width (int): Width of the ring in pixels/voxels.
        keep_original (bool): If ``True`` (default), original segment pixels
            are retained in the output alongside the ring pixels. If ``False``,
            only the ring pixels are labeled and original segment pixels are
            set to zero (background).

    Returns:
        np.ndarray: Label array containing the ring regions and, when
            ``keep_original`` is ``True``, also the original segment pixels.
            Same shape and dtype as input.
    """
    result = segmentation.copy() if keep_original else np.zeros_like(segmentation)
    for label_id in np.unique(segmentation):
        if label_id == 0:
            continue
        binary_mask = segmentation == label_id
        dilated = binary_dilation(binary_mask, iterations=ring_width)
        ring = dilated & ~binary_mask
        # Only place ring on background pixels; smaller label IDs take precedence
        # over later rings via the result == 0 guard.
        ring &= (segmentation == 0) & (result == 0)
        result[ring] = label_id
    return result


def apply_watershed(
    segmentation: np.ndarray,
    heatmap: np.ndarray,
    mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Refine a segmentation using the watershed algorithm.

    Uses the input segmentation as seed markers and ``heatmap`` as the
    topographic landscape for ``skimage.segmentation.watershed``.  The
    watershed algorithm floods uphill from each marker, so pixels with
    *low* heatmap values are claimed first.  For heatmaps where high values
    indicate cell interiors or distance-to-boundary (e.g. a distance
    transform), pass the negated heatmap so that high-confidence regions are
    flooded first.

    Args:
        segmentation (np.ndarray): Integer-valued label array used as seed
            markers.  0 is background; each positive integer is a distinct
            seed.  Supports arbitrary dimensionality.
        heatmap (np.ndarray): Landscape image of the same spatial shape as
            ``segmentation``.  Low values are flooded before high values.
        mask (Optional[np.ndarray]): Boolean or binary array of the same
            shape as ``segmentation``.  Only pixels where ``mask`` is
            ``True`` are processed; all other pixels are set to 0 in the
            output.  If ``None`` (default), all pixels are processed.

    Returns:
        np.ndarray: Refined label array, same shape and dtype as
            ``segmentation``.
    """
    from skimage.segmentation import watershed
    result = watershed(heatmap, markers=segmentation, mask=mask)
    return result.astype(segmentation.dtype)
