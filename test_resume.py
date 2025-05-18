#!/usr/bin/env python3
"""
Test script for the scan resume functionality in AutoSubNuclei.
This script deliberately interrupts scans at different phases and tests resumption.
"""

import os
import sys
import time
import signal
import subprocess
import argparse
import random
import shutil
from pathlib import Path
import json

def run_command(cmd, timeout=None, interrupt_after=None):
    """
    Run a command with option to interrupt after a specified time.
    
    Args:
        cmd: Command list to run
        timeout: Maximum time to let the command run
        interrupt_after: Seconds after which to interrupt (SIGINT)
        
    Returns:
        Tuple of (return_code, output)
    """
    print(f"Running command: {' '.join(cmd)}")
    
    if interrupt_after:
        print(f"Will interrupt after {interrupt_after} seconds")
        
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    output = []
    start_time = time.time()
    
    try:
        for line in process.stdout:
            line = line.rstrip()
            print(line)
            output.append(line)
            
            # Check if we need to interrupt
            if interrupt_after and (time.time() - start_time) >= interrupt_after:
                print(f"\n[TEST] Interrupting process after {interrupt_after} seconds")
                process.send_signal(signal.SIGINT)
                interrupt_after = None  # Only interrupt once
                
        process.wait(timeout=timeout)
        return process.returncode, "\n".join(output)
        
    except subprocess.TimeoutExpired:
        print(f"[TEST] Process timed out after {timeout} seconds")
        process.kill()
        return -1, "\n".join(output)
    
    except KeyboardInterrupt:
        print("[TEST] Received keyboard interrupt")
        process.kill()
        return -2, "\n".join(output)

def test_resume_at_phase(domain, phase, output_dir="output"):
    """
    Test interruption and resumption at a specific phase.
    
    Args:
        domain: Domain to scan
        phase: Phase to interrupt at ("subdomain", "alive", "nuclei")
        output_dir: Output directory for scan results
    """
    output_path = Path(output_dir) / domain
    
    # Clean output directory if it exists
    if output_path.exists():
        shutil.rmtree(output_path)
    
    # Map phases to approximate timing for interruption
    phase_timings = {
        "subdomain": 5,  # Interrupt after 5 seconds for subdomain phase
        "alive": 10,     # Interrupt after 10 seconds for alive check phase
        "nuclei": 15     # Interrupt after 15 seconds for nuclei scan phase
    }
    
    # Start scan with interruption
    scan_cmd = ["python", "autosubnuclei.py", "scan", domain, "--output", output_dir]
    print(f"\n[TEST] Running initial scan with interruption during {phase} phase")
    return_code, output = run_command(scan_cmd, interrupt_after=phase_timings[phase])
    
    # Check if we were actually interrupted
    if return_code == 0:
        print("[TEST] Scan completed without interruption - test failed")
        return False
    
    # Verify checkpoint file exists
    checkpoint_file = output_path / "checkpoints" / "scan_state.json"
    if not checkpoint_file.exists():
        print(f"[TEST] Checkpoint file not found at {checkpoint_file}")
        return False
    
    print(f"\n[TEST] Found checkpoint file at {checkpoint_file}")
    time.sleep(2)  # Brief pause
    
    # Try to resume the scan
    print(f"\n[TEST] Attempting to resume scan from checkpoint")
    resume_cmd = ["python", "autosubnuclei.py", "resume", domain, "--output", output_dir, "--no-confirm"]
    return_code, output = run_command(resume_cmd)
    
    # Check if resume completed successfully
    if return_code != 0:
        print("[TEST] Resume command failed")
        return False
    
    print("\n[TEST] Resume completed. Checking results...")
    
    # Verify results exist
    results_file = output_path / "results.txt"
    state_file = output_path / "scan_state.json"
    
    if not state_file.exists():
        print("[TEST] Scan state file not found")
        return False
    
    print(f"[TEST] Resume test for {phase} phase passed!")
    return True

