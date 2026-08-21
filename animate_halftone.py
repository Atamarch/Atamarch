#!/usr/bin/env python3
"""Generate improved holographic animation with adaptive laser."""

import re
import sys
from collections import defaultdict

INPUT_FILE = "halftone_dark.svg"
OUTPUT_FILE = "halftone_dark_animated.svg"

# Timeline (12 seconds total)
PHASE1_DUR = 1.0    # Initial scan: top→bottom, 0→60%
PHASE2_DUR = 1.0    # Verification: bottom→top, 60→100%
PHASE3_DUR = 5.0    # Hold: 100% stable
PHASE4_DUR = 2.0    # Shutdown: 100→60→0%
PHASE5_DUR = 3.0    # Off: 0% invisible
TOTAL_DUR = PHASE1_DUR + PHASE2_DUR + PHASE3_DUR + PHASE4_DUR + PHASE5_DUR  # 12s

# Phase start times
PHASE1_START = 0.0
PHASE2_START = PHASE1_DUR                          # 1.0s
PHASE3_START = PHASE2_START + PHASE2_DUR           # 2.0s
PHASE4_START = PHASE3_START + PHASE3_DUR           # 7.0s
PHASE5_START = PHASE4_START + PHASE4_DUR           # 9.0s

# Scan-line config
SCAN_HEIGHT = 3
SCAN_COLOR = "#22D3EE"
SCAN_PADDING = 8  # padding around object width

# Frame bounds (in transformed coordinates)
FRAME_Y_MIN = 84
FRAME_Y_MAX = 576
FRAME_X_MIN = 36
FRAME_X_MAX = 436


def parse_circles(svg_content):
    """Extract circle elements with cx, cy, r values."""
    pattern = r'<circle\s+cx="([0-9.]+)"\s+cy="([0-9.]+)"\s+r="([0-9.]+)"\s*/>'
    circles = []
    for match in re.finditer(pattern, svg_content):
        cx, cy, r = float(match.group(1)), float(match.group(2)), float(match.group(3))
        circles.append((cx, cy, r))
    return circles


def normalize_y(cy, min_cy, max_cy):
    """Normalize Y position to 0-1 range."""
    if max_cy == min_cy:
        return 0.5
    return (cy - min_cy) / (max_cy - min_cy)


def calculate_laser_bounds(circles, min_cy, max_cy, tolerance=2.0):
    """Pre-calculate laser width at various Y positions."""
    # Group circles by Y position (with tolerance)
    y_groups = defaultdict(list)
    for cx, cy, r in circles:
        # Round to nearest tolerance
        y_key = round(cy / tolerance) * tolerance
        y_groups[y_key].append(cx)

    # Calculate bounds for each Y
    laser_data = []
    for y in sorted(y_groups.keys()):
        cx_values = y_groups[y]
        min_x = min(cx_values)
        max_x = max(cx_values)
        laser_data.append((y, min_x, max_x))

    return laser_data


def interpolate_laser(laser_data, target_y):
    """Interpolate laser bounds for a given Y position."""
    if not laser_data:
        return FRAME_X_MIN + 50, FRAME_X_MAX - 50

    # Find surrounding data points
    if target_y <= laser_data[0][0]:
        return laser_data[0][1], laser_data[0][2]
    if target_y >= laser_data[-1][0]:
        return laser_data[-1][1], laser_data[-1][2]

    for i in range(len(laser_data) - 1):
        y1, x1_min, x1_max = laser_data[i]
        y2, x2_min, x2_max = laser_data[i + 1]
        if y1 <= target_y <= y2:
            t = (target_y - y1) / (y2 - y1) if y2 != y1 else 0
            min_x = x1_min + t * (x2_min - x1_min)
            max_x = x1_max + t * (x2_max - x1_max)
            return min_x, max_x

    return laser_data[-1][1], laser_data[-1][2]


