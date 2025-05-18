# Technical Decisions

This document logs key technical and design decisions made during the development of AutoSubNuclei.

## Core Architecture Decisions

### D001: Modular Component Structure

**Decision**: Organize the codebase into modular components (scanner, tool manager, config manager, notifier).

**Context**: Need to manage complexity and enable maintainability as the project grows.

**Alternatives Considered**:
- Single file script (simpler but harder to maintain)
- Microservices (overkill for this application)

**Rationale**: A modular design allows for better separation of concerns, easier testing, and clearer code organization without the complexity of a distributed system.

**Implications**:
- More files and directories to manage
- Clear boundaries between components
- Improved testability
- Better maintainability

**Stakeholders**: Core developers, contributors

## Technical Implementation Decisions

### D002: Asynchronous Processing

**Decision**: Use Python's asyncio for concurrency rather than threading or multiprocessing.

**Context**: Need to handle multiple concurrent operations efficiently, especially for HTTP operations and external tool execution.

**Alternatives Considered**:
- Threading (GIL limitations)
- Multiprocessing (higher overhead)
- Third-party async libraries

**Rationale**: Asyncio provides non-blocking I/O operations with less overhead than multiprocessing and avoids GIL limitations for I/O-bound operations.

**Implications**:
- More complex code structure
- Learning curve for contributors
- Better performance for I/O-bound operations
- Lower memory footprint than multiprocessing

**Stakeholders**: Core developers

### D003: Local Tool Installation

**Decision**: Automatically download and manage security tools locally rather than requiring pre-installation.

**Context**: Need to ensure users can quickly get started without manual tool installation.

**Alternatives Considered**:
- Require manual tool installation
- Use Docker containers
- Use web APIs for scanning

**Rationale**: Automatic tool installation provides the best balance of ease-of-use and functionality while maintaining a self-contained system.

**Implications**:
- Need to maintain tool downloading and installation logic
- Version compatibility concerns
- Works offline after initial download
- No reliance on external services

**Stakeholders**: Users, core developers

### D004: Command-Line Interface with Click

**Decision**: Use Click framework for building the command-line interface.

**Context**: Need a robust and user-friendly CLI that supports nested commands and good help text.

**Alternatives Considered**:
- Standard argparse
- Typer
- Custom CLI implementation

**Rationale**: Click provides a more intuitive API, better documentation capabilities, and more robust parameter handling than alternatives.

**Implications**:
- External dependency
- Better help text generation
- More intuitive command hierarchy
- Type validation built-in

**Stakeholders**: Users, developers

## Configuration and Data Management

### D005: JSON Configuration Format

**Decision**: Use JSON for configuration storage.

**Context**: Need a human-readable configuration format that's also easy to parse programmatically.

**Alternatives Considered**:
- YAML (more complex parsing)
- INI (limited structure)
- Environment variables (less persistent)
- Database (overkill)

**Rationale**: JSON provides a good balance of human readability and programmatic simplicity, with native Python support.

**Implications**:
- Simple to implement
- Easy for users to manually edit
- No schema validation built-in
- Widely supported format

**Stakeholders**: Users, developers

### D006: Local State Storage

**Decision**: Store scan state in JSON files within the output directory.

**Context**: Need to persist scan state for reporting and potential resumption.

**Alternatives Considered**:
- Database (overkill for simple state)
- Memory-only (lost on termination)
- Central state file (concurrency issues)

**Rationale**: Per-scan state files provide isolation between scans and keep state with results for better organization.

**Implications**:
- State tied to results
- No database dependency
- Simple implementation
- File I/O overhead

**Stakeholders**: Users, developers

## Current Development Decisions

### D007: High-Priority Fixes

**Decision**: Prioritize fixing configuration file path handling, Windows PATH issues, and error handling improvements.

**Context**: Need to address core reliability issues before adding new features.

**Alternatives Considered**:
- Focus on new features
- Complete rewrite of problematic components
- Defer fixes for later

**Rationale**: Improving reliability and fixing core issues will benefit all users and provide a solid foundation for future enhancements.

**Implications**:
- Delay in new feature development
- Improved stability for all users
- Better cross-platform compatibility
- More robust operation

**Stakeholders**: Users, developers 