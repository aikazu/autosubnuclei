# SUBTASK-T001: Improve Error Handling in Tool Installation

## Parent Task Reference
- **Task ID**: T001
- **Description**: Improve error handling in tool installation
- **Priority**: High
- **Status**: In Progress
- **Progress**: 90%

## Subtask Goal
Enhance error handling in the tool installation process to make it more robust against network issues, API rate limits, and other potential failures.

## Dependencies
None

## Implementation Approach

### Problem Analysis
Currently, the tool installation process in `tool_manager.py` has basic error handling but lacks:
1. Retry mechanisms for transient failures
2. Comprehensive error reporting
3. Fallback strategies when GitHub API fails
4. Proper cleanup when installations partially fail
5. Verification of downloaded files

### Solution Steps

1. **Implement retries for API requests**:
   - Add retry mechanism with exponential backoff for GitHub API requests
   - Handle rate limiting with proper waiting
   - Provide clear feedback during retry attempts

2. **Enhance error reporting**:
   - Improve error messages with specific causes
   - Add logging at appropriate levels
   - Return detailed error information from methods

3. **Add fallback strategies**:
   - Implement direct download URL construction when API fails
   - Support alternative download sources
   - Cache successful download URLs

4. **Improve file validation**:
   - Verify downloaded files with checksums or size checks
   - Implement better cleanup for failed installations
   - Add post-installation verification

5. **Add proper state management**:
   - Track installation state to enable resumption
   - Handle partial installations gracefully
   - Support cleanup and recovery

## Files to Modify

1. `autosubnuclei/utils/tool_manager.py` - Primary focus
2. `autosubnuclei/utils/helpers.py` - Add retry helpers

## Implementation Details

### Retry Mechanism in Helpers

```python
def retry_with_backoff(func, max_retries=3, base_delay=1, max_delay=60):
    """
    Execute a function with exponential backoff retry logic.
    
    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        
    Returns:
        The result of the function call
        
    Raises:
        The last exception encountered after all retries
    """
    import time
    import random
    
    retries = 0
    last_exception = None
    
    while retries <= max_retries:
        try:
            return func()
        except Exception as e:
            last_exception = e
            retries += 1
            
            if retries > max_retries:
                break
                
            # Calculate delay with exponential backoff and jitter
            delay = min(base_delay * (2 ** (retries - 1)) + random.uniform(0, 1), max_delay)
            
            logging.warning(f"Retry attempt {retries}/{max_retries} after {delay:.2f}s due to: {str(e)}")
            time.sleep(delay)
    
    # If we reach here, all retries failed
    raise last_exception
```

### Enhanced _get_latest_release Method

```python
def _get_latest_release(self, repo: str) -> Tuple[str, str]:
    """
    Get the latest release version and download URL for a GitHub repository
    with improved error handling and retries.
    """
    def _try_api_request():
        session = create_requests_session()
        release_url = f"https://api.github.com/repos/{repo}/releases/latest"
        response = session.get(release_url)
        response.raise_for_status()
        return response.json()
    
    try:
        # Try with retries
        release_data = retry_with_backoff(
            _try_api_request, 
            max_retries=3
        )
        
        version = release_data['tag_name'].lstrip('v')
        assets = release_data.get('assets', [])
        
        # Find the correct asset for our platform
        for asset in assets:
            asset_name = asset['name'].lower()
            if (self.system in asset_name and 
                self.arch in asset_name and 
                asset_name.endswith('.zip')):
                return version, asset['browser_download_url']
        
        # Fall back to constructing URL
        return self._construct_download_url(repo, version)
    
    except Exception as e:
        logging.error(f"GitHub API request failed: {str(e)}")
        
        # Try alternative approach - get latest from tags
        try:
            return self._get_latest_from_tags(repo)
        except Exception as nested_e:
            logging.error(f"Failed to get latest release from tags: {str(nested_e)}")
            
            # Last resort - try to construct a URL with a guessed version
            tool_name = repo.split('/')[-1]
            guessed_version = self._guess_latest_version(tool_name)
            if guessed_version:
                logging.warning(f"Using guessed version {guessed_version} for {tool_name}")
                return guessed_version, self._construct_download_url(repo, guessed_version)
            
            raise RuntimeError(f"Could not determine download URL for {repo}: {str(e)}")
```

### Download Verification

```python
def _verify_download(self, download_path: Path, expected_min_size: int = 1000) -> bool:
    """
    Verify that a downloaded file is valid.
    
    Args:
        download_path: Path to the downloaded file
        expected_min_size: Minimum expected file size in bytes
        
    Returns:
        bool: True if the file is valid, False otherwise
    """
    if not download_path.exists():
        logging.error(f"Downloaded file does not exist: {download_path}")
        return False
        
    # Check file size
    file_size = download_path.stat().st_size
    if file_size < expected_min_size:
        logging.error(f"Downloaded file too small ({file_size} bytes): {download_path}")
        return False
        
    # Additional checks could be added here (checksum, signature, etc.)
    
    return True
```

## Validation Criteria

1. Tool installation should succeed even with temporary network glitches
2. Clear error messages should be provided when installation fails
3. Partial installations should be cleaned up properly
4. Rate limiting should be handled gracefully
5. Alternative download methods should work when API fails

## Progress Status

90% - Implementation of retry logic and improved error handling has been completed. 

The following improvements have been implemented:
1. Added retry_with_backoff function to helpers.py for exponential backoff retry mechanism
2. Improved _get_latest_release method with multiple fallback strategies
3. Added _get_latest_from_tags method as a fallback when API fails
4. Implemented _construct_download_url method for consistent URL generation
5. Added _guess_latest_version method as a last resort
6. Implemented _verify_download method to validate downloaded files
7. Enhanced install_tool method with better error handling and cleanup

## Notes

The implementation has been completed based on the planned approach. Testing is recommended to verify the robustness of the solution with simulated network failures and API rate limiting. 