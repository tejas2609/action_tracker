from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    owner: str
    owner_id: str | None
    due_date: date | None
    status: str
    progress: int
    condition: str
    condition_met: bool
    blocker: str
    meeting_id: str | None


def agenda_state(review_state, total, completed):
    if review_state != "reviewed":
        return "awaiting_review"

    if not total:
        return "no_actions"

    return "completed" if completed == total else "active"


def detail(tasks, member_ids, edges, titles, current_id, today):
    by_id = {task.id: task for task in tasks}
    members = {identifier for identifier in member_ids if identifier in by_id}

    incoming = defaultdict(set)
    outgoing = defaultdict(set)

    # Edge direction: prerequisite -> dependent commitment.
    for prerequisite, dependent in edges:
        if prerequisite in by_id and dependent in by_id:
            incoming[dependent].add(prerequisite)
            outgoing[prerequisite].add(dependent)

    # Include all upstream prerequisites, including indirect ones.
    relevant = set(members)
    queue = deque(members)

    while queue:
        for prerequisite in incoming[queue.popleft()]:
            if prerequisite not in relevant:
                relevant.add(prerequisite)
                queue.append(prerequisite)

    def unfinished_prerequisites(identifier):
        return sorted(
            prerequisite
            for prerequisite in incoming[identifier]
            if by_id[prerequisite].status != "completed"
        )

    def task_item(identifier):
        task = by_id[identifier]
        reasons = []
        waiting = unfinished_prerequisites(identifier)

        if waiting:
            reasons.append(
                "Waiting for "
                + "; ".join(by_id[prerequisite].title for prerequisite in waiting)
            )

        if task.blocker.strip():
            reasons.append(task.blocker.strip())

        if task.condition.strip() and not task.condition_met:
            reasons.append("Condition: " + task.condition.strip())

        if task.status == "cancelled":
            reasons.append("Cancelled: replace or resolve this agenda commitment")

        ready = task.status == "active" and not reasons

        return {
            "id": task.id,
            "title": task.title,
            "owner": task.owner,
            "owner_id": task.owner_id,
            "due_date": task.due_date,
            "status": task.status,
            "progress": task.progress,
            "meeting_id": task.meeting_id,
            "meeting_title": titles.get(
                task.meeting_id,
                "Unassigned meeting",
            ),
            "ready": ready,
            "reasons": reasons,
            "external": identifier not in members,
            "prerequisite_ids": waiting,
        }

    pending = [
        identifier for identifier in members if by_id[identifier].status != "completed"
    ]

    candidates = {identifier: task_item(identifier) for identifier in pending}

    ordered = sorted(
        pending,
        key=lambda identifier: (
            not candidates[identifier]["ready"],
            by_id[identifier].due_date or date.max,
            by_id[identifier].owner.casefold(),
            identifier,
        ),
    )

    next_three = [candidates[identifier] for identifier in ordered[:3]]

    next_steps = []

    for task in next_three:
        deadline = (
            f" by {task['due_date']}" if task["due_date"] else " (deadline not set)"
        )

        if task["ready"]:
            next_steps.append(f"{task['owner']}: work on {task['title']}{deadline}.")
        else:
            next_steps.append(
                f"Unblock {task['title']} for {task['owner']}: "
                + "; ".join(task["reasons"])
                + "."
            )

    if not next_steps:
        next_steps = [
            (
                "All linked commitments are completed."
                if members
                else "Review the meeting and confirm its commitments to start tracking."
            )
        ]

    def graph(identifiers):
        return {
            "nodes": [task_item(identifier) for identifier in sorted(identifiers)],
            "edges": [
                {"source": prerequisite, "target": dependent}
                for prerequisite, dependent in sorted(edges)
                if prerequisite in identifiers and dependent in identifiers
            ],
        }

    # Which current agenda commitments depend on each external meeting?
    coverage = defaultdict(set)

    for external_id in relevant - members:
        meeting_id = by_id[external_id].meeting_id

        if not meeting_id or meeting_id == current_id:
            continue

        visited = {external_id}
        queue = deque([external_id])

        while queue:
            identifier = queue.popleft()

            if identifier in members:
                coverage[meeting_id].add(identifier)

            for dependent in outgoing[identifier]:
                if dependent in relevant and dependent not in visited:
                    visited.add(dependent)
                    queue.append(dependent)

    external_meetings = []

    for meeting_id, affected_ids in sorted(coverage.items()):
        external_meetings.append(
            {
                "meeting_id": meeting_id,
                "title": titles.get(meeting_id, "Meeting"),
                "affected_commitments": len(affected_ids),
                "total_commitments": len(members),
                "coverage": (
                    "full" if len(affected_ids) == len(members) else "partial"
                ),
                "pending_prerequisites": sum(
                    by_id[identifier].meeting_id == meeting_id
                    and by_id[identifier].status != "completed"
                    for identifier in relevant - members
                ),
            }
        )

    return {
        "next_actions": next_three,
        "next_steps": next_steps,
        "within": graph(members),
        "across": graph(relevant),
        "external_meetings": external_meetings,
    }
