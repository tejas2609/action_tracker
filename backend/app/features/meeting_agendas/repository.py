from sqlalchemy import select, union, func, case
from sqlalchemy.orm import aliased
from app.services.meetings.meeting_access_policy import readable_condition

from app.models.entities import Meeting, Commitment, Dependency, Event

from .domain import Task


class AgendaRepository:
    def __init__(self, store):
        self.store = store
        self.db = store.db
        self.org = store.actor.organization_id

    def membership(self):
        # Commitments created directly for the meeting.
        direct = select(
            Commitment.meeting_id.label("meeting_id"),
            Commitment.id.label("commitment_id"),
        ).where(
            Commitment.organization_id == self.org,
            Commitment.status != "review",
            Commitment.meeting_id.is_not(None),
        )

        # Existing commitments linked during meeting review.
        linked = (
            select(
                Event.meeting_id.label("meeting_id"),
                Commitment.id.label("commitment_id"),
            )
            .join(
                Commitment,
                Commitment.id == Event.commitment_id,
            )
            .where(
                Commitment.organization_id == self.org,
                Commitment.status != "review",
                Event.kind == "meeting_mention",
                Event.meeting_id.is_not(None),
            )
        )

        # UNION deduplicates repeated mentions and direct/linked overlap.
        return union(direct, linked).subquery()

    def summaries(self, tab, page, page_size):
        links = self.membership()

        stats = (
            select(
                links.c.meeting_id,
                func.count().label("total"),
                func.sum(
                    case(
                        (Commitment.status == "completed", 1),
                        else_=0,
                    )
                ).label("completed"),
                func.avg(
                    case(
                        (Commitment.status == "completed", 100),
                        else_=Commitment.progress,
                    )
                ).label("progress"),
            )
            .join(
                Commitment,
                Commitment.id == links.c.commitment_id,
            )
            .group_by(links.c.meeting_id)
            .subquery()
        )

        total = func.coalesce(stats.c.total, 0)
        completed = func.coalesce(stats.c.completed, 0)

        is_completed = (
            (Meeting.state == "reviewed") & (total > 0) & (total == completed)
        )

        query = (
            select(
                Meeting.id,
                Meeting.title,
                Meeting.held_on,
                Meeting.state.label("review_state"),
                total.label("total"),
                completed.label("completed"),
                func.coalesce(stats.c.progress, 0).label("progress"),
            )
            .outerjoin(
                stats,
                stats.c.meeting_id == Meeting.id,
            )
            .where(
                readable_condition(self.store.actor),
            )
        )

        query = query.where(is_completed if tab == "completed" else ~is_completed)

        count = self.db.scalar(select(func.count()).select_from(query.subquery()))

        rows = self.db.execute(
            query.order_by(Meeting.held_on.desc(), Meeting.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).mappings()

        return [dict(row) for row in rows], count

    def snapshot(self, meeting_id):
        # Existing Store.get checks access to this meeting.
        meeting = self.store.get(Meeting, meeting_id)
        links = self.membership()

        member_ids = set(
            self.db.scalars(
                select(links.c.commitment_id).where(
                    links.c.meeting_id == meeting_id,
                )
            )
        )

        columns = [
            Commitment.id,
            Commitment.title,
            Commitment.owner,
            Commitment.owner_id,
            Commitment.due_date,
            Commitment.status,
            Commitment.progress,
            Commitment.condition,
            Commitment.condition_met,
            Commitment.blocker,
            Commitment.meeting_id,
        ]

        # Fetch only agenda commitments and their upstream dependencies.
        # Recursive UNION deduplicates IDs and terminates on cycles.
        relevant = (
            select(Commitment.id.label("id"))
            .where(
                Commitment.organization_id == self.org,
                Commitment.status != "review",
                Commitment.id.in_(
                    select(links.c.commitment_id).where(
                        links.c.meeting_id == meeting_id,
                    )
                ),
            )
            .cte("agenda_upstream", recursive=True)
        )

        prerequisite = aliased(Commitment)

        relevant = relevant.union(
            select(Dependency.prerequisite_id.label("id"))
            .join(
                relevant,
                relevant.c.id == Dependency.commitment_id,
            )
            .join(
                prerequisite,
                prerequisite.id == Dependency.prerequisite_id,
            )
            .where(
                prerequisite.organization_id == self.org,
                prerequisite.status != "review",
            )
        )

        relevant_ids = select(relevant.c.id)

        tasks = [
            Task(**dict(row))
            for row in self.db.execute(
                select(*columns).where(
                    Commitment.organization_id == self.org,
                    Commitment.id.in_(relevant_ids),
                )
            ).mappings()
        ]

        prerequisite = aliased(Commitment)
        dependent = aliased(Commitment)

        edges = set(
            self.db.execute(
                select(
                    Dependency.prerequisite_id,
                    Dependency.commitment_id,
                )
                .join(
                    prerequisite,
                    prerequisite.id == Dependency.prerequisite_id,
                )
                .join(
                    dependent,
                    dependent.id == Dependency.commitment_id,
                )
                .where(
                    prerequisite.organization_id == self.org,
                    dependent.organization_id == self.org,
                    prerequisite.status != "review",
                    dependent.status != "review",
                    Dependency.commitment_id.in_(relevant_ids),
                    Dependency.prerequisite_id.in_(relevant_ids),
                )
            ).tuples()
        )

        meeting_ids = {task.meeting_id for task in tasks if task.meeting_id} | {
            meeting_id
        }

        titles = {
            identifier: title
            for identifier, title in self.db.execute(
                select(Meeting.id, Meeting.title).where(
                    readable_condition(self.store.actor),
                    Meeting.id.in_(meeting_ids),
                )
            ).tuples()
        }

        return meeting, tasks, member_ids, edges, titles
