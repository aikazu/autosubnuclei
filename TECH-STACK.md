# AutoSubNuclei Technology Stack

This document outlines the complete technology stack used in the AutoSubNuclei project, including languages, frameworks, libraries, and external tools.

## Languages

| Language | Version | Usage | Justification |
|----------|---------|-------|---------------|
| Python | >=3.7 | Core application | Modern language with strong async support and rich ecosystem for security tools |

## Frameworks and Libraries

### Core Dependencies

| Library | Version | Purpose | Justification |
|---------|---------|---------|---------------|
| Click | >=8.0.0 | Command-line interface | Provides elegant, composable command line interface with minimal code |
| Asyncio | Built-in | Asynchronous I/O | Native Python library for non-blocking operations, essential for performance |
| Pydantic | >=1.9.0 | Data validation | Enforces data types and validates input/configuration |
| Requests | >=2.25.1 | HTTP client | Industry-standard HTTP library for API interactions and downloads |
| Aiohttp | >=3.8.1 | Async HTTP client | Asyncio-compatible HTTP client for non-blocking requests |
| Tqdm | >=4.61.0 | Progress indicators | Provides real-time progress feedback with minimal overhead |
| Tabulate | >=0.8.9 | Formatted output | Creates clean, aligned tables for result reporting |
| Urllib3 | >=1.26.7 | HTTP client utilities | Provides robust HTTP functionality, used by Requests |
| Colorama | >=0.4.4 | Terminal colors | Cross-platform terminal color support |
| Rich | >=10.9.0 | Terminal formatting | Advanced terminal formatting for better user experience |
| Structlog | >=21.1.0 | Structured logging | Provides structured, contextual logs for better debugging |

### Development Dependencies

| Library | Version | Purpose | Justification |
|---------|---------|---------|---------------|
| Pytest | >=6.2.5 | Testing | Industry standard for Python testing |
| Flake8 | >=3.9.2 | Code linting | Enforces code style and quality standards |
| Black | >=21.5b2 | Code formatting | Consistent code formatting without debate |
| Mypy | >=0.812 | Static type checking | Catches type-related errors before runtime |

## External Tools

| Tool | Purpose | Integration Method | Alternatives Considered |
|------|---------|-------------------|------------------------|
| Subfinder | Subdomain discovery | Automated download, external process execution | Amass, Assetfinder |
| Httpx | HTTP probe and analysis | Automated download, external process execution | HTTProbe, Nmap |
| Nuclei | Vulnerability scanning | Automated download, external process execution | Nessus, OpenVAS |

## Development Tools

| Tool | Purpose | Justification |
|------|---------|---------------|
| Git | Version control | Industry standard, distributed workflow |
| GitHub Actions | CI/CD | Seamless integration with GitHub repository |
| VSCode | IDE | Modern editor with excellent Python support |
| Pre-commit | Git hooks | Automates checks before commits |

## Build and Deployment

| Tool | Purpose | Justification |
|------|---------|---------------|
| Pip | Package management | Standard Python package manager |
| Virtual Environment | Dependency isolation | Prevents conflicts with system packages |
| PyInstaller | Binary creation | Creates standalone executables for distribution |

## Third-party Services

| Service | Purpose | Justification |
|---------|---------|---------------|
| Discord | Notifications | Popular platform with easy webhook integration |
| GitHub API | Release monitoring | Used to check for tool updates |

## Technology Stack Decisions

### Python vs. Go
While many security tools are written in Go, we chose Python for AutoSubNuclei because:
- Easier to extend and maintain
- Richer ecosystem for rapid development
- Strong async capabilities with asyncio
- Better cross-platform compatibility without compilation

### Click vs. Argparse
Click was selected over the standard library Argparse for CLI handling because:
- More intuitive API with decorators
- Better support for nested commands
- Superior help text generation
- Parameter type validation built-in

### Requests vs. Urllib
Requests was chosen as the primary HTTP client library because:
- More intuitive API
- Better error handling
- Session management
- Wide adoption and community support

### External Tools vs. Native Implementation
We chose to integrate external tools rather than implement functionality natively:
- Leverages specialized, actively maintained security tools
- Reduces maintenance burden
- Benefits from community-contributed updates
- Allows focus on integration and workflow optimization 