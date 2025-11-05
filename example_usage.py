#!/usr/bin/env python3
"""
Example script showing how to use ntop_to_avl programmatically
"""

import numpy as np
from ntop_to_avl import (
    generate_avl_file,
    parse_points_file,
    run_avl
)

# Example 1: Generate AVL file from CSV files
def example_from_csv():
    """Load points from CSV and generate AVL file"""
    
    # Parse point files
    le_points = parse_points_file("leading_edge.csv")
    te_points = parse_points_file("trailing_edge.csv")
    
    # Generate AVL file
    generate_avl_file(
        le_points, te_points,
        "example_wing.avl",
        title="Example Wing from nTop",
        mach=0.0,
        iysym=1,  # Symmetric about Y=0
        nchordwise=8,
        airfoil="NACA 0012"
    )
    
    # Run AVL
    run_avl("example_wing.avl", interactive=True)


# Example 2: Generate AVL file from numpy arrays (programmatic)
def example_from_numpy():
    """Generate AVL file from numpy arrays"""
    
    # Create example points (simple tapered wing)
    n_points = 10
    span = 10.0
    
    # Leading edge points (straight wing)
    le_points = np.zeros((n_points, 3))
    le_points[:, 1] = np.linspace(0, span/2, n_points)  # Y-coordinate (span)
    
    # Trailing edge points (with taper and sweep)
    te_points = np.zeros((n_points, 3))
    te_points[:, 0] = 0.1 + 0.05 * np.linspace(0, 1, n_points)  # X-coordinate (sweep)
    te_points[:, 1] = np.linspace(0, span/2, n_points)  # Y-coordinate (span)
    
    # Chord length tapers from 1.0 to 0.5
    chords = 1.0 - 0.5 * np.linspace(0, 1, n_points)
    
    # Set TE points based on chord length
    for i in range(n_points):
        te_points[i, 0] = le_points[i, 0] + chords[i]
    
    # Generate AVL file
    generate_avl_file(
        le_points, te_points,
        "programmatic_wing.avl",
        title="Programmatically Generated Wing",
        mach=0.0,
        iysym=1,
        nchordwise=10,
        airfoil="NACA 2412"
    )


# Example 3: Custom reference values
def example_custom_refs():
    """Example with custom reference values"""
    
    le_points = np.array([
        [0.0, 0.0, 0.0],
        [0.1, 2.0, 0.1],
        [0.2, 4.0, 0.2],
    ])
    
    te_points = np.array([
        [1.0, 0.0, 0.0],
        [1.0, 2.0, 0.1],
        [0.9, 4.0, 0.2],
    ])
    
    # Custom reference values
    custom_refs = {
        'Sref': 20.0,  # Reference area
        'Cref': 1.0,   # Reference chord
        'Bref': 8.0,   # Reference span
        'Xref': 0.5,   # Reference location
        'Yref': 0.0,
        'Zref': 0.0,
    }
    
    generate_avl_file(
        le_points, te_points,
        "custom_refs_wing.avl",
        title="Wing with Custom References",
        custom_refs=custom_refs
    )


if __name__ == "__main__":
    print("Example 1: Generate from CSV files")
    print("(Uncomment to run)")
    # example_from_csv()
    
    print("\nExample 2: Generate from numpy arrays")
    example_from_numpy()
    print("Generated: programmatic_wing.avl")
    
    print("\nExample 3: Custom reference values")
    example_custom_refs()
    print("Generated: custom_refs_wing.avl")