def generate_laser_keyframes(laser_data, min_cy, max_cy, num_samples=50):
    """Generate laser position/width keyframes for the animation."""
    y_positions = []
    x_positions = []
    widths = []

    for i in range(num_samples + 1):
        t = i / num_samples
        # Sample Y positions across the object height
        sample_y = min_cy + t * (max_cy - min_cy)

        # Transform Y to frame coordinates
        frame_y = FRAME_Y_MIN + t * (FRAME_Y_MAX - FRAME_Y_MIN)

        # Get laser bounds at this Y
        min_x, max_x = interpolate_laser(laser_data, sample_y)

        # Add padding
        padding = (max_x - min_x) * 0.08
        laser_x = min_x - padding
        laser_width = (max_x - min_x) + 2 * padding

        y_positions.append(f"{frame_y:.1f}")
        x_positions.append(f"{laser_x:.2f}")
        widths.append(f"{laser_width:.2f}")

    return y_positions, x_positions, widths


def generate_circle_animation(norm_y):
    """Generate opacity and radius animations for a single dot."""
    # Phase 1: Initial scan (0→1s), 0→0.6
    begin_p1 = PHASE1_START + norm_y * PHASE1_DUR

    # Phase 2: Verification (1→2s), 0.6→1.0 (reverse direction)
    begin_p2 = PHASE2_START + (1.0 - norm_y) * PHASE2_DUR

    # Phase 4: Shutdown (7→9s), 1.0→0 (top→bottom like initial)
    begin_p4 = PHASE4_START + norm_y * PHASE4_DUR * 0.5

    # Opacity keyframes:
    # 0 = invisible, 0.6 = detected, 1.0 = verified
    # P1: 0→0.6, P2: 0.6→1.0, P3: 1.0 hold, P4: 1.0→0, P5: 0 hold
    values = "0;0.6;1;1;0;0"
    keyTimes = "0;0.0833;0.1667;0.5833;0.75;1"

    opacity_anim = (
        f'<animate attributeName="opacity" '
        f'values="{values}" '
        f'keyTimes="{keyTimes}" '
        f'dur="{TOTAL_DUR}s" '
        f'begin="{begin_p1}s" '
        f'repeatCount="indefinite"/>'
    )

    # Radius: small → original → original → small
    values_r = "0;1;1;0;0"
    radius_anim = (
        f'<animate attributeName="r" '
        f'values="{values_r}" '
        f'keyTimes="{values_r}" '  # placeholder, will fix below
        f'dur="{TOTAL_DUR}s" '
        f'begin="{begin_p1}s" '
        f'repeatCount="indefinite"/>'
    )

    # Fix radius animation values (multiply by actual radius)
    # Actually we need to include the actual radius value
    radius_anim = (
        f'<animate attributeName="r" '
        f'values="0;1;1;0;0" '
        f'keyTimes="0;0.0833;0.75;0.8333;1" '
        f'dur="{TOTAL_DUR}s" '
        f'begin="{begin_p1}s" '
        f'repeatCount="indefinite"/>'
    )

    return opacity_anim, radius_anim


def generate_laser_svg(y_positions, x_positions, widths):
    """Generate the adaptive laser element with animations."""
    y_values = ";".join(y_positions)
    x_values = ";".join(x_positions)
    w_values = ";".join(widths)

    # KeyTimes: evenly spaced
    num = len(y_positions)
    key_times = ";".join([f"{i/(num-1):.4f}" for i in range(num)])

    # Laser visibility: visible during scanning, hidden during hold/off
    vis_values = "0;1;1;0;0;1;1;0;0"
    vis_keyTimes = "0;0.02;0.0833;0.17;0.5833;0.75;0.8333;0.92;1"

    laser = (
        f'<rect x="0" y="84" width="0" height="{SCAN_HEIGHT}" '
        f'fill="{SCAN_COLOR}" opacity="0" rx="1.5" '
        f'filter="url(#scanGlow)">'
        # Position Y
        f'<animate attributeName="y" '
        f'values="{y_values};{y_values}" '
        f'keyTimes="0;0.0833;0.1667;0.5833;0.75;0.8333;0.92;1" '
        f'keyPoints="0;0.0833;0.1667;0.5833;0.75;0.8333;0.92;1" '
        f'calcMode="linear" '
        f'dur="{TOTAL_DUR}s" repeatCount="indefinite"/>'
        # Width (follows object shape)
        f'<animate attributeName="width" '
        f'values="{w_values};{w_values}" '
        f'keyTimes="0;0.0833;0.1667;0.5833;0.75;0.8333;0.92;1" '
        f'keyPoints="0;0.0833;0.1667;0.5833;0.75;0.8333;0.92;1" '
        f'calcMode="linear" '
        f'dur="{TOTAL_DUR}s" repeatCount="indefinite"/>'
        # X position
        f'<animate attributeName="x" '
        f'values="{x_values};{x_values}" '
        f'keyTimes="0;0.0833;0.1667;0.5833;0.75;0.8333;0.92;1" '
        f'keyPoints="0;0.0833;0.1667;0.5833;0.75;0.8333;0.92;1" '
        f'calcMode="linear" '
        f'dur="{TOTAL_DUR}s" repeatCount="indefinite"/>'
        # Visibility
        f'<animate attributeName="opacity" '
        f'values="{vis_values}" '
        f'keyTimes="{vis_keyTimes}" '
        f'dur="{TOTAL_DUR}s" repeatCount="indefinite"/>'
        f'</rect>'
    )
    return laser


