# SUBTASK-T002: Optimize Memory Usage for Large Scans

## Parent Task Reference
- **Task ID**: T002
- **Description**: Optimize memory usage for large scans
- **Priority**: Medium
- **Status**: In Progress
- **Progress**: 60%

## Subtask Goal
Reduce the memory footprint of the scanner when processing large domain lists, ensuring the application remains efficient and stable during extensive scans.

## Dependencies
None

## Implementation Approach

### Problem Analysis
After reviewing the scanner.py file, several areas with potential memory optimization opportunities have been identified:

1. Large domain lists are held in memory as sets and lists in multiple places
2. All subdomains are processed in memory before being written to temporary files
3. Batch processing exists but could be more memory-efficient
4. Results from subprocesses are loaded entirely into memory
5. There's no streaming processing of large result sets
6. Multiple conversions between sets and lists may be causing memory overhead
7. Temporary files are not cleaned up until the end of processing

### Solution Steps

1. **Implement streaming processing**:
   - Use generators instead of storing complete lists in memory
   - Process subdomain results in a streaming fashion
   - Read/write results incrementally rather than loading everything into memory

2. **Improve batch processing**:
   - Reduce memory overhead between batches
   - Implement better cleanup of resources between batches
   - Store intermediate results on disk instead of memory

3. **Optimize data structures**:
   - Replace memory-intensive sets with disk-backed structures for large domain lists
   - Use iterators instead of building complete lists when possible
   - Minimize conversions between data types

4. **Add memory monitoring**:
   - Track memory usage during execution
   - Implement adaptive batch sizing based on available memory
   - Log memory usage statistics for analysis

5. **Implement early cleanup**:
   - Release resources as soon as they're no longer needed
   - Clear large data structures proactively
   - Use context managers to ensure timely cleanup

## Files to Modify

1. `autosubnuclei/core/scanner.py` - Primary focus

## Implementation Details

### 1. Add Memory Monitoring

First, let's add memory monitoring to track usage during scans:

```python
def _get_memory_usage(self) -> float:
    """
    Get current memory usage in MB.
    """
    import psutil
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024  # Convert to MB
    return memory_mb

def _log_memory_usage(self, label: str) -> None:
    """
    Log current memory usage with a label.
    """
    memory_mb = self._get_memory_usage()
    logger.debug(f"Memory usage at {label}: {memory_mb:.2f} MB")
```

### 2. Implement Streaming Subdomain Processing

Replace the current subdomain handling with a streaming approach:

```python
async def _process_subdomains_stream(self, subdomains_generator):
    """
    Process subdomains as a stream rather than loading all into memory.
    
    Args:
        subdomains_generator: A generator yielding subdomains
        
    Returns:
        Generator yielding processed subdomains
    """
    batch = []
    batch_size = 1000  # Process in smaller batches
    
    for subdomain in subdomains_generator:
        batch.append(subdomain)
        if len(batch) >= batch_size:
            yield from self._process_batch(batch)
            batch = []  # Clear batch after processing
    
    # Process any remaining subdomains
    if batch:
        yield from self._process_batch(batch)
```

### 3. Replace Set Storage with Disk-Backed Storage for Large Lists

For large domain lists, we'll use a disk-backed storage approach:

```python
class DiskBackedSet:
    """
    A set-like object that stores items on disk to reduce memory usage.
    """
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Create empty file if it doesn't exist
        if not self.path.exists():
            with open(self.path, 'w'):
                pass
        
        # In-memory cache for fast membership tests
        # Using a small LRU cache to reduce memory footprint
        self._cache = {}
        self._cache_size = 1000
        
    def add(self, item: str) -> None:
        """Add an item to the set."""
        # Check if the item is already in the set
        if self._in_cache(item) or self._in_file(item):
            return
        
        # Add to file
        with open(self.path, 'a') as f:
            f.write(f"{item}\n")
        
        # Add to cache
        self._add_to_cache(item)
    
    def _add_to_cache(self, item: str) -> None:
        """Add an item to the in-memory cache."""
        # Maintain cache size
        if len(self._cache) >= self._cache_size:
            # Remove oldest item
            self._cache.pop(next(iter(self._cache)))
        
        self._cache[item] = True
    
    def _in_cache(self, item: str) -> bool:
        """Check if an item is in the cache."""
        return item in self._cache
    
    def _in_file(self, item: str) -> bool:
        """Check if an item is in the file."""
        # For very large sets, this could be slow
        # In a real implementation, we might use a bloom filter
        # or other data structure for faster lookups
        with open(self.path, 'r') as f:
            return item in (line.strip() for line in f)
    
    def __iter__(self):
        """Iterate over all items in the set."""
        with open(self.path, 'r') as f:
            for line in f:
                yield line.strip()
    
    def __len__(self):
        """Return the number of items in the set."""
        with open(self.path, 'r') as f:
            return sum(1 for _ in f)
```

