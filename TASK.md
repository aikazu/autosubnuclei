# AutoSubNuclei Tasks

## Active Tasks

| Task ID | Description | Priority | Complexity | Status | Dependencies | Associated Files | Expected Outcome | Progress | Notes |
|---------|-------------|----------|------------|--------|--------------|-----------------|-----------------|----------|-------|
| T001 | Improve error handling in tool installation | High | Medium | In Progress | - | autosubnuclei/utils/tool_manager.py | More robust error recovery when tool installation fails | 90% | Added retry mechanism and improved error handling |
| T002 | Optimize memory usage for large scans | Medium | Complex | To Do | - | autosubnuclei/core/scanner.py | Reduced memory footprint for large domain lists | 20% | Currently testing with profiler |
| T003 | Fix configuration file path handling | High | Simple | In Progress | - | autosubnuclei/config/config_manager.py | Config file correctly located regardless of execution directory | 90% | Implemented config file path discovery and resolution |
| T004 | Add more detailed logging | Medium | Medium | To Do | - | Multiple | Comprehensive logging throughout application | 10% | Start with core module first |
| T005 | Implement scan resume functionality | Medium | Complex | To Do | - | autosubnuclei/core/scanner.py | Ability to resume interrupted scans | 0% | Need to design state persistence |
| T006 | Refactor notification system | Low | Medium | To Do | - | autosubnuclei/utils/notifier.py | Support for additional notification channels | 0% | Consider plugin architecture |
| T007 | Fix tool path issues on Windows | High | Medium | To Do | - | autosubnuclei/utils/tool_manager.py | Correct PATH handling on Windows | 0% | Test on different Windows versions |
| T008 | Add result filtering options | Low | Simple | To Do | - | autosubnuclei.py | Ability to filter results by criteria | 0% | - |

## Backlog Tasks

| Task ID | Description | Priority | Complexity | Dependencies | Expected Outcome |
|---------|-------------|----------|------------|--------------|------------------|
| T009 | Web interface for scan management | Low | Complex | - | Simple web UI for managing scans |
| T010 | Add scan scheduling | Low | Medium | - | Ability to schedule scans at specific times |
| T011 | Implement result comparison | Low | Medium | - | Compare results between different scans |
| T012 | Support for custom Nuclei templates | Medium | Simple | - | Easy integration of user-provided templates |
| T013 | Add report generation | Medium | Medium | - | Generate PDF/HTML reports from scan results |
| T014 | Create Docker container | Low | Medium | - | Containerized version of the tool |
| T015 | Implement scan profiles | Medium | Medium | - | Predefined scan configurations for different scenarios |

## Completed Tasks

| Task ID | Description | Completion Date | Associated Files | Notes |
|---------|-------------|-----------------|-----------------|-------|
| C001 | Initial project setup | 2023-10-15 | All | Basic project structure and core functionality |
| C002 | Implement asynchronous scanning | 2023-10-22 | autosubnuclei/core/scanner.py | Improved performance by 60% |
| C003 | Add progress indicators | 2023-10-28 | autosubnuclei.py | Provides real-time feedback during scans |
| C004 | Implement caching mechanism | 2023-11-05 | autosubnuclei/core/scanner.py | Faster repeat scans |
| C005 | Add Discord notifications | 2023-11-15 | autosubnuclei/utils/notifier.py | Real-time scan updates |

## Current Sprint: Phase 2 Completion

**Sprint Goal**: Complete error handling improvements and optimize resource usage

**Start Date**: 2023-12-10

**End Date**: 2023-12-24

**Focus Areas**:
- Error handling robustness
- Memory optimization
- Configuration management
- Logging enhancements

## Known Blockers/Impediments

- **B001**: Limited testing on macOS platform
- **B002**: GitHub API rate limiting affecting tool updates

---

## Session Boundaries

### Session: 2023-12-15
- Worked on T001: Added better exception handling in tool_manager.py
- Started investigating T002: Identified memory leaks in scanner.py

### Session: 2023-12-18
- Continued T002: Implemented batch processing for large domain lists
- Started T003: Fixed path handling issues in config_manager.py 