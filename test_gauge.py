"""Standalone test script for gauge image processing."""
import sys
import logging
import math
import numpy as np
from io import BytesIO

logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')
_LOGGER = logging.getLogger("test_gauge")

def process_gauge_image(image_bytes: bytes, min_val: float, max_val: float) -> float | None:
    """Process gauge image and return the reading."""
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
            # Handle RGBA images (4 channels)
            if image.shape[2] == 4:
                image = image[:, :, :3]  # Remove alpha channel
            gray = color.rgb2gray(image)
        else:
            gray = image.astype(float) / 255.0 if image.max() > 1 else image
        
        height, width = gray.shape
        _LOGGER.debug("Grayscale image: %dx%d", width, height)
        
        # Try threshold-based detection (more reliable for this case)
        _LOGGER.debug("Using threshold-based detection...")
        result = _detect_gauge_threshold(gray, min_val, max_val, height, width)
        if result is not None:
            _LOGGER.info("Gauge reading (threshold method): %.2f", result)
            return result
        
        _LOGGER.warning("Could not detect gauge reading")
        return None
        
    except Exception as e:
        _LOGGER.error("Error processing gauge image: %s", e, exc_info=True)
        return None


def _detect_gauge_threshold(gray, min_val, max_val, height, width):
    """Detect needle using thresholding - selects the LONGEST needle."""
    from skimage import filters, morphology, measure
    
    # Assume gauge is centered
    center_x, center_y = width // 2, height // 2
    radius_estimate = min(height, width) // 3
    
    # Apply Otsu thresholding
    thresh = filters.threshold_otsu(gray)
    
    best_candidates = []
    
    # Try BOTH directions: needle darker OR lighter than background
    for direction in ['darker', 'lighter']:
        if direction == 'darker':
            binary = gray < thresh
        else:
            binary = gray > thresh
        
        # Clean up
        try:
            binary = morphology.remove_small_objects(binary, min_size=50)
        except Exception:
            pass
        binary = morphology.closing(binary, morphology.disk(3))
        
        # Find connected components
        labels = measure.label(binary)
        regions = measure.regionprops(labels)
        
        if not regions:
            continue
        
        for region in regions:
            cy, cx = region.centroid
            dist_to_center = math.sqrt((cx - center_x)**2 + (cy - center_y)**2)
            
            if region.eccentricity > 0.7 and region.area > 100:
                if dist_to_center < radius_estimate:
                    best_candidates.append({
                        'region': region,
                        'length': region.major_axis_length,
                        'dist_to_center': dist_to_center,
                        'orientation': region.orientation,
                        'direction': direction
                    })
    
    if not best_candidates:
        _LOGGER.debug("No needle candidates found")
        return None
    
    # Log all candidates
    _LOGGER.info("Found %d needle candidate(s):", len(best_candidates))
    for i, cand in enumerate(best_candidates):
        _LOGGER.info("  Candidate %d [%s]: length=%.1f, dist_to_center=%.1f", 
                     i+1, cand['direction'], cand['length'], cand['dist_to_center'])
    
    # Select the LONGEST needle
    best_candidates.sort(key=lambda x: x['length'], reverse=True)
    best_candidate = best_candidates[0]
    
    _LOGGER.info("Selected LONGEST needle [%s]: length=%.1f", 
                 best_candidate['direction'], best_candidate['length'])
    
    angle = best_candidate['orientation']
    return _angle_to_reading(angle, min_val, max_val)


def _angle_to_reading(angle_rad, min_val, max_val):
    """Convert angle to gauge reading."""
    angle_deg = math.degrees(angle_rad)
    needle_angle = (angle_deg + 90) % 360
    
    gauge_start = 225  # 7 o'clock
    gauge_sweep = 270  # Total sweep angle
    
    relative_angle = (needle_angle - gauge_start) % 360
    
    if relative_angle > gauge_sweep:
        alt_angle = (needle_angle + 180 - gauge_start) % 360
        if alt_angle <= gauge_sweep:
            relative_angle = alt_angle
        else:
            relative_angle = min(relative_angle, gauge_sweep)
    
    fraction = relative_angle / gauge_sweep
    reading = min_val + fraction * (max_val - min_val)
    reading = max(min_val, min(max_val, reading))
    
    _LOGGER.debug("Angle: %.1f° -> Relative: %.1f° -> Reading: %.2f", 
                  needle_angle, relative_angle, reading)
    
    return round(reading, 2)


if __name__ == "__main__":
    image_path = sys.argv[1] if len(sys.argv) > 1 else "test_snapshot.jpg"
    min_val = float(sys.argv[2]) if len(sys.argv) > 2 else 0
    max_val = float(sys.argv[3]) if len(sys.argv) > 3 else 2.5
    
    print(f"\n=== Testing gauge image: {image_path} ===")
    print(f"Scale: {min_val} - {max_val} bar\n")
    
    with open(image_path, 'rb') as f:
        image_bytes = f.read()
    
    result = process_gauge_image(image_bytes, min_val, max_val)
    
    if result is not None:
        print(f"\n{'='*40}")
        print(f"  RISULTATO: {result} bar")
        print(f"{'='*40}\n")
    else:
        print("\n=== NESSUN RISULTATO ===\n")
