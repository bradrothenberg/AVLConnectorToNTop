#!/usr/bin/env python3
"""
Create Flight Envelope Run Cases for AVL
=========================================
Generates an AVL .run file with multiple run cases at different angles of attack
for flight envelope analysis.
"""

import argparse
from pathlib import Path


def create_run_file(output_file, alpha_min=-5.0, alpha_max=15.0, alpha_step=1.0, cl_target=None, mach=0.0):
    """
    Create an AVL run case file with multiple angles of attack.
    
    Args:
        output_file: Path to output .run file
        alpha_min: Minimum angle of attack (degrees)
        alpha_max: Maximum angle of attack (degrees)
        alpha_step: Step size for angle of attack (degrees)
        cl_target: If specified, sets CL constraint instead of alpha
        mach: Mach number (default: 0.0)
    """
    alphas = []
    alpha = alpha_min
    while alpha <= alpha_max:
        alphas.append(alpha)
        alpha += alpha_step
    
    with open(output_file, 'w') as f:
        for i, alpha_val in enumerate(alphas, 1):
            f.write(f"---------------------------------------------\n")
            f.write(f" Run case  {i}:  alpha = {alpha_val:6.2f} deg\n\n")
            
            if cl_target is None:
                # Set alpha directly
                f.write(f" alpha        ->  alpha       = {alpha_val:12.5f}\n")
            else:
                # Set CL constraint, let AVL find alpha
                f.write(f" alpha        ->  CL          = {cl_target:12.5f}\n")
            
            f.write(f" beta         ->  beta        =   0.00000\n")
            f.write(f" pb/2V        ->  pb/2V       =   0.00000\n")
            f.write(f" qc/2V        ->  qc/2V       =   0.00000\n")
            f.write(f" rb/2V        ->  rb/2V       =   0.00000\n")
            f.write(f"\n")
            
            # Parameter values (will be updated when AVL runs)
            f.write(f" alpha     = {alpha_val:12.5f}     deg\n")
            f.write(f" beta      =   0.00000     deg\n")
            f.write(f" pb/2V     =   0.00000\n")
            f.write(f" qc/2V     =   0.00000\n")
            f.write(f" rb/2V     =   0.00000\n")
            if cl_target is None:
                f.write(f" CL        =   0.00000\n")
            else:
                f.write(f" CL        = {cl_target:12.5f}\n")
            f.write(f" CDo       =   0.00000\n")
            f.write(f" bank      =   0.00000     deg\n")
            f.write(f" elevation =   0.00000     deg\n")
            f.write(f" heading   =   0.00000     deg\n")
            f.write(f" Mach      = {mach:12.5f}\n")
            f.write(f" velocity  =   0.00000     ft/s\n")
            f.write(f" density   =  0.0023769     slug/ft^3\n")
            f.write(f" grav.acc. =  32.17400     ft/s^2\n")
            f.write(f" turn_rad. =   0.00000     ft\n")
            f.write(f" load_fac. =   1.00000\n")
            f.write(f" X_cg      =   0.00000     ft\n")
            f.write(f" Y_cg      =   0.00000     ft\n")
            f.write(f" Z_cg      =   0.00000     ft\n")
            f.write(f" mass      =   1.00000     slug\n")
            f.write(f" Ixx       =   1.00000     slug-ft^2\n")
            f.write(f" Iyy       =   1.00000     slug-ft^2\n")
            f.write(f" Izz       =   1.00000     slug-ft^2\n")
            f.write(f" Ixy       =   0.00000     slug-ft^2\n")
            f.write(f" Iyz       =   0.00000     slug-ft^2\n")
            f.write(f" Izx       =   0.00000     slug-ft^2\n")
            f.write(f" visc CL_a =   0.00000\n")
            f.write(f" visc CL_u =   0.00000\n")
            f.write(f" visc CM_a =   0.00000\n")
            f.write(f" visc CM_u =   0.00000\n")
            f.write(f"\n")
    
    print(f"Created run case file: {output_file}")
    print(f"  Number of run cases: {len(alphas)}")
    print(f"  Alpha range: {alpha_min:.1f}° to {alpha_max:.1f}° (step: {alpha_step:.1f}°)")


def create_avl_command_script(avl_base, num_cases, output_file="run_envelope.txt"):
    """
    Create a command script to run AVL and execute all cases, then view Trefftz plots.
    
    Args:
        avl_base: Base name of AVL file (without extension)
        num_cases: Number of run cases
        output_file: Output command script filename
    """
    with open(output_file, 'w') as f:
        # Load the run case file
        f.write(f"CASE\n")
        f.write(f"{avl_base}.run\n")
        
        # Go to OPER menu
        f.write(f"OPER\n")
        
        # Execute all run cases
        for i in range(1, num_cases + 1):
            f.write(f"#\n")  # Select run case
            f.write(f"{i}\n")
            f.write(f"X\n")  # Execute
            f.write(f"\n")   # Return
        
        # View Trefftz plot for last case
        f.write(f"T\n")  # Trefftz plot
        f.write(f"\n")   # Return
        
        # Save results
        f.write(f"S\n")  # Save run cases
        f.write(f"{avl_base}.run\n")
        
        f.write(f"Q\n")  # Quit OPER menu
        f.write(f"Q\n")  # Quit AVL
    
    print(f"Created AVL command script: {output_file}")
    print(f"  Commands: Load run cases, execute all, view Trefftz plot")


def main():
    parser = argparse.ArgumentParser(
        description="Create flight envelope run cases for AVL",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--output', '-o', default='wing_from_ntop.run',
                       help='Output .run filename (default: wing_from_ntop.run)')
    parser.add_argument('--alpha-min', type=float, default=-5.0,
                       help='Minimum angle of attack (degrees, default: -5.0)')
    parser.add_argument('--alpha-max', type=float, default=15.0,
                       help='Maximum angle of attack (degrees, default: 15.0)')
    parser.add_argument('--alpha-step', type=float, default=1.0,
                       help='Angle of attack step size (degrees, default: 1.0)')
    parser.add_argument('--cl-target', type=float, default=None,
                       help='If specified, use CL constraint instead of alpha')
    parser.add_argument('--mach', type=float, default=0.0,
                       help='Mach number (default: 0.0)')
    parser.add_argument('--avl-base', default='wing_from_ntop',
                       help='Base name of AVL file (default: wing_from_ntop)')
    parser.add_argument('--create-commands', action='store_true',
                       help='Also create AVL command script')
    
    args = parser.parse_args()
    
    # Create run file
    create_run_file(
        args.output,
        alpha_min=args.alpha_min,
        alpha_max=args.alpha_max,
        alpha_step=args.alpha_step,
        cl_target=args.cl_target,
        mach=args.mach
    )
    
    # Create command script if requested
    if args.create_commands:
        num_cases = int((args.alpha_max - args.alpha_min) / args.alpha_step) + 1
        cmd_file = Path(args.output).with_suffix('.commands')
        create_avl_command_script(args.avl_base, num_cases, str(cmd_file))
        print(f"\nTo run AVL with these commands:")
        print(f"  cd ntop")
        print(f"  Get-Content {cmd_file.name} | avl {args.avl_base}")


if __name__ == "__main__":
    main()
