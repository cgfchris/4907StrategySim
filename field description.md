# FRC Simulator: Field Coordinate System 📏

This document describes the coordinate system, units, and orientations used in the simulator.

## 📍 The Origin (0,0)
The origin **(0,0)** is located at the **TOP-LEFT** corner of the field carpet.

---

## 📏 Field Layout (Inches)
The field uses **inches** for all distance measurements.

### X-Axis (Width): 0 to ~651"
*   **0"**: Red Alliance Wall
*   **181.5"**: Red Alliance Scoring Line (The Hub/Divider)
*   **325.6"**: Midfield (Center of the Neutral Zone)
*   **469.7"**: Blue Alliance Scoring Line
*   **651.2"**: Blue Alliance Wall

### Y-Axis (Length): 0 to ~317"
*   **0"**: Top side boundary
*   **158.8"**: Centerline (Middle of the field height)
*   **317.7"**: Bottom side boundary

---

## 🔄 Rotation (Degrees)
Rotation follows a clockwise convention from the right-hand horizontal.

*   **0°**: Faces **RIGHT** (Towards the Blue Alliance)
*   **90°**: Faces **DOWN**
*   **180°**: Faces **LEFT** (Towards the Red Alliance)
*   **270°**: Faces **UP** (Screen North)

---

## 🔴 Example Coordinates for Red Agent

### Centered on Red Alliance Wall
*   `start_x`: **20.0** (Just inside the wall)
*   `start_y`: **158.8** (Middle of the field height)

### Positioned at the Scoring Line
*   `target_x`: **150.0** (Just before the Red Hub)
*   `target_y`: **158.8**

---

## 🤖 Autonomous Routine Rotation (`rot`)

When specifying `"rot"` in a step within an autonomous JSON file:

- **In a Target Step** (has `target_x/y`): `rot` is treated as a **Target Angle** (0-360°). The robot will automatically rotate to face this heading while driving.
- **In a Timed Step**: 
  - If `abs(rot) > 1.1`, it is treated as a **Target Angle**.
  - If `abs(rot) <= 1.1`, it is treated as **Rotation Power** (-1.0 to 1.0).