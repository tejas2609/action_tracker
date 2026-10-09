"""Database filtering/risk expressions; serialization only touches the page."""

from datetime import date
from sqlalchemy import select, exists, case, and_, or_, func, literal
from sqlalchemy.orm import aliased
from app.models.entities import Commitment as C, Dependency as D
from app.services.commitments.intelligence import serialize
from app.core.config import settings
from app.services.commitments.dependency_graph import DependencyGraph


class CommitmentRepository:
    def __init__(self, db, actor):
        self.db, self.actor = db, actor

    def expressions(self):
        pre = aliased(C)
        pending = exists(
            select(1)
            .select_from(D)
            .join(pre, pre.id == D.prerequisite_id)
            .where(
                D.commitment_id == C.id,
                pre.organization_id == self.actor.organization_id,
                pre.status != "completed",
            )
        )
        blocked = or_(
            C.blocker != "",
            and_(C.condition != "", C.condition_met.is_(False)),
            pending,
        )
        overdue = and_(C.due_date.is_not(None), C.due_date < date.today())
        soon = C.due_date <= date.today().fromordinal(date.today().toordinal() + 3)
        level = case(
            (C.status.in_(["completed", "cancelled"]), literal("low")),
            (or_(overdue, and_(blocked, soon)), literal("high")),
            (or_(blocked, and_(soon, C.progress < 80)), literal("medium")),
            else_=literal("low"),
        )
        state = case(
            (C.status.in_(["completed", "cancelled"]), C.status),
            (blocked, literal("waiting")),
            (overdue, literal("overdue")),
            else_=literal("on-track"),
        )
        return blocked, overdue, level, state

    def base(self):
        return select(C).where(
            C.organization_id == self.actor.organization_id, C.status != "review"
        )

    def filtered(self, scope="mine", q="", state="all"):
        query = self.base().where(C.status != "cancelled")
        if scope == "mine":
            query = query.where(C.owner_id == self.actor.id)
        if q:
            query = query.where(
                or_(
                    C.title.ilike("%" + q + "%", escape="\\"),
                    C.owner.ilike("%" + q + "%", escape="\\"),
                )
            )
        blocked, overdue, level, risk_state = self.expressions()
        if state == "overdue":
            query = query.where(C.status == "active", overdue)
        elif state == "attention":
            query = query.where(C.status == "active", level != "low")
        elif state != "all":
            query = query.where(
                or_(C.status == state, level == state, risk_state == state)
            )
        priority = case((level == "high", 0), (level == "medium", 1), else_=2)
        return query.order_by(priority, C.due_date.asc().nullslast(), C.id)

    def serialize_page(self, tasks, include_impact=True):
        ids = [c.id for c in tasks]
        rows = {c.id: c for c in tasks}
        edges = (
            list(self.db.scalars(select(D).where(D.commitment_id.in_(ids))))
            if ids
            else []
        )
        pre_ids = {edge.prerequisite_id for edge in edges} - set(ids)
        if pre_ids:
            rows.update(
                {c.id: c for c in self.db.scalars(self.base().where(C.id.in_(pre_ids)))}
            )
        graph = DependencyGraph(edges)
        items = [serialize(c, rows, graph, include_impact=False) for c in tasks]
        if include_impact and ids:
            # One recursive query for the page; UNION prevents cyclic revisits.
            walk = (
                select(D.prerequisite_id.label("root"), D.commitment_id.label("child"))
                .join(C, C.id == D.commitment_id)
                .where(
                    D.prerequisite_id.in_(ids),
                    C.organization_id == self.actor.organization_id,
                    C.status != "review",
                )
                .cte("impact_walk", recursive=True)
            )
            walk = walk.union(
                select(walk.c.root, D.commitment_id)
                .join(D, D.prerequisite_id == walk.c.child)
                .join(C, C.id == D.commitment_id)
                .where(
                    C.organization_id == self.actor.organization_id,
                    C.status != "review",
                )
            )
            impacts = {identifier: [] for identifier in ids}
            for root, child in self.db.execute(
                select(walk.c.root, walk.c.child).limit(settings.max_graph_nodes + 1)
            ):
                if child != root:
                    impacts[root].append(child)
            truncated = (
                sum(len(value) for value in impacts.values()) > settings.max_graph_nodes
            )
            for item in items:
                item["impact"] = sorted(impacts[item["id"]])[: settings.max_graph_nodes]
                item["impact_truncated"] = truncated
        return items

    def page(self, query, page, page_size, clamp=False):
        total = self.db.scalar(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        if clamp:
            page = min(page, max(1, (total + page_size - 1) // page_size))
        tasks = list(
            self.db.scalars(query.offset((page - 1) * page_size).limit(page_size))
        )
        return {
            "items": self.serialize_page(tasks),
            "total": total,
            "page": page,
            "page_size": page_size,
        }
