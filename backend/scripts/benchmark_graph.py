"""CPU-only benchmark; not an HTTP latency benchmark."""

from types import SimpleNamespace
from time import perf_counter
from statistics import median
from app.services.dependency_graph import DependencyGraph


def original(identifier, edges):
    seen, stack = set(), [identifier]
    while stack:
        node = stack.pop()
        for edge in edges:
            if edge.prerequisite_id == node and edge.commitment_id not in seen:
                seen.add(edge.commitment_id)
                stack.append(edge.commitment_id)
    return seen


def benchmark(n=500):
    edges = [
        SimpleNamespace(prerequisite_id=str(i), commitment_id=str(i + 1))
        for i in range(n)
    ]

    def old():
        return [original(str(i), edges) for i in range(n)]

    def new():
        graph = DependencyGraph(edges)
        return [graph.descendants(str(i)) for i in range(n)]

    assert old() == new()
    for label, fn in [("original", old), ("indexed", new)]:
        times = []
        for _ in range(3):
            start = perf_counter()
            fn()
            times.append((perf_counter() - start) * 1000)
        print(
            f"{label}: median {median(times):.2f} ms; 500-node chain, all descendants, 3 runs"
        )


if __name__ == "__main__":
    benchmark()
