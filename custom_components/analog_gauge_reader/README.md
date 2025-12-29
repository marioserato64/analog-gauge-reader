# Analog Gauge Reader for Home Assistant

![Version](https://img.shields.io/badge/version-1.0.0-blue) ![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-brightgreen)

An advanced Home Assistant custom integration that uses Computer Vision (OpenCV) to read analog gauges (such as boiler pressure monitoring) from any camera stream and convert them into digital sensors.

## 🌟 Features

-   **Universal Compatibility**: Works with any camera entity in Home Assistant.
-   **Intelligent Processing**: Uses OpenCV to detect gauge needle angle.
-   **Resource Efficient**: Configurable update intervals (1 min / 15 min) to save CPU.
-   **Integrated Alarms**: Built-in logic for multi-stage visual alarms (Warning, Critical).
-   **Easy Calibration**: Simple definition of min/max values.

---

## 🛠️ How it Works

The integration captures snapshots from your existing camera and processes them to extract data.

```mermaid
graph TD
    A[Camera Entity] -->|Snapshot| B(Analog Gauge Reader)
    B -->|OpenCV Processing| C{Analyze Image}
    C -->|Find Circle| D[Detect Gauge]
    C -->|Find Line| E[Detect Needle]
    D & E --> F[Calculate Angle]
    F --> G[Map to Pressure (Bar)]
    G --> H((Sensor Value))
    H --> I{Check Thresholds}
    I -->|Val >= Alarm 1| J[Binary Sensor: Alarm 1 ON]
    I -->|Val >= Alarm 2| K[Binary Sensor: Alarm 2 ON]
```

---

## 🚀 Installation

1.  **Download Source**: Copy the `analog_gauge_reader` folder into your `/config/custom_components/` directory.
    ```text
    /config/
    └── custom_components/
        └── analog_gauge_reader/
            ├── __init__.py
            ├── manifest.json
            ├── ...
    ```
2.  **Restart Home Assistant**: This is crucial to load the required `opencv-python-headless` libraries.
3.  **Add Integration**:
    - Navigate to **Settings** > **Devices & Services**.
    - Click **+ ADD INTEGRATION**.
    - Search for `Analog Gauge Reader`.

---

## ⚙️ Configuration Parameters

| Parameter | Description | Default |
| :--- | :--- | :--- |
| **Camera Entity** | The source camera to read from. | *Required* |
| **Interval** | How often to process the image. | `15 minutes` |
| **Min Reading** | The value at the start of the scale (usually bottom-left). | `0.0` |
| **Max Reading** | The value at the end of the scale (usually bottom-right). | `3.0` |
| **Alarm 1, 2, 3** | Threshold values for triggering binary alarm sensors. | *Optional* |

---

## 📐 Calibration & Troubleshooting

### Best Practices for Camera Setup
*   **Direct View**: The camera should face the gauge as directly as possible (90° angle) to avoid parallax error.
*   **Lighting**: Ensure consistent lighting. Avoid direct glare or reflections on the glass face of the gauge.
*   **Focus**: The needle must be clearly visible and sharp.

### Common Issues

> **Problem**: Sensor shows `Unknown` or `Unavailable`.
>
> **Solution**:
> 1. Check the logs (`Settings > System > Logs`) for "Analog Gauge Reader".
> 2. Ensure the camera entity is streaming correctly.
> 3. Verify that the gauge takes up a significant portion of the image.

> **Problem**: The value is inaccurate.
>
> **Solution**:
> The algorithm assumes a standard ~270° gauge sweep starting from the bottom-left. If your gauge has a different layout (e.g., 180° sweep), the readings will be scaled incorrectly.

---

## 🔧 Expert Details

**OpenCV Logic:**
The system uses `HoughCircleTransform` to find the gauge face and `HoughLineTransformP` (Probabilistic) to find the strongest line originating near the center of that circle.

**Dependencies:**
- `opencv-python-headless`
- `numpy`

These are installed automatically by Home Assistant upon the first run.
