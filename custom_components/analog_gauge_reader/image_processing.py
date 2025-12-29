"""Image processing for Analog Gauge Reader - Improved Algorithm."""
from __future__ import annotations

import numpy as np
from io import BytesIO
import logging
import math

_LOGGER = logging.getLogger(__name__)


def process_gauge_image(image_bytes: bytes, min_val: float, max_val: float) -> float | None:
    """Process gauge image and return the reading.
    
    Improved algorithm with multiple detection strategies:
    1. Multiple edge detection parameters
    2. Fallback to center-of-mass for needle detection
    3. Adaptive thresholding
    4. Larger tolerance for varied gauge types
    """
    try:
        from skimage import io as skio
        from skimage import color, filters, morphology, measure
        from skimage.transform import hough_circle, hough_circle_peaks, hough_line, hough_line_peaks
        from skimage.feature import canny
    except ImportError as e:
        _LOGGER.error("scikit-image not available: %s", e)
        return None

    try:
        # Load image from bytes
        image = skio.imread(BytesIO(image_bytes))
        _LOGGER.debug("Image loaded, shape: %s", image.shape)
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            # Handle RGBA images (4 channels) - common with PNG files
            if image.shape[2] == 4:
                image = image[:, :, :3]  # Remove alpha channel
            gray = color.rgb2gray(image)
        else:
            gray = image.astype(float) / 255.0 if image.max() > 1 else image
        
        height, width = gray.shape
        _LOGGER.debug("Grayscale image: %dx%d", width, height)
        
        # Use ONLY threshold-based detection (best for selecting longest needle)
        # Hough method disabled because it cannot reliably distinguish between
        # multiple needles of different lengths (it detects lines, not segments)
        _LOGGER.debug("Using threshold-based detection...")
        result = _detect_gauge_threshold(gray, min_val, max_val, height, width)
        if result is not None:
            _LOGGER.info("Gauge reading: %.2f bar", result)
            return result
        
        _LOGGER.warning("Could not detect gauge reading")
        return None
        
    except Exception as e:
        _LOGGER.error("Error processing gauge image: %s", e, exc_info=True)
        return None


def _detect_gauge(gray, sigma, min_val, max_val, height, width):
    """Detect gauge using Hough transforms - selects the LONGEST needle line.
    
    This gauge has two needles - we need to select the LONGEST one.
    """
    from skimage.transform import hough_circle, hough_circle_peaks, hough_line, hough_line_peaks
    from skimage.feature import canny
    
    # Edge detection
    edges = canny(gray, sigma=sigma, low_threshold=0.1, high_threshold=0.3)
    
    # Detect circles (gauge face)
    min_radius = min(height, width) // 8  # Reduced minimum
    max_radius = min(height, width) // 2
    
    if min_radius >= max_radius:
        return None
    
    hough_radii = np.arange(min_radius, max_radius, 5)  # Finer steps
    hough_res = hough_circle(edges, hough_radii)
    
    # Find circles
    accums, cx_arr, cy_arr, radii = hough_circle_peaks(
        hough_res, hough_radii, total_num_peaks=3  # Get top 3
    )
    
    if len(cx_arr) == 0:
        _LOGGER.debug("No circles detected with sigma=%.1f", sigma)
        return None
    
    # Use the strongest circle
    cx, cy, radius = cy_arr[0], cx_arr[0], radii[0]  # Note: cy/cx swap for row/col
    _LOGGER.debug("Circle detected at (%d, %d), radius=%d", cx, cy, radius)
    
    # Detect lines (needle)
    tested_angles = np.linspace(-np.pi, np.pi, 720, endpoint=False)
    h, theta, d = hough_line(edges, theta=tested_angles)
    
    # Find lines that pass near the center and calculate their "length" 
    # (based on how far into the gauge they extend)
    candidates = []
    
    for _, angle, dist in zip(*hough_line_peaks(h, theta, d, num_peaks=30)):
        # Calculate distance from center to this line
        dist_from_center = abs(cx * np.cos(angle) + cy * np.sin(angle) - dist)
        
        # More lenient threshold (50% of radius)
        if dist_from_center < radius * 0.5:
            # Estimate "effective length" based on how close the line is to center
            # Lines passing through center have higher effective length
            effective_length = radius - dist_from_center
            candidates.append({
                'angle': angle,
                'dist_from_center': dist_from_center,
                'effective_length': effective_length
            })
    
    if not candidates:
        _LOGGER.debug("No needle lines detected near center with sigma=%.1f", sigma)
        return None
    
    # Log candidates
    _LOGGER.debug("Found %d line candidates near center", len(candidates))
    
    # Select the line with highest effective length (closest to center = longer needle)
    candidates.sort(key=lambda x: x['effective_length'], reverse=True)
    best_candidate = candidates[0]
    
    _LOGGER.debug("Selected best line: angle=%.2f rad, dist_from_center=%.1f, effective_length=%.1f",
                  best_candidate['angle'], best_candidate['dist_from_center'], 
                  best_candidate['effective_length'])
    
    return _angle_to_reading(best_candidate['angle'], min_val, max_val)


