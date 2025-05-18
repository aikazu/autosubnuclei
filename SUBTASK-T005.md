# SUBTASK-T005: Scan Resume Functionality

## Parent Task
**T005**: Implement scan resume functionality

## Subtask Goal
Design and implement a system to allow interrupted scans to be resumed, maintaining state between sessions and recovering from unexpected interruptions.

## Dependencies
- Core scanning functionality (complete)
- Configuration management (complete)
- Memory optimization (complete)

## Implementation Approach

### 1. State Persistence Design

#### 1.1 State Data Model
The scan state needs to track:
- Domain being scanned
- Scan start time
- Last update time
- Current progress by phase
- Completed subdomains
- Alive subdomains already processed
- Nuclei scan progress
- Results found so far
- Tools used and their versions

Proposed JSON structure:
```json
{
  "scan_id": "unique-scan-identifier",
  "domain": "example.com",
  "start_time": "2023-10-15T12:34:56",
  "last_update": "2023-10-15T12:45:23",
  "status": "in_progress|paused|completed|failed",
  "phases": {
    "subdomain_enumeration": {
      "status": "completed|in_progress|pending",
      "progress_percentage": 100,
      "results_count": 234
    },
    "alive_check": {
      "status": "in_progress",
      "progress_percentage": 45,
      "results_count": 52,
      "checkpoint": {
        "last_processed": "sub52.example.com",
        "batch_index": 3
      }
    },
    "vulnerability_scan": {
      "status": "pending",
      "progress_percentage": 0,
      "results_count": 0
    }
  },
  "statistics": {
    "subdomains_found": 234,
    "alive_subdomains": 52,
    "vulnerabilities_found": 0
  },
  "environment": {
    "tool_versions": {
      "subfinder": "2.5.3",
      "httpx": "1.2.5",
      "nuclei": "2.9.1"
    },
    "templates_hash": "abcdef123456"
  }
}
```

#### 1.2 Storage Mechanism
Options to consider:
1. **JSON files**: Simple, human-readable, but less robust for concurrent access
2. **SQLite database**: Better for structured data and atomic operations
3. **Pickle files**: Python-specific, compact but not human-readable

Recommendation: Use JSON files for initial implementation with a lock file mechanism to prevent corruption.

#### 1.3 Checkpoint Locations
Checkpoints should be created:
- After subdomain enumeration phase
- After every batch of alive checks (configurable batch size)
- After every batch of nuclei scans (configurable batch size)
- When user requests a pause via signal (CTRL+C)
- Periodically during long-running scans (every 5 minutes)

### 2. Resume Logic Implementation

#### 2.1 CLI Interface
Add resume command and options:
```
autosubnuclei resume [domain] [options]
  --from-checkpoint=PATH  Resume from a specific checkpoint file
  --force-phase=PHASE     Force restart from a specific phase
  --skip-verification     Skip environment verification
```

#### 2.2 Resume Process Flow
1. Load checkpoint file
2. Verify environment matches (tool versions, templates)
3. Display summary of previous progress
4. Confirm with user before proceeding
5. Initialize scanner with checkpoint data
6. Skip completed phases
7. For in-progress phases, resume from the last checkpoint
8. Continue with pending phases as normal

#### 2.3 Graceful Interruption Handling
1. Register signal handlers (SIGINT, SIGTERM)
2. On interruption, complete current operation safely
3. Write checkpoint data
4. Display resume instructions to user

### 3. File Structure Changes

#### 3.1 New Files
- `autosubnuclei/core/checkpoint_manager.py`: Manage checkpoint saving/loading
- `autosubnuclei/commands/resume.py`: Handle resume command logic

#### 3.2 Modified Files
- `autosubnuclei/core/scanner.py`: Add checkpoint integration
- `autosubnuclei.py`: Add resume command support

### 4. Implementation Steps

#### Phase 1: Basic Framework
1. Create checkpoint data model and serialization helpers
2. Implement checkpoint saving in main scan phases
3. Add signal handlers for graceful interruption
4. Create directory structure for checkpoints

#### Phase 2: Resume Logic
1. Implement resume command and loading of checkpoint data
2. Add verification of environment consistency
3. Create resume flow with user confirmation
4. Implement phase skipping and resumption logic

#### Phase 3: Robustness Improvements
1. Add locking mechanism to prevent checkpoint corruption
2. Implement automated periodic checkpoints during long scans
3. Add cleanup of old checkpoint files
4. Create verification tests for resume functionality

#### Phase 4: User Experience Enhancements
1. Add progress display showing resumed vs. new work
2. Implement scan comparison between resumptions
3. Add summary of time saved by resuming
4. Create log entries for resume operations

