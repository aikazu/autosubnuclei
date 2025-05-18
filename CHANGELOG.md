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

### Changed
- Improved documentation structure following standardized format
- Updated README to be more concise and focused
- Enhanced configuration file management with multi-location search

### Fixed
- Configuration file path handling to support execution from any directory
- Improved error handling in tool installation with retries and proper cleanup
- Fixed issue with configuration file not being found when run from different locations

### Pending
- Windows PATH handling issues fix
- Memory optimization for large scans
- Additional logging enhancements

## [1.0.0] - 2023-11-20

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