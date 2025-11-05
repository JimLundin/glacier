"""
DAG (Directed Acyclic Graph) builder and analyzer for Glacier pipelines.
"""

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque


@dataclass
class DAGNode:
    """Represents a node in the pipeline DAG."""

    name: str
    task: Any
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DAG:
    """
    Directed Acyclic Graph for pipeline task dependencies.

    Provides:
    1. Dependency resolution
    2. Topological sorting
    3. Cycle detection
    4. Visualization support
    """

    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}
        self._adjacency_list: Dict[str, List[str]] = defaultdict(list)
        self._reverse_adjacency_list: Dict[str, List[str]] = defaultdict(list)

    def add_node(self, name: str, task: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a node to the DAG."""
        if name not in self.nodes:
            self.nodes[name] = DAGNode(name=name, task=task, metadata=metadata or {})

    def add_edge(self, from_node: str, to_node: str) -> None:
        """
        Add a directed edge from one node to another.

        Args:
            from_node: The node that the 'to_node' depends on
            to_node: The dependent node
        """
        if from_node not in self.nodes or to_node not in self.nodes:
            raise ValueError(f"Both nodes must exist in DAG before adding edge")

        # Add to adjacency lists
        self._adjacency_list[from_node].append(to_node)
        self._reverse_adjacency_list[to_node].append(from_node)

        # Update node dependencies
        self.nodes[to_node].dependencies.append(from_node)
        self.nodes[from_node].dependents.append(to_node)

    def get_dependencies(self, node_name: str) -> List[str]:
        """Get all nodes that this node depends on."""
        return self.nodes[node_name].dependencies if node_name in self.nodes else []

    def get_dependents(self, node_name: str) -> List[str]:
        """Get all nodes that depend on this node."""
        return self.nodes[node_name].dependents if node_name in self.nodes else []

    def topological_sort(self) -> List[str]:
        """
        Return a topological ordering of the DAG.

        This gives us the order in which tasks should be executed.

        Raises:
            ValueError: If the graph contains cycles
        """
        # Calculate in-degrees
        in_degree = {node: 0 for node in self.nodes}
        for node in self.nodes:
            for dependent in self._adjacency_list[node]:
                in_degree[dependent] += 1

        # Queue of nodes with no dependencies
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            # Reduce in-degree for dependents
            for dependent in self._adjacency_list[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for cycles
        if len(result) != len(self.nodes):
            raise ValueError("DAG contains cycles - cannot perform topological sort")

        return result

    def detect_cycles(self) -> Optional[List[str]]:
        """
        Detect if there are any cycles in the DAG.

        Returns:
            A cycle path if one exists, None otherwise
        """
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self._adjacency_list[node]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]

            path.pop()
            rec_stack.remove(node)
            return False

        for node in self.nodes:
            if node not in visited:
                cycle = dfs(node)
                if cycle:
                    return cycle

        return None

    def get_execution_levels(self) -> List[List[str]]:
        """
        Get execution levels for parallel execution.

        Returns a list of lists, where each inner list contains tasks
        that can be executed in parallel (have no dependencies on each other).
        """
        sorted_nodes = self.topological_sort()
        levels = []
        processed = set()

        for node in sorted_nodes:
            # Find the appropriate level for this node
            dependencies = set(self.get_dependencies(node))
            level_idx = 0

            # Node must be placed after all its dependencies
            for i, level in enumerate(levels):
                if dependencies.intersection(level):
                    level_idx = i + 1

            # Add new level if needed
            while len(levels) <= level_idx:
                levels.append([])

            levels[level_idx].append(node)
            processed.add(node)

        return levels

    def to_dict(self) -> Dict[str, Any]:
        """Convert DAG to dictionary representation for serialization."""
        return {
            "nodes": [
                {
                    "name": node.name,
                    "dependencies": node.dependencies,
                    "dependents": node.dependents,
                    "metadata": node.metadata,
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {"from": from_node, "to": to_node}
                for from_node, to_nodes in self._adjacency_list.items()
                for to_node in to_nodes
            ],
        }

    def __repr__(self) -> str:
        return f"DAG(nodes={len(self.nodes)}, edges={sum(len(deps) for deps in self._adjacency_list.values())})"
