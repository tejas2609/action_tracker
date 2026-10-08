from datetime import date

from .domain import agenda_state, detail


def summary(row):
    state = agenda_state(
        row["review_state"],
        row["total"],
        row["completed"],
    )

    return {
        "id": row["id"],
        "title": row["title"],
        "held_on": row["held_on"],
        "review_state": row["review_state"],
        "agenda_state": state,
        "total": row["total"],
        "completed": row["completed"],
        "progress": (
            100 if state == "completed" else min(99, round(float(row["progress"]), 1))
        ),
    }


class AgendaService:
    def __init__(self, repository):
        self.repository = repository

    def list(self, tab, page, page_size):
        rows, total = self.repository.summaries(
            tab,
            page,
            page_size,
        )

        return {
            "items": [summary(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def detail(self, meeting_id):
        meeting, tasks, member_ids, edges, titles = self.repository.snapshot(meeting_id)

        members = [task for task in tasks if task.id in member_ids]

        completed = sum(task.status == "completed" for task in members)

        progress = sum(
            100 if task.status == "completed" else task.progress for task in members
        ) / max(1, len(members))

        result = summary(
            {
                "id": meeting.id,
                "title": meeting.title,
                "held_on": meeting.held_on,
                "review_state": meeting.state,
                "total": len(members),
                "completed": completed,
                "progress": progress,
            }
        )

        result.update(
            detail(
                tasks,
                member_ids,
                edges,
                titles,
                meeting_id,
                date.today(),
            )
        )

        if meeting.state != "reviewed":
            result["next_steps"].insert(
                0,
                "Finish reviewing extracted commitments before treating "
                "this agenda as final.",
            )

        return result