def main():
    # Read input SVG
    with open(INPUT_FILE, 'r') as f:
        svg_content = f.read()

    # Parse circles
    circles = parse_circles(svg_content)
    print(f"Parsed {len(circles)} circles")

    if not circles:
        print("ERROR: No circles found!")
        sys.exit(1)

    # Find Y bounds
    min_cy = min(c[1] for c in circles)
    max_cy = max(c[1] for c in circles)
    print(f"Y range: {min_cy} - {max_cy}")

    # Calculate laser bounds
    laser_data = calculate_laser_bounds(circles, min_cy, max_cy)
    print(f"Laser data points: {len(laser_data)}")

    # Generate laser keyframes
    y_pos, x_pos, widths = generate_laser_keyframes(laser_data, min_cy, max_cy, num_samples=40)
    print(f"Laser keyframes: {len(y_pos)} samples")

    # Build new SVG
    output_parts = []

    # SVG header
    output_parts.append('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
    output_parts.append('<svg width="100mm" height="100mm" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">')

    # Defs with filters
    output_parts.append('<defs>')
    output_parts.append('<filter id="smoothGlow" x="-20%" y="-20%" width="140%" height="140%">')
    output_parts.append('<feGaussianBlur in="SourceGraphic" stdDeviation="0.15"/>')
    output_parts.append('</filter>')
    output_parts.append('<filter id="scanGlow" x="-50%" y="-50%" width="200%" height="200%">')
    output_parts.append('<feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur"/>')
    output_parts.append('<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>')
    output_parts.append('</filter>')
    output_parts.append('</defs>')

    # Background
    output_parts.append('<rect width="100%" height="100%" fill="#0B1120"/>')

    # Halftone group with filter
    output_parts.append('<g filter="url(#smoothGlow)" opacity="0.8">')
    output_parts.append('<g fill="#C9B8FF" transform="translate(62,84) scale(6.4) translate(-23.6,-22.8)">')

    # Generate animated circles
    for i, (cx, cy, r) in enumerate(circles):
        norm_y = normalize_y(cy, min_cy, max_cy)
        opacity_anim, radius_anim = generate_circle_animation(norm_y)

        # Wrap radius animation with actual radius value
        radius_anim_final = radius_anim.replace('values="0;1;1;0;0"', f'values="0;{r};{r};0;0"')

        circle_line = (
            f'<circle cx="{cx}" cy="{cy}" r="{r}">'
            f'{opacity_anim}'
            f'{radius_anim_final}'
            f'</circle>'
        )
        output_parts.append(circle_line)

        if (i + 1) % 1000 == 0:
            print(f"Generated {i + 1}/{len(circles)} circles...")

    output_parts.append('</g>')
    output_parts.append('</g>')

    # Add adaptive laser
    output_parts.append(generate_laser_svg(y_pos, x_pos, widths))

    # Close SVG
    output_parts.append('</svg>')

    # Write output
    output_content = '\n'.join(output_parts)
    with open(OUTPUT_FILE, 'w') as f:
        f.write(output_content)

    print(f"\nGenerated {OUTPUT_FILE}")
    print(f"Total circles: {len(circles)}")
    print(f"Animation duration: {TOTAL_DUR}s")
    print(f"Timeline: P1({PHASE1_DUR}s) + P2({PHASE2_DUR}s) + P3({PHASE3_DUR}s) + P4({PHASE4_DUR}s) + P5({PHASE5_DUR}s)")


if __name__ == "__main__":
    main()
