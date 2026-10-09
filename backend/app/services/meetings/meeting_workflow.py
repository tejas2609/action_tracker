from fastapi import HTTPException
from pydantic import ValidationError
from app.models.entities import Meeting, Commitment, Dependency
from app.schemas.contracts import Findings
from app.models.people import User
from sqlalchemy import select, func

EXTRACT = """
Extract work commitments from the numbered meeting transcript.

Read the entire conversation before extracting anything.

A work commitment is a speaker accepting responsibility for a specific
action. Examples include "I'll send the list tomorrow" and "Once QA
approves, I'll deploy." Conditional promises are still commitments.

Do not extract jokes, personal plans, suggestions, requests that nobody
accepted, or statements explicitly refusing to commit.

For each genuine commitment:
- owner: the speaker who accepted responsibility, not someone they mentioned.
- title: a concise description of the promised action.
- source_line: the supplied line number containing that promise.
- statement: use the literal string "source"; the backend copies the line.
- due_date: the FINAL agreed calendar date in YYYY-MM-DD, or null if unknown.
- condition: prerequisites and relative timing, if any.
- explanation: relevant corrections, conditions and time of day.
- existing_id: a matching supplied commitment ID, otherwise null.
- depends_on_indices: prerequisite indices in your final findings array.
- prerequisite_ids: IDs of existing prerequisite commitments.
- confidence: a number between 0 and 1.

When a deadline is proposed, challenged later, and finally agreed:
extract ONE commitment with the final accepted deadline.
Repeated mentions of the same promise are not separate commitments.
Do not assign promises to absent people unless they actually made them
in the supplied transcript.

Use held_on to resolve relative dates.
Do not invent dates for promises whose timing depends on an unknown event.

Return:
{
  "findings": [
    {
      "kind": "commitment",
      "title": "Promised action",
      "owner": "Speaker",
      "source_line": 1,
      "statement": "source",
      "due_date": null,
      "condition": "",
      "confidence": 0.9,
      "explanation": "",
      "existing_id": null,
      "depends_on_indices": [],
      "prerequisite_ids": []
    }
  ]
}

Return an empty findings array only when there are no genuine work promises.
Before returning an empty array, recheck every speaker turn for accepted
actions and conditional promises.
Return JSON only.
"""


