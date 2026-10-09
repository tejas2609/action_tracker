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

    def has_cycle(self, proposed_edges=()):
        """Kahn's algorithm: O(V + E), including a whole review batch."""
        from collections import deque

        adjacency = {key: set(value) for key, value in self.downstream.items()}
        for prerequisite, child in proposed_edges:
            adjacency.setdefault(prerequisite, set()).add(child)
        nodes = set(adjacency)
        for children in adjacency.values():
            nodes.update(children)
        indegree = dict.fromkeys(nodes, 0)
        for children in adjacency.values():
            for child in children:
                indegree[child] += 1
        ready = deque(node for node, count in indegree.items() if count == 0)
        visited = 0
        while ready:
            node = ready.popleft()
            visited += 1
            for child in adjacency.get(node, ()):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        return visited != len(nodes)
