"""Image processing logic for Analog Gauge Reader."""
import logging
import cv2
import numpy as np

_LOGGER = logging.getLogger(__name__)

def avg_circles(circles, b):
    avg_x=0
    avg_y=0
    avg_r=0
    for i in range(b):
        avg_x = avg_x + circles[0][i][0]
        avg_y = avg_y + circles[0][i][1]
        avg_r = avg_r + circles[0][i][2]
    avg_x = int(avg_x/(b))
    avg_y = int(avg_y/(b))
    avg_r = int(avg_r/(b))
    return avg_x, avg_y, avg_r

def dist_2_pts(x1, y1, x2, y2):
    return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

def process_gauge_image(image_bytes, min_val, max_val):
    """Process the image bytes and return a float value."""
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Could not decode image")

        height, width = img.shape[:2]
        
        # 1. Find the gauge (Circle detection)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Apply Gaussian Blur to reduce noise
        gray_blurred = cv2.GaussianBlur(gray, (9, 9), 0)
        
        # Hough Circle Transform
        # Use simple heuristics regarding image size to estimate radius range
        min_r = int(min(height, width) * 0.1)
        max_r = int(min(height, width) * 0.5)
        
        circles = cv2.HoughCircles(
            gray_blurred, 
            cv2.HOUGH_GRADIENT, 
            dp=1.2, 
            minDist=width/2, # Assume only one gauge
            param1=100,
            param2=50, # Sensitivity
            minRadius=min_r, 
            maxRadius=max_r
        )

        if circles is None:
            _LOGGER.warning("No gauge circle found")
            return None # Or raise error

        circles = np.round(circles[0, :]).astype("int")
        x, y, r = circles[0] # Take the strongest circle

        # 2. Find the needle (Line detection)
        # Can extract the ROI of the circle to simplify
        # For simplicity, we filter lines in the whole image that pass near center (x,y)
        
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Probabilistic Hough Line Transform
        # thresholds need tuning
        min_line_length = int(r * 0.5)
        max_line_gap = int(r * 0.1)
        
        lines = cv2.HoughLinesP(
            edges, 
            rho=1, 
            theta=np.pi/180, 
            threshold=50, 
            minLineLength=min_line_length, 
            maxLineGap=max_line_gap
        )
        
        if lines is None:
             _LOGGER.warning("No needle found")
             return None

        # Filter lines: must be within the circle and point towards center
        # We look for a line where one end is close to center (distance < r*0.2)
        # and length is significant.
        
        best_line = None
        longest_dist = 0
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Check distance to center
            d1 = dist_2_pts(x, y, x1, y1)
            d2 = dist_2_pts(x, y, x2, y2)
            
            # Use the point furthest from center as the "tip"
            # and the point closest as "base"
            if d1 > d2:
                tip_x, tip_y = x1, y1
                base_dist = d2
            else:
                tip_x, tip_y = x2, y2
                base_dist = d1
                
            # Needle base should be somewhat close to center
            if base_dist < r * 0.3:
                # This could be the needle
                # Calculate length
                length = dist_2_pts(x1, y1, x2, y2)
                if length > longest_dist:
                    longest_dist = length
                    best_line = (tip_x, tip_y)

        if best_line is None:
            _LOGGER.warning("No valid needle line found")
            return None

        tip_x, tip_y = best_line

        # 3. Calculate Angle
        # atan2 returns -pi to +pi. 
        # In image coords, y is positive down.
        # 0 is Right (3 o'clock), -pi/2 is Up (12 o'clock), pi/2 is Down (6 o'clock), +/-pi is Left (9 o'clock)
        
        angle_rad = np.arctan2(tip_y - y, tip_x - x)
        angle_deg = np.degrees(angle_rad)
        
        # Normalize to 0-360 starting from 6 o'clock clockwise? 
        # Standard gauge usually goes from say 135 deg (bottom left) to 45 deg (bottom right) clockwise
        # or -135 to -45.
        # Let's assume standard behavior:
        # 0 value is at some start_angle
        # Max value is at some end_angle
        # Since we don't not have calibration, I will assume a standard 270 degree gauge.
        # 0 val at +135 degrees (South West)
        # Max val at +45 degrees (South East) going clockwise
        
        # Convert atan2 (Right=0, clockwise positive) to standard 0-360
        # In openCV/image:
        # Right (0) -> 0
        # Down (90) -> 90
        # Left (180/-180) -> 180
        # Up (-90) -> 270
        
        if angle_deg < 0:
            angle_deg += 360
            
        # Ref: https://github.com/intel-iot-devkit/python-cv-apps/blob/master/analog-gauge-reader/analog_gauge_reader.py
        # They use a separation method.
        
        # HEURISTIC:
        # Lets assume 0 bar is at 135 degrees (bottom-left)
        # 3 bar is at 45 degrees (bottom-right)
        # Wait, if we go clockwise from bottom-left:
        # Bottom-Left (135) -> Left (180) -> Top (270) -> Right (0/360) -> Bottom-Right (45)
        # That's about 270 degrees span.
        
        # This mapping is extremely fragile without user input.
        # But for v1 let's hardcode a common span.
        
        # Map:
        # 135 deg to 405 deg (45 + 360)?
        # Let's define the "zero" angle.
        
        start_angle = 135 # degrees
        end_angle = 45 # degrees
        
        # To make math easy, let's calculate "angle from start" clockwise
        
        current_angle = angle_deg
        
        # If start is 135, and we go clockwise...
        # 135 -> 180 (diff 45)
        # 180 -> 270 (diff 90)
        # 270 -> 360 (diff 90)
        # 0 -> 45 (diff 45)
        # Total span = 270
        
        # Clean up angle to be relative to start_angle
        # If angle < start_angle (e.g. 45), it might be in the next cycle
        # We want everything in [start_angle, start_angle + span]
        
        # Case 1: angle = 180. 180-135 = 45.
        # Case 2: angle = 0. 0 + 360 - 135 = 225.
        # Case 3: angle = 45. 45 + 360 - 135 = 270.
        
        if current_angle < start_angle:
            current_angle += 360
            
        val_angle = current_angle - start_angle
        
        # Clip if outside expected range (with some buffer)
        total_angle_span = 270 # typical
        
        if val_angle < 0: val_angle = 0
        if val_angle > total_angle_span: val_angle = total_angle_span
        
        # Map to value
        val_per_degree = (max_val - min_val) / total_angle_span
        reading = min_val + (val_angle * val_per_degree)
        
        return round(reading, 2)

    except Exception as e:
        _LOGGER.error(f"Error processing gauge image: {e}")
        return None