### 4. Improve Batch Processing in _run_httpx

Modify the _run_httpx method to use less memory:

```python
async def _run_httpx(self, subdomains) -> str:
    """
    Run httpx to find alive subdomains with concurrent batching and low memory usage.
    Returns a path to a file containing the alive subdomains instead of a set.
    """
    logger.info("Running httpx to find alive subdomains")
    self.scan_state["status"] = "probing_subdomains"
    self._log_memory_usage("before_httpx")
    
    # Create a file to store alive subdomains
    alive_subdomains_file = self.output_dir / "alive_subdomains.txt"
    if alive_subdomains_file.exists():
        alive_subdomains_file.unlink()
    
    # Create a queue for batching
    batch_queue = asyncio.Queue(maxsize=self.max_workers * 2)
    
    # Create a semaphore to limit concurrent tasks
    semaphore = asyncio.Semaphore(self.max_workers)
    
    # Create producer and consumer tasks
    producer_task = asyncio.create_task(self._produce_subdomain_batches(subdomains, batch_queue))
    consumer_tasks = [
        asyncio.create_task(self._consume_subdomain_batches(batch_queue, semaphore, alive_subdomains_file)) 
        for _ in range(self.max_workers)
    ]
    
    # Wait for producer to finish
    await producer_task
    
    # Signal consumers to stop
    for _ in range(self.max_workers):
        await batch_queue.put(None)
    
    # Wait for consumers to finish
    await asyncio.gather(*consumer_tasks)
    
    # Count the alive subdomains
    alive_count = 0
    with open(alive_subdomains_file, 'r') as f:
        alive_count = sum(1 for _ in f)
    
    logger.info(f"Found {alive_count} alive subdomains")
    self.scan_state["alive_subdomains"] = alive_count
    
    # Send notification with a limited number of subdomains to avoid memory issues
    with open(alive_subdomains_file, 'r') as f:
        # Only read the first 1000 for notification
        sample_subdomains = [line.strip() for line in f.readlines()[:1000]]
        self.notifier.send_alive_subdomains(self.domain, sample_subdomains)
    
    self._log_memory_usage("after_httpx")
    return str(alive_subdomains_file)
```

### 5. Update _run_nuclei to Use File-Based Processing

```python
async def _run_nuclei(self, alive_subdomains_file: str, severities: List[str]) -> None:
    """
    Run nuclei scan using a file of alive subdomains instead of a set.
    
    Args:
        alive_subdomains_file: Path to the file containing alive subdomains
        severities: List of severity levels to scan for
    """
    logger.info("Running nuclei scan")
    self.scan_state["status"] = "scanning_vulnerabilities"
    self._log_memory_usage("before_nuclei")
    
    # Verify templates exist before running
    if not self.templates_path.exists():
        logger.error(f"Nuclei templates not found at {self.templates_path}")
        raise FileNotFoundError(f"Templates directory not found: {self.templates_path}")
    
    # Split the subdomains file into smaller chunks for processing
    await self._split_file_and_process(alive_subdomains_file, severities)
    
    self._log_memory_usage("after_nuclei")
```

## Validation Criteria

1. Scanner can process large domain lists (100,000+) without excessive memory usage
2. Memory usage remains stable throughout the scanning process
3. No memory leaks or excessive growth in memory consumption
4. Scan performance does not degrade significantly with memory optimizations
5. All results remain accurate compared to the original implementation

## Progress Status

60% - Memory optimization has been implemented throughout the scanner. Key improvements include:

1. Memory monitoring with psutil integrated into scanner
2. DiskBackedSet implemented for large domain lists
3. Streaming processing of subdomains using iterators
4. Adaptive batch sizing based on current memory usage
5. File-based storage for large result sets
6. Added memory usage logging throughout the scan process

Next steps:
1. Test performance with large domain lists (100,000+ domains)
2. Fine-tune memory thresholds and batch sizing algorithms
3. Add more aggressive memory cleanup
4. Implement early resource release

## Notes

The implementation should focus on reducing peak memory usage rather than just average usage. Special attention should be paid to the `_run_httpx` and `_run_nuclei` methods, which handle the largest datasets. 