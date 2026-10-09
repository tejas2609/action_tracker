from fastapi import HTTPException
from app.models.entities import Commitment, Dependency
from sqlalchemy import select
from app.services.commitments.intelligence import serialize, assess, descendants
from app.services.commitments.dependency_graph import DependencyGraph


class GraphWorkflow:
    def snapshot(self, identifiers=None):
        from app.core.config import settings
        from sqlalchemy import or_

        if identifiers is None:
            tasks = self.s.all(Commitment, limit=settings.max_graph_nodes + 1)
            if len(tasks) > settings.max_graph_nodes:
                raise HTTPException(
                    413, "Graph exceeds configured node limit; use filtered task lists"
                )
            rows = {c.id: c for c in tasks}
            edges = DependencyGraph(self.s.all(Dependency))
            return rows, edges
        # Connected component only, with bounded breadth-first expansion.
        rows, edges, seen = {}, {}, set()
        frontier = set(identifiers)
        while frontier:
            if len(seen | frontier) > settings.max_graph_nodes:
                raise HTTPException(
                    413, "Connected graph exceeds configured node limit"
                )
            tasks = list(
                self.s.db.scalars(
                    select(Commitment).where(
                        Commitment.id.in_(frontier),
                        Commitment.organization_id == self.s.actor.organization_id,
                        Commitment.status != "review",
                    )
                )
            )
            permitted = {c.id for c in tasks}
            rows.update({c.id: c for c in tasks})
            seen.update(frontier)
            links = list(
                self.s.db.scalars(
                    select(Dependency).where(
                        or_(
                            Dependency.commitment_id.in_(permitted),
                            Dependency.prerequisite_id.in_(permitted),
                        )
                    )
                )
            )
            frontier = set()
            for edge in links:
                edges[(edge.commitment_id, edge.prerequisite_id)] = edge
                frontier.update({edge.commitment_id, edge.prerequisite_id} - seen)
        return rows, DependencyGraph(
            e
            for e in edges.values()
            if e.commitment_id in rows and e.prerequisite_id in rows
        )

    def risk_levels(self, identifiers=None):
        rows, edges = self.snapshot(identifiers)
        return {id: assess(c, rows, edges)["level"] for id, c in rows.items()}

    def audit_risks(self, before):
        rows, edges = self.snapshot(list(before)) if self.s.actor else self.snapshot()
        for id, c in rows.items():
            level = assess(c, rows, edges)["level"]
            if id in before and before[id] != level:
                self.s.event(c, "risk_change", before[id] + " → " + level)

    def listing(self, include_impact=True, snapshot=None):
        rows, edges = snapshot or self.snapshot()
        return sorted(
            [
                serialize(c, rows, edges, include_impact=include_impact)
                for c in rows.values()
            ],
            key=lambda c: (
                {"high": 0, "medium": 1, "low": 2}[c["risk"]["level"]],
                str(c["due_date"] or "9999"),
            ),
        )

    def edge(self, id, pre):
        from app.core.concurrency import lock_organization

        lock_organization(self.s.db, self.s.actor.organization_id)
        self.s.db.expire_all()
        self.s.get(Commitment, id)
        self.s.get(Commitment, pre)
        rows, edges = self.snapshot([id, pre])
        if id == pre or pre in descendants(id, edges):
            raise HTTPException(422, "Dependency would create a cycle.")
        if self.s.db.get(Dependency, (id, pre)):
            return
        before = self.risk_levels([id, pre])
        self.s.save(Dependency(commitment_id=id, prerequisite_id=pre))
        self.s.event(rows[id], "dependency_added", "Waiting for " + rows[pre].title)
        self.audit_risks(before)
        self.s.db.commit()
