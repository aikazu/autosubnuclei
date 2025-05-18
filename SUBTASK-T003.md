# SUBTASK-T003: Fix Configuration File Path Handling

## Parent Task Reference
- **Task ID**: T003
- **Description**: Fix configuration file path handling
- **Priority**: High
- **Status**: In Progress
- **Progress**: 90%

## Subtask Goal
Ensure that the configuration file is correctly located and accessed regardless of the directory from which the tool is executed.

## Dependencies
None

## Implementation Approach

### Problem Analysis
Currently, the configuration file path is determined relative to the module's location. This works when running from the project root but fails when executed from a different directory. The key issue is in the `ConfigManager` class initialization.

### Solution Steps

1. **Update ConfigManager initialization**:
   - Modify the `__init__` method to handle different execution contexts
   - Use absolute paths consistently
   - Check multiple potential locations for the config file

2. **Improve config file discovery logic**:
   - First check if config exists at the specified path
   - If not, try to find it relative to the executable's location
   - If still not found, try to find it relative to the current working directory
   - Finally, fall back to creating a new config file in an appropriate location

3. **Enhance path resolution**:
   - Add helper methods to resolve config paths consistently
   - Handle edge cases like symlinks and relative paths

4. **Add tests**:
   - Create tests to verify config loading from different directories
   - Test edge cases for path resolution

## Files to Modify

1. `autosubnuclei/config/config_manager.py` - Update the ConfigManager class with improved path handling

## Implementation Details

The primary changes will be to the `ConfigManager` class in `config_manager.py`, focusing on the `__init__` and `_ensure_config_exists` methods:

```python
def __init__(self, config_path=None):
    """
    Initialize the ConfigManager with a specified or default config path.
    
    Args:
        config_path (str or Path, optional): Path to the config file.
            If not provided, will search in standard locations.
    """
    # If path specified, use it directly
    if config_path:
        self.config_file = Path(config_path).resolve()
        self.config_dir = self.config_file.parent
    else:
        # Try to find config in various locations
        self.config_file = self._find_config_file()
        self.config_dir = self.config_file.parent
        
    self._ensure_config_exists()

def _find_config_file(self):
    """
    Find the configuration file in various possible locations.
    
    Returns:
        Path: Resolved path to the config file (may not exist yet)
    """
    # Possible locations in priority order
    possible_locations = [
        # 1. Root workspace directory
        Path.cwd() / "config.json",
        
        # 2. In config subdirectory of workspace
        Path.cwd() / "config" / "config.json",
        
        # 3. In the same directory as the executing script
        Path(__file__).parent.parent.parent / "config.json",
        
        # 4. In user's home directory
        Path.home() / ".autosubnuclei" / "config.json"
    ]
    
    # Try each location
    for loc in possible_locations:
        if loc.exists():
            return loc
    
    # Default to workspace root if none found
    return Path.cwd() / "config.json"
```

## Validation Criteria

1. Configuration can be loaded correctly when:
   - Running from project root directory
   - Running from a different directory
   - Running via absolute path to script
   - Running via relative path to script

2. New configuration files are created in the appropriate location when not found

3. Configuration changes are saved to the correct file

## Progress Status

90% - Implementation completed. The ConfigManager class has been updated to properly handle config file paths in different execution contexts.

The following improvements have been implemented:
1. Added config_path parameter to ConfigManager.__init__ for custom config paths
2. Implemented _find_config_file method to locate config files in various locations
3. Enhanced _ensure_config_exists to properly handle directory creation
4. Updated save_config to ensure the parent directory exists before saving

## Notes

The implementation has been completed as planned. Testing is recommended across different execution contexts to ensure that the configuration file is correctly located and accessed regardless of the directory from which the tool is executed. 