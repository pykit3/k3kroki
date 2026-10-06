# k3kroki

[![Action-CI](https://github.com/pykit3/k3kroki/actions/workflows/python-package.yml/badge.svg)](https://github.com/pykit3/k3kroki/actions/workflows/python-package.yml)
[![Documentation Status](https://readthedocs.org/projects/k3kroki/badge/?version=stable)](https://k3kroki.readthedocs.io/en/stable/?badge=stable)
[![Package](https://img.shields.io/pypi/pyversions/k3kroki)](https://pypi.org/project/k3kroki)

Convert diagrams to images via the kroki.io API — zero local dependencies

k3kroki is a component of [pykit3] project: a python3 toolkit set.

k3kroki converts diagrams to images via the free kroki.io HTTP API — no local tools needed.


# Install

```
pip install k3kroki
```

# Synopsis

```python
import k3kroki

# Render a Graphviz diagram to SVG bytes
svg = k3kroki.convert("graphviz", "digraph { a -> b }")

# Render a Mermaid diagram and save to file
k3kroki.convert_to_file("mermaid", "graph TD\n  A --> B", "diagram.svg")

# Render PlantUML to PNG
png = k3kroki.convert("plantuml", "@startuml\nAlice -> Bob: hello\n@enduml", "png")
```

#   Author

Zhang Yanpo (张炎泼) <drdr.xp@gmail.com>

#   Copyright and License

The MIT License (MIT)

Copyright (c) 2015 Zhang Yanpo (张炎泼) <drdr.xp@gmail.com>


[pykit3]: https://github.com/pykit3