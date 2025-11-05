"""
Tests for DAG (Directed Acyclic Graph) functionality.
"""

import pytest
from glacier.core.dag import DAG, DAGNode
from glacier.core.task import Task


class TestDAG:
    """Tests for DAG class."""

    def test_empty_dag(self):
        """Test creating an empty DAG."""
        dag = DAG()

        assert len(dag.nodes) == 0

    def test_add_node(self):
        """Test adding nodes to DAG."""
        dag = DAG()

        task = Task(lambda: None, name="test_task")
        dag.add_node("task1", task)

        assert "task1" in dag.nodes
        assert dag.nodes["task1"].name == "task1"
        assert dag.nodes["task1"].task == task

    def test_add_edge(self):
        """Test adding edges between nodes."""
        dag = DAG()

        task1 = Task(lambda: None, name="task1")
        task2 = Task(lambda: None, name="task2")

        dag.add_node("task1", task1)
        dag.add_node("task2", task2)
        dag.add_edge("task1", "task2")

        # task2 depends on task1
        assert "task1" in dag.nodes["task2"].dependencies
        assert "task2" in dag.nodes["task1"].dependents

    def test_topological_sort(self):
        """Test topological sorting of DAG."""
        dag = DAG()

        # Create a simple pipeline: task1 -> task2 -> task3
        for i in range(1, 4):
            task = Task(lambda: None, name=f"task{i}")
            dag.add_node(f"task{i}", task)

        dag.add_edge("task1", "task2")
        dag.add_edge("task2", "task3")

        sorted_nodes = dag.topological_sort()

        assert sorted_nodes.index("task1") < sorted_nodes.index("task2")
        assert sorted_nodes.index("task2") < sorted_nodes.index("task3")

    def test_topological_sort_complex(self):
        """Test topological sorting with parallel branches."""
        dag = DAG()

        # Create a diamond-shaped DAG:
        #     task1
        #    /     \
        # task2   task3
        #    \     /
        #     task4

        for i in range(1, 5):
            task = Task(lambda: None, name=f"task{i}")
            dag.add_node(f"task{i}", task)

        dag.add_edge("task1", "task2")
        dag.add_edge("task1", "task3")
        dag.add_edge("task2", "task4")
        dag.add_edge("task3", "task4")

        sorted_nodes = dag.topological_sort()

        # task1 must come first
        assert sorted_nodes[0] == "task1"

        # task4 must come last
        assert sorted_nodes[-1] == "task4"

        # task2 and task3 can be in any order, but both before task4
        assert sorted_nodes.index("task2") < sorted_nodes.index("task4")
        assert sorted_nodes.index("task3") < sorted_nodes.index("task4")

    def test_cycle_detection(self):
        """Test detecting cycles in DAG."""
        dag = DAG()

        # Create a cycle: task1 -> task2 -> task3 -> task1
        for i in range(1, 4):
            task = Task(lambda: None, name=f"task{i}")
            dag.add_node(f"task{i}", task)

        dag.add_edge("task1", "task2")
        dag.add_edge("task2", "task3")
        dag.add_edge("task3", "task1")  # Creates a cycle

        cycle = dag.detect_cycles()

        assert cycle is not None
        # The cycle should contain the problematic nodes

    def test_no_cycle_detection(self):
        """Test that no cycle is detected in valid DAG."""
        dag = DAG()

        for i in range(1, 4):
            task = Task(lambda: None, name=f"task{i}")
            dag.add_node(f"task{i}", task)

        dag.add_edge("task1", "task2")
        dag.add_edge("task2", "task3")

        cycle = dag.detect_cycles()

        assert cycle is None

    def test_execution_levels(self):
        """Test getting execution levels for parallel execution."""
        dag = DAG()

        # Create a DAG with parallel tasks:
        #     task1
        #    /     \
        # task2   task3
        #    \     /
        #     task4

        for i in range(1, 5):
            task = Task(lambda: None, name=f"task{i}")
            dag.add_node(f"task{i}", task)

        dag.add_edge("task1", "task2")
        dag.add_edge("task1", "task3")
        dag.add_edge("task2", "task4")
        dag.add_edge("task3", "task4")

        levels = dag.get_execution_levels()

        # Should have 3 levels
        assert len(levels) == 3

        # Level 0: task1
        assert "task1" in levels[0]

        # Level 1: task2 and task3 (can run in parallel)
        assert set(levels[1]) == {"task2", "task3"}

        # Level 2: task4
        assert "task4" in levels[2]

    def test_dag_to_dict(self):
        """Test converting DAG to dictionary."""
        dag = DAG()

        task1 = Task(lambda: None, name="task1")
        task2 = Task(lambda: None, name="task2")

        dag.add_node("task1", task1)
        dag.add_node("task2", task2)
        dag.add_edge("task1", "task2")

        dag_dict = dag.to_dict()

        assert "nodes" in dag_dict
        assert "edges" in dag_dict
        assert len(dag_dict["nodes"]) == 2
        assert len(dag_dict["edges"]) == 1

    def test_get_dependencies(self):
        """Test getting dependencies of a node."""
        dag = DAG()

        for i in range(1, 4):
            task = Task(lambda: None, name=f"task{i}")
            dag.add_node(f"task{i}", task)

        dag.add_edge("task1", "task3")
        dag.add_edge("task2", "task3")

        deps = dag.get_dependencies("task3")

        assert set(deps) == {"task1", "task2"}

    def test_get_dependents(self):
        """Test getting dependents of a node."""
        dag = DAG()

        for i in range(1, 4):
            task = Task(lambda: None, name=f"task{i}")
            dag.add_node(f"task{i}", task)

        dag.add_edge("task1", "task2")
        dag.add_edge("task1", "task3")

        dependents = dag.get_dependents("task1")

        assert set(dependents) == {"task2", "task3"}
