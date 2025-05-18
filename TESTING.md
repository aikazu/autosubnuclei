# AutoSubNuclei Testing Strategy

This document outlines the testing approach for AutoSubNuclei, covering test categories, environments, and best practices.

## Testing Approach

AutoSubNuclei follows a mixed testing approach:

- **Manual Testing**: Used for initial development and UI/UX validation
- **Automated Testing**: Used for regression testing and continuous integration
- **Component Testing**: Focused on individual modules and classes
- **Integration Testing**: Tests interactions between components
- **End-to-End Testing**: Validates complete scanning workflow

## Test Environments

| Environment | Purpose | Configuration |
|-------------|---------|---------------|
| Development | Local testing during development | Developer machines with virtual environments |
| CI/CD | Automated testing on pull requests | GitHub Actions runners |
| Staging | Pre-release validation | Similar to production environment |
| Production | Post-deployment validation | Real-world deployment verification |

## Test Categories

### Unit Tests

Unit tests focus on validating individual functions and classes in isolation.

**Key Areas**:
- Configuration management
- Tool installation
- Command parsing
- Result processing

**Framework**: Pytest

**Coverage Goal**: 80% code coverage

**Example Test Case**:
```python
def test_config_manager_load():
    """Test that ConfigManager correctly loads configuration"""
    # Arrange
    config_path = Path("test_config.json")
    with open(config_path, "w") as f:
        json.dump({"test_key": "test_value"}, f)
    
    # Act
    config_manager = ConfigManager(config_path=config_path)
    loaded_config = config_manager.load_config()
    
    # Assert
    assert loaded_config["test_key"] == "test_value"
    
    # Cleanup
    config_path.unlink()
```

### Integration Tests

Integration tests validate the interactions between different components.

**Key Areas**:
- CLI to Core component interaction
- Tool manager to external tools
- Scanner to result storage

**Framework**: Pytest with fixtures

**Coverage Goal**: 70% of component interactions

**Example Test Case**:
```python
@pytest.mark.integration
def test_tool_installation():
    """Test that ToolManager can install and verify tools"""
    # Arrange
    tool_manager = ToolManager(test_mode=True)
    
    # Act
    result = tool_manager.install_tool("test_tool")
    
    # Assert
    assert result is True
    assert tool_manager._is_tool_installed("test_tool")
```

### End-to-End Tests

End-to-end tests validate the complete scanning workflow.

**Key Areas**:
- Full scan process
- Command-line interface
- Result generation

**Framework**: Bash scripts and Python test harness

**Coverage Goal**: All main workflows tested

**Example Test Case**:
```python
@pytest.mark.e2e
def test_basic_scan_workflow():
    """Test complete scan workflow with a test domain"""
    # Arrange
    test_domain = "example.com"
    expected_output_dir = Path("output") / test_domain
    if expected_output_dir.exists():
        shutil.rmtree(expected_output_dir)
    
    # Act
    result = subprocess.run(
        ["python", "autosubnuclei.py", "scan", test_domain, "--no-notify"],
        capture_output=True,
        text=True
    )
    
    # Assert
    assert result.returncode == 0
    assert expected_output_dir.exists()
    assert (expected_output_dir / "scan_state.json").exists()
```

### Performance Tests

Performance tests evaluate the tool's efficiency and resource usage.

**Key Areas**:
- Large domain list handling
- Memory consumption
- CPU utilization
- Scan completion time

**Tools**: cProfile, memory_profiler

**Metrics**:
- Time to scan 100 subdomains
- Peak memory usage
- Scaling with increasing domain count

## Mock Data Strategy

To enable reliable testing without external dependencies:

1. **Mock HTTP Responses**:
   - Use pytest-responses to simulate API calls
   - Predefined JSON responses for GitHub API
   - Simulated tool download endpoints

2. **Mock Tool Execution**:
   - Predefined output for subprocess calls
   - Controllable exit codes and stderr/stdout

3. **Mock Domains and Vulnerabilities**:
   - Set of test domains with known characteristics
   - Predefined vulnerability findings

## Test Automation

Tests are automated through GitHub Actions:

```yaml
name: Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    - name: Run tests
      run: |
        pytest tests/
```

## Test Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| pytest | >=6.2.5 | Test framework |
| pytest-cov | >=2.12.1 | Code coverage |
| pytest-mock | >=3.6.1 | Mocking functionality |
| pytest-responses | >=0.4.0 | HTTP response mocking |
| memory-profiler | >=0.58.0 | Memory profiling |

## Validation Criteria

For a release to pass testing:

1. All unit tests must pass
2. All integration tests must pass
3. All end-to-end tests must pass
4. Code coverage must meet targets
5. No security vulnerabilities in dependencies
6. No regression in performance metrics 