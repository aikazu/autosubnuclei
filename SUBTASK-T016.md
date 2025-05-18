# SUBTASK-T016: Refactor Code to Reduce Nesting Complexity

## Parent Task
**T016**: Refactor code to reduce nesting complexity

## Subtask Goal
Improve code maintainability, readability, and testability by reducing nesting depth and complex conditional logic throughout the codebase.

## Dependencies
- Core scanning functionality (complete)
- Checkpoint manager (95% complete)
- Test suite (partial)

## Implementation Approach

### 1. ToolManager Class Refactoring

#### 1.1 _validate_windows_path Method
Current implementation has excessive nesting with multi-level error handling. Split into smaller, focused methods:

```python
# Current method with deep nesting
def _validate_windows_path(self, executable_path: Path) -> bool:
    if self.system != "windows":
        return True
    try:
        if not executable_path.exists():
            return False
        if not str(executable_path).lower().endswith('.exe'):
            return False
        # More nested checks and logic...
        try:
            # Yet more nested PowerShell checks...
        except Exception:
            # Error handling...
    except Exception:
        # More error handling...
```

Refactor to:

```python
def _validate_windows_path(self, executable_path: Path) -> bool:
    """Main validation method with clear steps"""
    if self.system != "windows":
        return True
    
    if not self._basic_path_validation(executable_path):
        return False
        
    return self._powershell_validation(executable_path)
    
def _basic_path_validation(self, path: Path) -> bool:
    """Basic file validation with early returns"""
    
def _powershell_validation(self, path: Path) -> bool:
    """Windows-specific PowerShell validation"""
```

#### 1.2 _execute_windows_tool Method
Simplify platform-specific command execution:

```python
def _execute_windows_tool(self, tool_name: str, args: List[str]) -> subprocess.CompletedProcess:
    tool_path = self._find_tool_path(tool_name)
    cmd = self._build_command(tool_path, args)
    return self._execute_command(cmd)
    
def _find_tool_path(self, tool_name: str) -> str:
    """Find the tool path, either in tools directory or PATH"""
    
def _build_command(self, exec_path: str, args: List[str]) -> str:
    """Build the command string with proper quoting"""
    
def _execute_command(self, cmd: str) -> subprocess.CompletedProcess:
    """Execute the command with proper environment"""
```

### 2. SecurityScanner Class Refactoring

#### 2.1 _run_httpx Method
Extract resumption logic and batch processing:

```python
async def _run_httpx(self, subdomains) -> str:
    if self._should_load_from_checkpoint("alive_check"):
        return self._load_alive_subdomains_from_checkpoint()
    
    # Initialize phase
    self._initialize_alive_check_phase()
    
    # Prepare for processing
    subdomain_list, temp_file = self._prepare_subdomains_for_processing(subdomains)
    
    # Calculate batch parameters
    batch_size, total_batches, start_batch = self._calculate_batch_parameters(subdomain_list)
    
    # Process in batches
    result = await self._process_subdomains_in_batches(subdomain_list, temp_file, batch_size, total_batches, start_batch)
    
    return result
```

#### 2.2 _run_nuclei_in_batches Method
Simplify batch processing logic:

```python
async def _run_nuclei_in_batches(self, targets_file: Path, severities: List[str], batch_size: int) -> List[Dict[str, Any]]:
    total_lines = self._count_file_lines(targets_file)
    total_batches = self._calculate_total_batches(total_lines, batch_size)
    
    return await self._process_nuclei_batches(targets_file, severities, batch_size, total_batches)
```

### 3. ProgressMonitor Class Refactoring

#### 3.1 update Method
Replace complex conditional logic with strategy pattern:

```python
def update(self):
    current_status = self.scanner.scan_state.get("status", "")
    
    if not current_status or self.last_status == current_status:
        return
        
    self._close_progress_bar()
    self.progress_bar = self._create_progress_bar_for_status(current_status)
    self.last_status = current_status
    
def _create_progress_bar_for_status(self, status: str) -> Optional[tqdm]:
    # Map of status types to creation methods
    status_handlers = {
        "downloading_templates": self._create_download_progress_bar,
        "discovering_subdomains": self._create_discovery_progress_bar,
        "probing_subdomains": self._create_probe_progress_bar,
        "scanning_vulnerabilities": self._create_scan_progress_bar,
        "completed": self._handle_completion,
        "error": self._handle_error
    }
    
    handler = status_handlers.get(status)
    if not handler:
        return None
        
    return handler()
```

