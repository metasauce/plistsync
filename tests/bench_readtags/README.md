# Benchmark of some ID3 readers

This folder holds a simple benchmarks for common ID3 readers in Python. As we are only reading tags at the moment, we only benchmark the reading speed.

Benchmark layout:
- 'test_files': Folder with real music files (place some from your collection here!)
    I normally use 100-1000 mp3 and flac files from my collection

- using `pytest-benchmark` for benchmarking


Install dependencies:
```bash
pip install -e .[bench]
```