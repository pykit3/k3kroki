import k3kroki

# Render a Graphviz diagram to SVG bytes
svg = k3kroki.convert("graphviz", "digraph { a -> b }")

# Render a Mermaid diagram and save to file
k3kroki.convert_to_file("mermaid", "graph TD\n  A --> B", "diagram.svg")

# Render PlantUML to PNG
png = k3kroki.convert("plantuml", "@startuml\nAlice -> Bob: hello\n@enduml", "png")
