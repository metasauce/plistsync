# Debugging

```python
import logging

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-25s | %(filename)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)
```
