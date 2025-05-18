# AutoSubNuclei Architecture

## Architectural Overview

AutoSubNuclei follows a modular architecture designed around the core scanning workflow. The system is structured to provide a smooth transition from subdomain discovery to vulnerability detection through a pipeline of specialized tools.

```
[User] → [CLI] → [SecurityScanner] → [Results]
                      ↓
    [ToolManager] ← [Core Components] → [Notifier]
          ↓               ↓
  [External Tools]    [ConfigManager]
```

## System Components

### A1. Core Components

#### A1.1 SecurityScanner
The central component that orchestrates the entire scanning process. It manages the workflow from subdomain discovery through to vulnerability scanning.

**Responsibilities:**
- Coordinating the scanning pipeline
- Managing state throughout the scan
- Handling batching and parallelism
- Processing and storing results

#### A1.2 ToolManager
Responsible for managing external security tools (Subfinder, Httpx, Nuclei).

**Responsibilities:**
- Downloading and installing tools
- Verifying tool installations
- Updating tools to latest versions
- Adding tools to the system PATH

#### A1.3 ConfigManager
Manages configuration settings and user preferences.

**Responsibilities:**
- Storing and retrieving configuration
- Managing notification settings
- Handling default scan parameters
- Maintaining configuration persistence

#### A1.4 Notifier
Handles notifications to external systems (currently Discord).

**Responsibilities:**
- Sending status updates
- Formatting notification content
- Managing notification preferences

### A2. Command-Line Interface

The CLI is built using Click and provides a user-friendly interface for interacting with the tool.

**Key Commands:**
- `scan`: Run security scan on a domain
- `results`: View scan results for a domain
- `update`: Update security tools and templates
- `setup`: Configure notifications and settings

### A3. Data Flow

1. User initiates scan via CLI
2. SecurityScanner verifies tools and templates
3. Subfinder discovers subdomains
4. Httpx identifies alive hosts
5. Nuclei scans for vulnerabilities
6. Results are processed and stored
7. Notifications are sent at key milestones

## Technical Design Details

### D1. Asynchronous Processing

The system uses Python's asyncio framework to perform non-blocking operations:

- Subdomain discovery operates asynchronously
- HTTP probing runs in parallel for batches of subdomains
- Vulnerability scanning processes multiple hosts concurrently

### D2. Caching Strategy

To improve performance for repeated scans:

- Intermediate results are cached with unique keys
- Cache is stored in a hidden directory within the output folder
- Cache keys are derived from command parameters for deterministic lookup

### D3. Tool Management

External tools are managed with the following approach:

- Tools are downloaded from GitHub releases
- Platform-specific binaries are selected automatically
- Version tracking prevents unnecessary downloads
- PATH integration makes tools available within the application

### D4. Error Handling

The system implements a multi-layered error handling strategy:

- Command-level error catching for user-friendly messages
- Tool-specific error detection and recovery
- Network error handling with retries
- Resource cleanup on interruption

## Performance Considerations

- **Batching**: Large subdomain lists are processed in manageable batches
- **Concurrency Control**: Number of workers is adjusted based on system capabilities
- **Resource Management**: External processes are monitored and limited
- **Caching**: Repeat scans leverage cached results for performance

## Security Architecture

- Configuration with credentials is stored locally
- No data is sent to external services except notifications
- Downloaded tools are verified for integrity
- External tools execute with minimal required permissions

## Design Decisions

| Decision | Alternatives | Rationale |
|----------|--------------|-----------|
| Use Click for CLI | Argparse, Typer | Better documentation, nested commands, parameter validation |
| Asyncio for concurrency | Threading, Multiprocessing | Better I/O performance, simpler coordination |
| Local tool installation | Docker containers, Web API | Self-contained, works offline, no dependencies |
| JSON for configuration | YAML, INI, Database | Simple, human-readable, native Python support |

## Future Architecture Considerations

- Potential migration to plugin architecture for additional tools
- Database integration for result storage and analysis
- API layer for integration with other systems
- Web interface for visualization and management 