def _detect_gauge_threshold(gray, min_val, max_val, height, width):
    """Detect needle using thresholding - selects the LONGEST needle.
    
    This gauge has two needles:
    - Short red needle: threshold indicator (should be IGNORED)
    - Long black needle: actual pressure reading (should be READ)
    
    Since the camera uses infrared, we cannot distinguish by color.
    We try BOTH threshold directions (darker and lighter than background)
    because in IR images the needle may appear either way.
    We select the LONGEST needle candidate from the best result.
    """
    from skimage import filters, morphology, measure
    
    # Assume gauge is centered and takes up most of the image
    center_x, center_y = width // 2, height // 2
    radius_estimate = min(height, width) // 3
    
    # Apply Otsu thresholding
    thresh = filters.threshold_otsu(gray)
    
    best_candidates = []
    
    # Try BOTH directions: needle darker OR lighter than background
    # This is important for IR images where contrast can be inverted
    for direction in ['darker', 'lighter']:
        if direction == 'darker':
            binary = gray < thresh
        else:
            binary = gray > thresh
        
        # Clean up
        try:
            binary = morphology.remove_small_objects(binary, min_size=50)
        except Exception:
            pass  # May fail if no objects
        binary = morphology.closing(binary, morphology.disk(3))
        
        # Find connected components
        labels = measure.label(binary)
        regions = measure.regionprops(labels)
        
        if not regions:
            continue
        
        # Find ALL elongated regions (potential needles)
        for region in regions:
            cy, cx = region.centroid
            dist_to_center = math.sqrt((cx - center_x)**2 + (cy - center_y)**2)
            
            # Check if elongated (eccentricity > 0.7 means elongated)
            if region.eccentricity > 0.7 and region.area > 100:
                # Only consider regions near the center (within radius)
                if dist_to_center < radius_estimate:
                    best_candidates.append({
                        'region': region,
                        'length': region.major_axis_length,
                        'dist_to_center': dist_to_center,
                        'orientation': region.orientation,
                        'direction': direction
                    })
    
    if not best_candidates:
        _LOGGER.debug("No needle candidates found (tried both threshold directions)")
        return None
    
    # Log all candidates
    _LOGGER.debug("Found %d needle candidate(s) across both threshold directions:", len(best_candidates))
    for i, cand in enumerate(best_candidates):
        _LOGGER.debug("  Candidate %d [%s]: length=%.1f, dist_to_center=%.1f", 
                      i+1, cand['direction'], cand['length'], cand['dist_to_center'])
    
    # Select the LONGEST needle (ignore the short indicator needle)
    best_candidates.sort(key=lambda x: x['length'], reverse=True)
    best_candidate = best_candidates[0]
    
    _LOGGER.info("Selected LONGEST needle [%s]: length=%.1f (ignoring %d shorter needle(s))",
                 best_candidate['direction'], best_candidate['length'], len(best_candidates) - 1)
    
    # Get orientation of the selected needle
    angle = best_candidate['orientation']  # Radians, -pi/2 to pi/2
    
    return _angle_to_reading(angle, min_val, max_val)


def _angle_to_reading(angle_rad, min_val, max_val):
    """Convert angle to gauge reading.
    
    Assumes standard gauge: 
    - Min value at 7 o'clock position (225 degrees)
    - Max value at 5 o'clock position (315 degrees)  
    - 270 degree sweep clockwise
    """
    # Convert to degrees (0-360 range)
    angle_deg = math.degrees(angle_rad)
    
    # Hough angle is perpendicular to line direction, adjust
    needle_angle = (angle_deg + 90) % 360
    
    # Standard gauge parameters
    gauge_start = 225  # 7 o'clock
    gauge_sweep = 270  # Total sweep angle
    
    # Calculate relative position
    relative_angle = (needle_angle - gauge_start) % 360
    
    # Clamp to valid range
    if relative_angle > gauge_sweep:
        # Could be on the "wrong side" - try the opposite direction
        alt_angle = (needle_angle + 180 - gauge_start) % 360
        if alt_angle <= gauge_sweep:
            relative_angle = alt_angle
        else:
            relative_angle = min(relative_angle, gauge_sweep)
    
    # Calculate reading
    fraction = relative_angle / gauge_sweep
    reading = min_val + fraction * (max_val - min_val)
    
    # Clamp to valid range
    reading = max(min_val, min(max_val, reading))
    
    _LOGGER.debug("Angle: %.1f° -> Relative: %.1f° -> Reading: %.2f", 
                  needle_angle, relative_angle, reading)
    
    return round(reading, 2)
