from fastapi import HTTPException
from pydantic import ValidationError
from app.models.entities import Meeting, Commitment, Dependency
from app.schemas.contracts import Findings
from app.models.people import User
from sqlalchemy import select
import hashlib, json
from app.services.intelligence import serialize, assess, descendants
from app.services.search import CommitmentSearch
from app.services.dependency_graph import DependencyGraph

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


class Workflow:
    def __init__(self, store, ai):
        self.s = store
        self.ai = ai

    def resolve_owner(self, name, id=None):
        org = self.s.actor.organization_id
        if id:
            user = self.s.db.get(User, id)
            if not user or user.organization_id != org or not user.active:
                raise HTTPException(422, "Owner must be an active organization user.")
            return user.id
        users = list(
            self.s.db.scalars(
                select(User).where(User.organization_id == org, User.active == True)
            )
        )
        matches = [
            u for u in users if u.name.strip().casefold() == name.strip().casefold()
        ]
        if len(matches) == 1:
            return matches[0].id
        raise HTTPException(422, "Select an organization user for owner " + name)

    def snapshot(self):
        rows = {c.id: c for c in self.s.all(Commitment)}
        edges = DependencyGraph(self.s.all(Dependency))
        return rows, edges

    def risk_levels(self):
        rows, edges = self.snapshot()
        return {id: assess(c, rows, edges)["level"] for id, c in rows.items()}

    def audit_risks(self, before):
        rows, edges = self.snapshot()
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
                for item in self.listing()
            ],
        }

        raw = await self.ai.json(EXTRACT, payload)

        if isinstance(raw, dict) and raw.get("findings") == []:
            raw = await self.ai.json(
                EXTRACT + "\nA previous attempt returned no findings. "
                "Re-read the transcript independently and check for "
                "explicit work promises. Extract those supported by "
                "the conversation; do not invent commitments.",
                payload,
            )
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
            if f.existing_id and not self.s.db.get(Commitment, f.existing_id):
                f.existing_id = None
        m.findings = findings.model_dump(mode="json")["findings"]
        m.state = "analyzed"
        self.s.db.commit()
        return m

    def review(self, id, review):
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
                            f"{key}: {getattr(c,key)} → {value}",
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
        # Apply reviewed dependency suggestions only after all promises exist.
        for item in review.items:
            if item.action == "ignore":
                continue
            c = confirmed[item.index]
            upstream = list(item.prerequisite_ids)
            for index in item.depends_on_indices:
                if index not in confirmed:
                    raise HTTPException(
                        422,
                        "A prerequisite finding was ignored or missing. Remove that dependency or confirm it.",
                    )
                upstream.append(confirmed[index].id)
            for pre in upstream:
                self.s.get(Commitment, pre)
                rows, edges = self.snapshot()
                if c.id == pre or pre in descendants(c.id, edges):
                    raise HTTPException(
                        422, "Suggested dependency creates a cycle. Edit the review."
                    )
                if not self.s.db.get(Dependency, (c.id, pre)):
                    self.s.save(Dependency(commitment_id=c.id, prerequisite_id=pre))
                    self.s.event(
                        c, "dependency_added", "Waiting for " + rows[pre].title
                    )
        m.state = "reviewed"
        self.s.db.commit()
        return m

    def update(self, id, patch):
        c = self.s.get(Commitment, id)
        before_levels = self.risk_levels()
        rows, edges = self.snapshot()
        values = patch.model_dump(exclude_unset=True)
        if self.s.actor and ("owner" in values or "owner_id" in values):
            owner_id = self.resolve_owner(
                values.get("owner") or c.owner, values.get("owner_id")
            )
            if not owner_id:
                raise HTTPException(422, "Select an organization user as owner.")
            values["owner_id"] = owner_id
            values["owner"] = self.s.db.get(User, owner_id).name
        for key, value in values.items():
            if value is None and key != "due_date":
                raise HTTPException(422, key + " cannot be null")
            if getattr(c, key) != value:
                self.s.event(
                    c,
                    (
                        "deadline_change"
                        if key == "due_date"
                        else "status_change" if key == "status" else "updated"
                    ),
                    f"{key}: {getattr(c,key)} → {value}",
                )
                setattr(c, key, value)
        if c.status == "completed":
            c.progress = 100
        self.audit_risks(before_levels)
        self.s.db.commit()
        return serialize(c, rows, edges)

    def edge(self, id, pre):
        self.s.get(Commitment, id)
        self.s.get(Commitment, pre)
        rows, edges = self.snapshot()
        if id == pre or pre in descendants(id, edges):
            raise HTTPException(422, "Dependency would create a cycle.")
        if self.s.db.get(Dependency, (id, pre)):
            return
        before = self.risk_levels()
        self.s.save(Dependency(commitment_id=id, prerequisite_id=pre))
        self.s.event(rows[id], "dependency_added", "Waiting for " + rows[pre].title)
        self.audit_risks(before)
        self.s.db.commit()

    def blocker_context(self, id):
        items = self.listing()
        c = next((x for x in items if x["id"] == id), None)
        if not c:
            raise HTTPException(404, "Commitment not found")
        context = {
            "commitment": c,
            "prerequisites": [x for x in items if x["id"] in c["dependencies"]],
            "downstream": [x for x in items if x["id"] in c["impact"]],
        }
        fingerprint = hashlib.sha256(
            json.dumps(context, sort_keys=True, default=str).encode()
        ).hexdigest()
        return context, fingerprint

    async def blocker_analysis(self, id):
        c = self.s.get(Commitment, id)
        context, fingerprint = self.blocker_context(id)
        if c.analysis_hash == fingerprint and c.analysis_text:
            return {
                "explanation": c.analysis_text,
                "next_action": c.analysis_next,
                "cached": True,
            }
        raw = await self.ai.json(
            'Explain blockers using only supplied facts. Identify unresolved prerequisite, person or condition and a practical next action. Do not invent blockers or approval status. Return {"explanation":"plain language","next_action":"one action"}.',
            context,
        )
        if not isinstance(raw.get("explanation"), str) or not isinstance(
            raw.get("next_action"), str
        ):
            raise HTTPException(502, "Invalid blocker analysis response")
        # Do not cache stale AI results if another user changed the graph during generation.
        self.s.db.expire_all()
        _, latest = self.blocker_context(id)
        if latest != fingerprint:
            raise HTTPException(
                409,
                "Commitment changed during analysis. Refresh to analyze the latest state.",
            )
        c = self.s.get(Commitment, id)
        c.analysis_text = raw["explanation"]
        c.analysis_next = raw["next_action"]
        c.analysis_hash = fingerprint
        self.s.event(
            c, "blocker_analysis", raw["explanation"] + " Next: " + raw["next_action"]
        )
        self.s.db.commit()
        return {
            "explanation": c.analysis_text,
            "next_action": c.analysis_next,
            "cached": False,
        }

    async def search(self, q):
        return await CommitmentSearch(self).run(q)

    async def followup(self, id, recipient=None):
        items = self.listing()
        c = next((x for x in items if x["id"] == id), None)
        if not c:
            raise HTTPException(404, "Commitment not found")
        history = [
            {"kind": e.kind, "message": e.message} for e in self.s.events_for(id)
        ]
        raw = await self.ai.json(
            'Draft a concise respectful contextual follow-up. Address the supplied recipient if present, otherwise the owner. Include the exact promise, deadline, blocker and actionable next step; do not invent dates or facts. Return {"message":"draft"}. Do not send anything.',
            {
                "commitment": c,
                "recipient": recipient,
                "dependencies": [x for x in items if x["id"] in c["dependencies"]],
                "history": history,
            },
        )
        msg = raw.get("message")
        if not isinstance(msg, str) or not msg.strip():
            raise HTTPException(502, "Invalid follow-up response")
        self.s.event(self.s.get(Commitment, id), "followup_generated", msg)
        self.s.db.commit()
        return {"message": msg}
