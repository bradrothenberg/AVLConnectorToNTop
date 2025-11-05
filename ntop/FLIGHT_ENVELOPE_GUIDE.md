# Flight Envelope Simulation and Trefftz Plot Guide

## Overview
This guide explains how to run a flight envelope simulation across multiple angles of attack and view Trefftz plane plots in AVL.

## Files Created
- `wing_from_ntop.run` - Run case file with 21 cases (alpha from -5° to +15°)
- `wing_from_ntop.commands` - Automated command script for AVL
- `create_flight_envelope.py` - Script to generate custom run case files

## Method 1: Interactive AVL (Recommended)

### Step 1: Start AVL
```powershell
cd ntop
avl wing_from_ntop
```

### Step 2: Load Run Cases
In AVL, type:
```
CASE
wing_from_ntop.run
```

### Step 3: Enter OPER Menu
```
OPER
```

### Step 4: Execute All Cases
To run each case one by one:
- Type `#` to select run case
- Type case number (1-21)
- Type `X` to execute
- Press Enter to return

Or use the command file:
```
# Get run case number
1
X
# Next case
# 
2
X
# Continue for all 21 cases...
```

### Step 5: View Results

**View a specific case:**
- Type `#` and the case number (e.g., `# 11` for alpha = 5°)
- Type `T` for Trefftz plane plot (shows lift distribution)
- Press Enter to close plot

**List all cases:**
- Type `L` to list all run cases with their results

**Save results:**
- Type `S` to save updated run cases to file
- Type `wing_from_ntop.run` (or press Enter for default)

### Step 6: Quit
```
Q    # Quit OPER menu
Q    # Quit AVL
```

## Method 2: Automated (Using Command File)

Run AVL with the automated command file:
```powershell
cd ntop
Get-Content wing_from_ntop.commands | avl wing_from_ntop
```

This will:
1. Load the run case file
2. Execute all 21 cases
3. Show Trefftz plot for the last case
4. Save results
5. Exit

**Note:** The automated method may have issues with interactive graphics. Interactive method (Method 1) is recommended for viewing plots.

## Customizing the Flight Envelope

To create a custom flight envelope with different angles of attack:

```powershell
python ntop/create_flight_envelope.py --alpha-min -10 --alpha-max 20 --alpha-step 0.5 --output ntop/custom_envelope.run
```

Options:
- `--alpha-min`: Minimum angle of attack (degrees)
- `--alpha-max`: Maximum angle of attack (degrees)
- `--alpha-step`: Step size (degrees)
- `--output`: Output filename
- `--cl-target`: Use CL constraint instead of alpha (optional)

Example: Create fine resolution envelope from -2° to 10° with 0.25° steps:
```powershell
python ntop/create_flight_envelope.py --alpha-min -2 --alpha-max 10 --alpha-step 0.25 --output ntop/fine_envelope.run
```

## Understanding Results

After running cases, you can:

1. **View CL vs Alpha**: The run case file will have updated CL values for each alpha
2. **Trefftz Plot**: Shows lift distribution across the span (type `T` in OPER menu)
3. **Forces**: Type `FT` to see total forces and moments
4. **Stability**: Type `ST` for stability derivatives

## Tips

- Start with a few cases (e.g., alpha = 0°, 5°, 10°) to verify everything works
- Trefftz plot (`T`) shows the lift distribution - elliptical is ideal
- Use `L` command to list all cases and see CL, CD, CM values
- Results are saved in the `.run` file after you use `S` command

## Troubleshooting

- **No plots showing**: Make sure you're in the OPER menu and have executed a case first (`X` command)
- **Case not converging**: Some high alpha cases may not converge - this is normal
- **Graphics not working**: AVL requires X11 server on Windows (like Xming or VcXsrv)

