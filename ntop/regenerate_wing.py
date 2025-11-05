#!/usr/bin/env python3
"""
Script to regenerate wing_from_ntop.avl from LEpts.csv and TEpts.csv point files.
Run this script from the ntop/ directory:
    python regenerate_wing.py
"""
import csv
import numpy as np

# Read LE points
le_pts = []
with open('LEpts.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    for row in reader:
        if len(row) >= 3:
            le_pts.append([float(row[0]), float(row[1]), float(row[2])])

# Read TE points
te_pts = []
with open('TEpts.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    for row in reader:
        if len(row) >= 3:
            te_pts.append([float(row[0]), float(row[1]), float(row[2])])

# Convert inches to feet
le = np.array(le_pts) / 12.0
te = np.array(te_pts) / 12.0

# Calculate chords
chords = np.linalg.norm(te - le, axis=1)

# Calculate span (Y distance)
y_coords = le[:, 1]
span = np.max(y_coords) - np.min(y_coords)

# Calculate area (trapezoidal integration)
area = 0.0
for i in range(len(le) - 1):
    dy = abs(y_coords[i+1] - y_coords[i])
    area += (chords[i] + chords[i+1]) / 2.0 * dy

# Calculate MAC (area-weighted mean chord)
mac_sum = 0.0
for i in range(len(le) - 1):
    dy = abs(y_coords[i+1] - y_coords[i])
    mac_sum += (chords[i]**2 + chords[i+1]**2) / 2.0 * dy
mac = mac_sum / area if area > 0 else np.mean(chords)

# Calculate reference point (centroid of LE points)
x_ref = np.mean(le[:, 0])
y_ref = np.mean(le[:, 1])
z_ref = np.mean(le[:, 2])

# Force no symmetry - use all points for full wing
# Check if symmetric (Y coordinates symmetric about 0) - for info only
is_symmetric = np.allclose(y_coords, -y_coords[::-1]) and len(le) > 1

# Generate AVL file
with open('wing_from_ntop.avl', 'w') as f:
    f.write("!***************************************\n")
    f.write("!AVL input file generated from nTop geometry\n")
    f.write("!***************************************\n")
    f.write("nTop Geometry\n")
    f.write("!Mach\n")
    f.write(" 0.000\n")
    f.write("!IYsym   IZsym   Zsym\n")
    # Always use all points - no symmetry
    f.write(" 0       0       0.000\n")
    section_indices = list(range(len(le)))
    
    f.write(f"!Sref    Cref    Bref\n")
    f.write(f"{area:.6f}     {mac:.6f}     {span:.6f}\n")
    f.write(f"!Xref    Yref    Zref\n")
    f.write(f"{x_ref:.6f}     {y_ref:.6f}     {z_ref:.6f}\n")
    f.write("\n")
    f.write("SURFACE\n")
    f.write("WING\n")
    f.write("!Nchordwise  Cspace\n")
    f.write("8            1.0\n")
    f.write("\n")
    
    # Write sections
    for i, idx in enumerate(section_indices):
        f.write("SECTION\n")
        f.write("!Xle    Yle    Zle     Chord   Ainc  Nspanwise  Sspace\n")
        # Calculate number of spanwise panels between sections
        # Adjust these values to control spanwise panel density:
        # - min_panels: minimum panels between sections (default: 3)
        # - panels_per_ft: multiplier for distance-based panels (default: 2)
        min_panels = 3
        panels_per_ft = 2
        if i < len(section_indices) - 1:
            next_idx = section_indices[i+1]
            dy = abs(y_coords[next_idx] - y_coords[idx])
            nspan = max(min_panels, int(dy * panels_per_ft))  # More panels where sections are farther apart
        else:
            nspan = 0  # Last section
        f.write(f"{le[idx,0]:.6f}    {le[idx,1]:.6f}    {le[idx,2]:.6f}    {chords[idx]:.6f}   0.000   {nspan}          1.000\n")
        f.write("NACA\n")
        f.write("2412\n")
        f.write("\n")
    
    f.write("END\n")

print(f"Generated AVL file with {len(section_indices)} sections (full wing, no symmetry)")
print(f"Reference values: Sref={area:.6f} ft², Cref={mac:.6f} ft, Bref={span:.6f} ft")