def test_resume_with_random_interrupts(domain, interrupts=3, output_dir="output"):
    """
    Test multiple random interruptions during a scan.
    
    Args:
        domain: Domain to scan
        interrupts: Number of times to interrupt the scan
        output_dir: Output directory for scan results
    """
    output_path = Path(output_dir) / domain
    
    # Clean output directory if it exists
    if output_path.exists():
        shutil.rmtree(output_path)
    
    current_cmd = ["python", "autosubnuclei.py", "scan", domain, "--output", output_dir]
    
    for i in range(interrupts):
        interrupt_after = random.randint(3, 20)  # Random interrupt between 3-20 seconds
        print(f"\n[TEST] Running scan attempt {i+1}/{interrupts} with interruption after ~{interrupt_after}s")
        
        return_code, output = run_command(current_cmd, interrupt_after=interrupt_after)
        
        # Check if scan completed despite interrupt attempt
        if return_code == 0:
            print("[TEST] Scan completed without interruption")
            break
        
        # Check if checkpoint file exists
        checkpoint_file = output_path / "checkpoints" / "scan_state.json"
        if not checkpoint_file.exists():
            print(f"[TEST] Checkpoint file not found at {checkpoint_file}")
            return False
        
        print(f"[TEST] Found checkpoint file at {checkpoint_file}")
        time.sleep(2)  # Brief pause
        
        # Update command to resume
        current_cmd = ["python", "autosubnuclei.py", "resume", domain, "--output", output_dir, "--no-confirm"]
    
    # Final run to completion
    if return_code != 0:
        print("\n[TEST] Running final resume to completion")
        return_code, output = run_command(current_cmd)
    
    # Check if resume completed successfully
    if return_code != 0:
        print("[TEST] Final resume command failed")
        return False
    
    # Verify results exist
    state_file = output_path / "scan_state.json"
    
    if not state_file.exists():
        print("[TEST] Scan state file not found")
        return False
    
    print(f"\n[TEST] Multiple interruptions test passed! Scan completed after {interrupts} interruptions.")
    return True

def test_resume_with_corrupt_checkpoint(domain, output_dir="output"):
    """
    Test resumption with a corrupted checkpoint file.
    
    Args:
        domain: Domain to scan
        output_dir: Output directory for scan results
    """
    output_path = Path(output_dir) / domain
    
    # Clean output directory if it exists
    if output_path.exists():
        shutil.rmtree(output_path)
    
    # Start a normal scan with interruption
    scan_cmd = ["python", "autosubnuclei.py", "scan", domain, "--output", output_dir]
    print(f"\n[TEST] Running initial scan with interruption")
    return_code, output = run_command(scan_cmd, interrupt_after=5)
    
    # Check if we were actually interrupted
    if return_code == 0:
        print("[TEST] Scan completed without interruption - test failed")
        return False
    
    # Verify checkpoint file exists
    checkpoint_file = output_path / "checkpoints" / "scan_state.json"
    if not checkpoint_file.exists():
        print(f"[TEST] Checkpoint file not found at {checkpoint_file}")
        return False
    
    print(f"\n[TEST] Found checkpoint file at {checkpoint_file}")
    
    # Corrupt the checkpoint file
    print(f"\n[TEST] Corrupting checkpoint file")
    try:
        # Read the checkpoint file
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
        
        # Corrupt the data by removing a key
        if "statistics" in checkpoint_data:
            del checkpoint_data["statistics"]
        
        # Write back the corrupted data
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)
            
        print("[TEST] Checkpoint file corrupted successfully")
    except Exception as e:
        print(f"[TEST] Error corrupting checkpoint file: {str(e)}")
        return False
    
    time.sleep(2)  # Brief pause
    
    # Try to resume with automatic repair
    print(f"\n[TEST] Attempting to resume scan with corrupted checkpoint")
    # Add --no-confirm to automatically repair the checkpoint
    resume_cmd = ["python", "autosubnuclei.py", "resume", domain, "--output", output_dir, "--no-confirm"]
    return_code, output = run_command(resume_cmd)
    
    # Check if resume completed successfully
    if return_code != 0:
        print("[TEST] Resume command failed")
        return False
    
    print("\n[TEST] Resume with corrupt checkpoint test completed successfully")
    return True

def main():
    parser = argparse.ArgumentParser(description="Test the scan resume functionality")
    parser.add_argument("domain", help="Domain to use for testing")
    parser.add_argument("--output", default="output", help="Output directory")
    parser.add_argument("--phase", choices=["subdomain", "alive", "nuclei"], 
                       help="Specific phase to test interruption at")
    parser.add_argument("--random", action="store_true", 
                       help="Test multiple random interruptions")
    parser.add_argument("--corrupt", action="store_true",
                       help="Test resumption with corrupted checkpoint")
    
    args = parser.parse_args()
    
    if args.corrupt:
        success = test_resume_with_corrupt_checkpoint(args.domain, args.output)
    elif args.phase:
        success = test_resume_at_phase(args.domain, args.phase, args.output)
    elif args.random:
        success = test_resume_with_random_interrupts(args.domain, interrupts=3, output_dir=args.output)
    else:
        print("Please specify a test type: --phase, --random, or --corrupt")
        sys.exit(1)
    
    if success:
        print("\n✅ Test completed successfully")
        sys.exit(0)
    else:
        print("\n❌ Test failed")
        sys.exit(1)

if __name__ == "__main__":
    sys.exit(main()) 