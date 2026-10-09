from fastapi import HTTPException
from app.models.entities import Commitment
import hashlib, json
from app.services.commitments.search import CommitmentSearch


class AssistanceWorkflow:
    def blocker_context(self, id):
        items = self.listing(snapshot=self.snapshot([id]))
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
        items = self.listing(snapshot=self.snapshot([id]))
        c = next((x for x in items if x["id"] == id), None)
        if not c:
            raise HTTPException(404, "Commitment not found")
        history = [
            {"kind": e.kind, "message": e.message} for e in self.s.events_for(id)[-20:]
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
