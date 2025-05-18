# Scan Resume Functionality

## Overview

AutoSubNuclei includes a powerful scan resume functionality that allows you to continue interrupted scans without losing progress. This feature is particularly useful for:

- Long-running scans that were interrupted by system shutdown or network issues
- Scans that need to be paused and resumed later
- Recovering from unexpected errors during scanning

The resume functionality uses a checkpoint system to save scan state at key points and automatically recover from where it left off.

## How It Works

1. **Checkpoint Creation**: During a scan, AutoSubNuclei creates checkpoints at key milestones:
   - After subdomain enumeration phase
   - After each batch of alive checks
   - After each batch of vulnerability scans
   - When the user interrupts the scan (Ctrl+C)
   - Periodically every few minutes during long-running phases

2. **State Persistence**: Scan state is saved in JSON format with a lock mechanism to prevent corruption. 
   The state includes:
   - Current progress by phase
   - Results found so far
   - Tool versions used
   - Environment information

3. **Resumption Logic**: When resuming a scan, AutoSubNuclei:
   - Validates the environment matches the original scan
   - Verifies checkpoint integrity
   - Displays a summary of previous progress
   - Confirms with the user before proceeding
   - Skips completed phases
   - Resumes in-progress phases from the last checkpoint

## Usage

### Basic Resume Command

```bash
autosubnuclei resume example.com
```

This command will look for the latest checkpoint in the default output directory and resume the scan.

### Advanced Options

```bash
autosubnuclei resume example.com [options]
```

Available options:

| Option | Description |
|--------|-------------|
| `--from-checkpoint=PATH` | Resume from a specific checkpoint file |
| `--force-phase=PHASE` | Force restart from a specific phase (subdomain, alive, nuclei) |
| `--skip-verification` | Skip environment verification |
| `--output=DIR` | Specify output directory (default: "output") |
| `--templates=DIR` | Path to nuclei templates |
| `--no-confirm` | Skip confirmation prompts |
| `--severities=LIST` | Override comma-separated severity levels |

### Examples

Resume a scan for example.com:
```bash
autosubnuclei resume example.com
```

Resume from a specific checkpoint file:
```bash
autosubnuclei resume example.com --from-checkpoint=path/to/checkpoint.json
```

Force restart from the alive check phase:
```bash
autosubnuclei resume example.com --force-phase=alive
```

Resume without confirmation prompts:
```bash
autosubnuclei resume example.com --no-confirm
```

## Error Recovery

The resume functionality includes robust error recovery mechanisms:

1. **Checkpoint Integrity Verification**: Before resuming, the system checks if the checkpoint file is valid and complete.

2. **Automatic Repair**: If issues are detected in the checkpoint file, AutoSubNuclei can attempt to repair it.

3. **Environment Validation**: The system checks if the current tools match those used in the original scan.

4. **Checkpoint Backup**: A backup of the checkpoint is created before attempting to resume, ensuring you can recover if anything goes wrong.

5. **Optimization**: Checkpoint files are optimized to remove unnecessary data, keeping file sizes manageable.

## Best Practices

1. **Allow Graceful Interruption**: When you need to stop a scan, use Ctrl+C instead of force-quitting the application. This ensures a proper checkpoint is created.

2. **Verify Output Directory**: Make sure the output directory matches the one used in the original scan when resuming.

3. **Check Tool Versions**: If you've updated your tools between the initial scan and resuming, consider whether this might affect the results.

4. **Regular Backups**: For critical scans, consider backing up the checkpoints directory periodically.

5. **Test Resumption**: For important scans, consider testing the resume functionality on a small domain first.

## Troubleshooting

### Common Issues

1. **"Checkpoint file not found"**: Ensure you're specifying the correct output directory that contains the checkpoint.

2. **"Failed to load checkpoint file"**: The checkpoint file might be corrupted. Try using the repair option.

3. **"Environment mismatch detected"**: Tool versions have changed since the original scan. You can continue, but results might be inconsistent.

4. **"Scan completed without change"**: Some phases may not detect any progress since the last checkpoint. This is normal.

### Recovering from Corrupted Checkpoints

If you encounter issues with a corrupted checkpoint:

1. Try using the automatic repair:
   ```bash
   autosubnuclei resume example.com
   ```
   When prompted about integrity issues, choose to repair.

2. If automatic repair fails, check the backup checkpoints in the `output/example.com/checkpoints/` directory.

3. As a last resort, you can start a new scan.

## Implementation Details

- Checkpoints are stored in the `output/domain/checkpoints/` directory
- The main checkpoint file is `scan_state.json`
- Backups are named `scan_state_YYYYMMDD_HHMMSS.json`
- A lock file (`scan_state.lock`) prevents concurrent access

## Testing

To test the resume functionality:

```bash
python test_resume.py example.com --phase=subdomain
```

This script interrupts a scan at the specified phase and tests resumption.

You can also test with corrupted checkpoints:

```bash
python test_resume.py example.com --corrupt
``` 