"""Request-local adjacency indexes. Never cache across database mutations."""

from collections import defaultdict


class DependencyGraph:
    def __init__(self, edges):
        self.edges = tuple(edges)
        self.upstream = defaultdict(list)
        self.downstream = defaultdict(list)
        for edge in self.edges:
            self.upstream[edge.commitment_id].append(edge.prerequisite_id)
            self.downstream[edge.prerequisite_id].append(edge.commitment_id)

    def __iter__(self):
        return iter(self.edges)

    def descendants(self, identifier):
        seen, stack = set(), [identifier]
        while stack:
            for child in self.downstream.get(stack.pop(), ()):
                if child not in seen:
                    seen.add(child)
                    stack.append(child)
        return seen