### 4. CheckpointManager Class Refactoring

#### 4.1 FileLock Implementation
Create platform-specific implementations:

```python
# Base class with common interface
class BaseFileLock:
    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.lock_handle = None
        
    def acquire(self, timeout: int = 10, check_interval: float = 0.1) -> bool:
        """Acquire lock - implemented by subclasses"""
        raise NotImplementedError
        
    def release(self) -> bool:
        """Release lock - common implementation"""
        # Common release logic
        
# Windows implementation
class WindowsFileLock(BaseFileLock):
    def acquire(self, timeout: int = 10, check_interval: float = 0.1) -> bool:
        # Windows-specific implementation
        
# Unix implementation
class UnixFileLock(BaseFileLock):
    def acquire(self, timeout: int = 10, check_interval: float = 0.1) -> bool:
        # Unix-specific implementation with fcntl
        
# Factory function
def create_file_lock(lock_file: Path) -> BaseFileLock:
    if os.name == 'nt':
        return WindowsFileLock(lock_file)
    else:
        return UnixFileLock(lock_file)
```

#### 4.2 repair_checkpoint Method
Replace nested conditionals with lookup approach:

```python
def repair_checkpoint(self) -> bool:
    if not self.checkpoint_data:
        logger.error("Cannot repair checkpoint: checkpoint not initialized")
        return False
        
    try:
        # Define repair handlers for each field type
        field_handlers = {
            "scan_id": self._repair_scan_id,
            "domain": self._repair_domain,
            "start_time": self._repair_timestamp,
            "last_update": self._repair_timestamp,
            "status": self._repair_status,
            "phases": self._repair_phases,
            "statistics": self._repair_statistics,
            "environment": self._repair_environment
        }
        
        # Check and repair required fields
        for field in self._required_fields():
            if field not in self.checkpoint_data:
                handler = field_handlers.get(field)
                if handler:
                    handler()
                    
        # Check and repair phases
        self._repair_all_phases()
        
        # Save repaired checkpoint
        with FileLock(self.lock_file):
            self._write_checkpoint()
            
        logger.info("Checkpoint repair successful")
        return True
        
    except Exception as e:
        logger.error(f"Error repairing checkpoint: {str(e)}")
        return False
        
def _required_fields(self) -> List[str]:
    """Return list of required fields"""
    
def _repair_scan_id(self) -> None:
    """Repair scan_id field"""
    
def _repair_domain(self) -> None:
    """Repair domain field"""
    
# Additional repair methods for each field type...
```

## Refactoring Strategy and Guidelines

1. **Extract Method Refactoring**:
   - Extract complex nested code into separate, focused methods
   - Follow single responsibility principle
   - Target nesting depth should be maximum 2-3 levels

2. **Replace Conditionals with Strategy Pattern**:
   - Use dictionaries to map conditions to handlers
   - Replace if/elif chains with lookups
   - Use polymorphism where appropriate

3. **Use Guard Clauses**:
   - Return early for special cases
   - Handle error conditions at the top of methods
   - Convert nested conditions to flat structures

4. **Testing Approach**:
   - Write tests for current behavior before refactoring
   - Unit test each extracted method
   - Ensure overall behavior remains unchanged

## Progress Status
- Analysis (100%)
- Implementation (0%)

## Validation Criteria
- Maximum nesting depth reduced to 3 levels
- All methods less than 50 lines (with exceptions only for truly indivisible logic)
- Improved code coverage for refactored classes
- No new bugs introduced in core functionality
- All unit tests pass

## Files to Modify
- `autosubnuclei/utils/tool_manager.py`
- `autosubnuclei/core/scanner.py`
- `autosubnuclei.py` (ProgressMonitor class)
- `autosubnuclei/core/checkpoint_manager.py`
- `autosubnuclei/commands/resume.py`

## Implementation Schedule

1. **Week 1**: ToolManager and SecurityScanner refactoring
   - Day 1-2: Write tests for existing functionality
   - Day 3-4: Refactor ToolManager class
   - Day 5: Refactor SecurityScanner _run_httpx and batch processing

2. **Week 2**: CheckpointManager and ProgressMonitor refactoring
   - Day 1-2: Refactor CheckpointManager and FileLock
   - Day 3: Refactor ProgressMonitor update method
   - Day 4-5: Integration testing and documentation updates 