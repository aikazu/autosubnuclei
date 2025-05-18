# Changelog

All notable changes to AutoSubNuclei will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation (README, PLANNING, ARCHITECTURE, etc.)
- Development dependency requirements file
- Testing strategy documentation
- Robust retry mechanism with exponential backoff for network operations
- Multiple fallback strategies for GitHub API failures
- Download verification for tool installations
- Memory monitoring with psutil for adaptive resource usage
- DiskBackedSet implementation for memory-efficient storage of large domain lists
- Streaming processing for subdomain and vulnerability scanning
- Memory-adaptive batch sizing for large scans
- Advanced Windows path handling with PowerShell validation
- Enhanced Windows testing and validation tools

### Changed
- Improved documentation structure following standardized format
- Updated README to be more concise and focused
- Updated all documentation to reflect current project state
- Enhanced configuration file management with multi-location search
- Optimized notification system to handle extremely large result sets
- Modified Nuclei scanning process for significantly reduced memory usage
- Enhanced batch processing with garbage collection and cleanup
- Major code refactoring to reduce nesting complexity in key components:
  - Refactored ToolManager._validate_windows_path using guard clauses and dedicated validation methods
  - Refactored ToolManager._execute_windows_tool with improved path resolution and command execution separation
  - Refactored SecurityScanner._run_httpx with clear separation of resumption, batch processing, and checkpoint logic
  - Refactored SecurityScanner._run_nuclei_in_batches with improved batch file handling and processing logic
  - Refactored ProgressMonitor.update by separating status change and update logic into dedicated methods
  - Refactored CheckpointManager.repair_checkpoint with specialized field validation and repair methods
  - Implemented Strategy pattern for FileLock to properly separate platform-specific code
- Improved PATH environment handling for Windows systems

### Fixed
- Configuration file path handling to support execution from any directory
- Improved error handling in tool installation with retries and proper cleanup
- Fixed issue with configuration file not being found when run from different locations
- Fixed Windows tool path handling and validation issues
- Resolved memory leaks when processing large domain lists
- Addressed excessive memory usage during nuclei scans
- Fixed temporary file cleanup for large scans
- Fixed empty results.txt bug when reporting vulnerabilities found by nuclei

### Pending
- Additional logging enhancements
- Scan resume functionality
- Result filtering options

## [1.0.0]

### Added
- Initial release of AutoSubNuclei
- Subdomain discovery with Subfinder
- HTTP probing with Httpx
- Vulnerability scanning with Nuclei
- Discord notifications
- Automatic tool installation and updates
- Progress indicators
- Caching for faster repeat scans
- Asynchronous processing
- Comprehensive CLI

### Security
- Secure storage of Discord webhook in local configuration 