class MeetingWorkflow:
    def resolve_owner(self, name, id=None):
        org = self.s.actor.organization_id
        if id:
            user = self.s.db.get(User, id)
            if not user or user.organization_id != org or not user.active:
                raise HTTPException(422, "Owner must be an active organization user.")
            return user.id
        users = list(
            self.s.db.scalars(
                select(User)
                .where(
                    User.organization_id == org,
                    User.active.is_(True),
                    func.lower(func.trim(User.name)) == name.strip().lower(),
                )
                .limit(2)
            )
        )
        matches = [
            u for u in users if u.name.strip().casefold() == name.strip().casefold()
        ]
        if len(matches) == 1:
            return matches[0].id
        raise HTTPException(422, "Select an organization user for owner " + name)

    def _meeting_candidates(self, transcript):
        from app.services.sources.source_candidates import find_candidates
        from app.core.config import settings

        rows = find_candidates(
            self.s.db,
            self.s.actor,
            transcript,
            organization_wide=True,
            limit=settings.ai_candidate_limit,
        )
        return [
            {
                k: getattr(row, k)
                for k in ("id", "title", "owner", "due_date", "condition", "status")
            }
            for row in rows
        ]

    async def analyze(self, id):
        m = self.s.get(Meeting, id)
        if m.state == "reviewed":
            raise HTTPException(409, "This meeting has already been reviewed.")
        lines = m.transcript.splitlines()
        payload = {
            "held_on": m.held_on,
            "transcript_lines": [
                {"line": i, "text": text}
                for i, text in enumerate(lines, 1)
                if text.strip()
            ],
            "existing": [
                {
                    k: item[k]
                    for k in ("id", "title", "owner", "due_date", "condition", "status")
                }
                for item in self._meeting_candidates(m.transcript)
            ],
        }

        raw = await self.ai.json(EXTRACT, payload)

        try:
            findings = Findings.model_validate(raw)
        except ValidationError as e:
            raise HTTPException(
                502, "AI result failed validation; retry analysis."
            ) from e
        for f in findings.findings:
            if f.source_line is not None:
                if f.source_line > len(lines) or not lines[f.source_line - 1].strip():
                    raise HTTPException(502, "AI selected an invalid source line.")
                f.statement = lines[f.source_line - 1]
            elif f.statement not in m.transcript:
                raise HTTPException(502, "AI did not provide a valid source line.")
            if f.existing_id and f.existing_id not in {
                x["id"] for x in payload["existing"]
            }:
                f.existing_id = None
        original_transcript = "\n".join(lines)
        from app.core.concurrency import lock_organization

        lock_organization(self.s.db, self.s.actor.organization_id)
        self.s.db.expire_all()
        m = self.s.get(Meeting, id)
        if (
            m.state == "reviewed"
            or m.transcript.splitlines() != original_transcript.splitlines()
        ):
            raise HTTPException(
                409, "Meeting changed during analysis; refresh and retry"
            )
        m.findings = findings.model_dump(mode="json")["findings"]
        m.state = "analyzed"
        self.s.db.commit()
        return m

    def review(self, id, review):
        from app.core.concurrency import lock_organization

        lock_organization(self.s.db, self.s.actor.organization_id)
        self.s.db.expire_all()
        m = self.s.get(Meeting, id)
        if m.state != "analyzed":
            raise HTTPException(
                409, "Analyze before review; a meeting can be confirmed only once."
            )
        indices = [i.index for i in review.items]
        if len(set(indices)) != len(indices) or set(indices) != set(
            range(len(m.findings))
        ):
            raise HTTPException(422, "Review every finding exactly once.")
        confirmed = {}
        for item in review.items:
            if item.action == "ignore":
                continue
            f = m.findings[item.index]
            if item.action == "link":
                if not item.existing_id:
                    raise HTTPException(422, "Choose an existing commitment to link.")
                c = self.s.get(Commitment, item.existing_id)
                if any(
                    getattr(c, key) != getattr(item, key)
                    for key in ("title", "owner", "due_date", "condition")
                ) or (item.owner_id and item.owner_id != c.owner_id):
                    from app.core.permissions import require_edit

                    require_edit(self.s.actor, c)
                self.s.event(c, "meeting_mention", f["statement"], m.id)
                for key in ("title", "owner", "due_date", "condition"):
                    value = getattr(item, key)
                    if getattr(c, key) != value:
                        self.s.event(
                            c,
                            (
                                "deadline_change"
                                if key == "due_date"
                                else "context_change"
                            ),
                            f"{key}: {getattr(c, key)} → {value}",
                            m.id,
                        )
                        setattr(c, key, value)
            else:
                c = self.s.save(
                    Commitment(
                        title=item.title,
                        owner=item.owner,
                        due_date=item.due_date,
                        condition=item.condition,
                        source_statement=f["statement"],
                        meeting_id=m.id,
                    )
                )
                self.s.event(c, "created", "Confirmed from " + m.title, m.id)
            if self.s.actor:
                c.owner_id = self.resolve_owner(item.owner, item.owner_id)
                if c.owner_id:
                    c.owner = self.s.db.get(User, c.owner_id).name
            confirmed[item.index] = c
        # Validate all suggested dependencies once, then apply atomically.
        proposed = set()
        for item in review.items:
            if item.action == "ignore":
                continue
            c = confirmed[item.index]
            upstream = list(item.prerequisite_ids)
            for index in item.depends_on_indices:
                if index not in confirmed:
                    raise HTTPException(422, "A prerequisite was ignored or missing")
                upstream.append(confirmed[index].id)
            proposed.update((pre, c.id) for pre in upstream)
        if proposed:
            identifiers = {node for pair in proposed for node in pair}
            rows, graph = self.snapshot(list(identifiers))
            if identifiers - set(rows):
                raise HTTPException(404, "Prerequisite not found")
            if graph.has_cycle(proposed):
                raise HTTPException(422, "Suggested dependency creates a cycle")
            existing = {(edge.prerequisite_id, edge.commitment_id) for edge in graph}
            for pre, child in sorted(proposed - existing):
                self.s.save(Dependency(commitment_id=child, prerequisite_id=pre))
                self.s.event(
                    rows[child], "dependency_added", "Waiting for " + rows[pre].title
                )
        m.state = "reviewed"
        self.s.db.commit()
        return m