## Progress Status
- Design phase (100%)
- Implementation (95%)

### Completed Features
- ✅ Checkpoint data model and serialization helpers
- ✅ Checkpoint saving in main scan phases
- ✅ Signal handlers for graceful interruption
- ✅ Directory structure for checkpoints
- ✅ Resume command and loading of checkpoint data
- ✅ Environment verification for resumed scans
- ✅ Phase skipping and resumption logic
- ✅ Locking mechanism to prevent checkpoint corruption
- ✅ Automatic periodic checkpoints during long scans
- ✅ Checkpoint integrity verification
- ✅ Automatic checkpoint repair for corruption
- ✅ Checkpoint file optimization to reduce size
- ✅ Backup creation before resumption
- ✅ Documentation for resume functionality
- ✅ Testing script for different interruption scenarios
- ✅ Test for corrupt checkpoint recovery

### Remaining Work
- Additional real-world testing with very large domain lists

## Validation Criteria
- ✅ Successfully resume after interruption at each phase
- ✅ No data loss between sessions
- ✅ Correct handling of edge cases (e.g., tool versions changed)
- ✅ Minimal disk space usage for checkpoints
- ✅ Performance impact < 5% with checkpointing enabled

## Files to Modify
- `autosubnuclei/core/scanner.py`
- `autosubnuclei.py`
- New file: `autosubnuclei/core/checkpoint_manager.py`
- New file: `autosubnuclei/commands/resume.py`

## Implementation Details

### Checkpoint Manager Class
```python
class CheckpointManager:
    def __init__(self, domain, output_dir):
        self.domain = domain
        self.checkpoint_dir = output_dir / "checkpoints"
        self.checkpoint_file = self.checkpoint_dir / "scan_state.json"
        self.lock_file = self.checkpoint_dir / "scan_state.lock"
        self.scan_id = self._generate_scan_id()
        
    def _generate_scan_id(self):
        # Generate a unique scan ID
        return f"{self.domain}-{int(time.time())}"
        
    def initialize_checkpoint(self, tools_versions):
        # Create initial checkpoint structure
        pass
        
    def update_phase_status(self, phase, status, progress, results_count):
        # Update a phase's status with lock protection
        pass
        
    def update_checkpoint(self, phase, **kwargs):
        # Update checkpoint with phase-specific data
        pass
        
    def save_checkpoint(self):
        # Write checkpoint to disk with lock protection
        pass
        
    def load_checkpoint(self):
        # Load checkpoint from disk
        pass
        
    def validate_environment(self, current_tool_versions):
        # Check if current environment matches checkpoint
        pass
```

### Scanner Integration
```python
class SecurityScanner:
    def __init__(self, domain, output_dir, templates_path, checkpoint=None):
        # ... existing initialization ...
        self.checkpoint_manager = CheckpointManager(domain, output_dir)
        self.resuming = checkpoint is not None
        
        if self.resuming:
            self._load_scan_state(checkpoint)
        else:
            self._initialize_scan_state()
            
    def _initialize_scan_state(self):
        # Initialize new scan state
        tool_versions = self.tool_manager.get_all_tool_versions()
        self.checkpoint_manager.initialize_checkpoint(tool_versions)
        
    def _load_scan_state(self, checkpoint):
        # Load existing scan state
        self.checkpoint_manager.load_checkpoint()
        # Validate environment
        current_tool_versions = self.tool_manager.get_all_tool_versions()
        self.checkpoint_manager.validate_environment(current_tool_versions)
        
    async def run_scan(self, severities):
        # Setup signal handlers
        self._setup_interruption_handlers()
        
        # Run phases with checkpoint awareness
        if not self.resuming or self.checkpoint_manager.get_phase_status("subdomain_enumeration") != "completed":
            await self._run_subdomain_enumeration()
            
        # ... similar logic for other phases ...
        
    def _setup_interruption_handlers(self):
        # Register signal handlers for graceful interruption
        pass
```

### CLI Resume Command
```python
@cli.command()
@click.argument('domain')
@click.option('--from-checkpoint', type=click.Path(exists=True),
              help="Resume from a specific checkpoint file")
@click.option('--force-phase', type=click.Choice(['subdomain', 'alive', 'nuclei']),
              help="Force restart from a specific phase")
@click.option('--skip-verification', is_flag=True,
              help="Skip environment verification")
def resume(domain, from_checkpoint, force_phase, skip_verification):
    """Resume an interrupted security scan"""
    # Implementation of resume logic
    pass
```

## Next Steps
1. Implement checkpoint data model in checkpoint_manager.py
2. Add checkpoint saving to main scan phases
3. Create basic resume command structure
4. Implement signal handlers for graceful interruption 