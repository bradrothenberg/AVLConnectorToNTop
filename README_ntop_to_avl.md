# nTop to AVL Converter

This Python script converts leading edge and trailing edge points exported from nTop into AVL format for aerodynamic analysis.

## Features

- Reads CSV files with leading edge (LE) and trailing edge (TE) points from nTop
- Automatically calculates chord lengths, reference values (Sref, Cref, Bref)
- Generates valid AVL input files (.avl format)
- Runs AVL.exe for interactive or batch analysis
- Flexible CSV input format support

## Requirements

- Python 3.6+
- numpy (`pip install numpy`)
- AVL executable (should be in `binw32/avl3.51-32.exe`)

## Installation

1. Install numpy:
```bash
pip install numpy
```

2. Make sure AVL.exe is available (the script will auto-detect it in common locations)

## Usage

### Basic Usage

```bash
python ntop_to_avl.py --le leading_edge.csv --te trailing_edge.csv
```

This will:
1. Read the LE and TE point files
2. Generate `ntop_geometry.avl`
3. Launch AVL interactively

### Advanced Options

```bash
# Specify output filename
python ntop_to_avl.py --le le.csv --te te.csv --output wing.avl

# Set Mach number
python ntop_to_avl.py --le le.csv --te te.csv --mach 0.3

# Run in batch mode (non-interactive)
python ntop_to_avl.py --le le.csv --te te.csv --no-interactive

# Generate AVL file without running
python ntop_to_avl.py --le le.csv --te te.csv --no-run

# Use custom airfoil
python ntop_to_avl.py --le le.csv --te te.csv --airfoil "NACA 2412"

# Specify AVL executable path
python ntop_to_avl.py --le le.csv --te te.csv --avl-exe "C:\path\to\avl.exe"
```

## Input File Format

### CSV Format

The CSV files should contain X, Y, Z coordinates for each point. The script supports flexible column naming:

**Supported column names (case insensitive):**
- `X`, `Y`, `Z`
- `Xle`, `Yle`, `Zle` (or `X_le`, `Y_le`, `Z_le`)
- `Leading_X`, `Leading_Y`, `Leading_Z`
- Or any first three columns will be used as X, Y, Z

**Example CSV format:**

```csv
X,Y,Z
0.0,0.0,0.0
0.1,0.5,0.02
0.2,1.0,0.05
0.3,1.5,0.08
```

Or:

```csv
Leading_X,Leading_Y,Leading_Z
0.0,0.0,0.0
0.1,0.5,0.02
0.2,1.0,0.05
```

**Important:**
- Points should be ordered spanwise (typically from root to tip)
- Both LE and TE files should have the same number of points
- Points should be corresponding (i.e., row 1 in LE file corresponds to row 1 in TE file)

### Exporting from nTop

When exporting points from nTop:

1. Create a selection of leading edge points
2. Export as CSV (ensure coordinates are included)
3. Repeat for trailing edge points
4. Ensure points are ordered consistently (same spanwise order)

## Output

The script generates an AVL input file with:

- **Automatic calculations:**
  - Chord length for each section (distance from LE to TE)
  - Reference area (Sref) - calculated using trapezoidal integration
  - Reference chord (Cref) - mean chord
  - Reference span (Bref) - calculated span
  - Local twist/angle of attack (Ainc) - calculated from chord line orientation

- **Default settings:**
  - Mach number: 0.0 (incompressible)
  - Y-symmetry: Enabled (iysym=1) - assumes half-model
  - Chordwise vortices: 8
  - Airfoil: NACA 0012 (symmetric)

## Running AVL Analysis

### Interactive Mode (Default)

When you run the script, AVL will launch interactively. Common commands:

- `OPER` - Enter operating point menu
- `G` - Plot geometry
- `A A 1` - Set angle of attack to 1 degree
- `X` - Execute calculation
- `T` - Show Trefftz plane plot (lift distribution)
- `Q` - Quit

### Batch Mode

Use `--no-interactive` to run without GUI:

```bash
python ntop_to_avl.py --le le.csv --te te.csv --no-interactive
```

## Example Workflow

1. **Export from nTop:**
   ```
   - Select leading edge points → Export to le_points.csv
   - Select trailing edge points → Export to te_points.csv
   ```

2. **Run conversion:**
   ```bash
   python ntop_to_avl.py --le le_points.csv --te te_points.csv --output my_wing.avl
   ```

3. **Analyze in AVL:**
   - Script launches AVL automatically
   - Or manually: `avl my_wing`

4. **Customize analysis:**
   - Edit the generated `.avl` file if needed
   - Adjust reference values
   - Change vortex density
   - Add controls or design variables

## Troubleshooting

**"Could not find AVL.exe"**
- Specify the path manually: `--avl-exe "path\to\avl.exe"`
- Or ensure AVL is in `binw32/` relative to the script

**"No valid points found in file"**
- Check CSV format - ensure X, Y, Z columns exist
- Check for headers in CSV file
- Verify file encoding (UTF-8)

**"Unequal number of points"**
- Ensure LE and TE files have same number of points
- Check that points are aligned (row 1 LE = row 1 TE)

**AVL errors about geometry**
- Check that points are in correct order (spanwise)
- Verify that chord lengths are reasonable
- Ensure no zero-length chords

## Tips

- **Symmetry:** If modeling a full wing, set `--iysym 0` to disable symmetry
- **Vortex density:** Increase `--nchordwise` for higher resolution (e.g., 12-16)
- **Airfoils:** Use `AFILE` format for custom airfoils: `--airfoil "my_airfoil.dat"`
- **Reference values:** The script calculates these automatically, but you can edit the `.avl` file manually if needed

## License

This script is provided as-is for use with AVL (Athena Vortex Lattice) code by Mark Drela and Harold Youngren.

