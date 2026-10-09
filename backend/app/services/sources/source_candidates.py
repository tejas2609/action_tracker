"""Bounded indexed retrieval shared by meeting, email and chat processing."""

import re
from sqlalchemy import func, select, literal_column, or_
from app.models.entities import Commitment
from app.core.config import settings


def find_candidates(
    db, actor, text, preferred_ids=(), limit=None, organization_wide=False
):
    limit = limit or settings.ai_candidate_limit
    scope = [
        Commitment.organization_id == actor.organization_id,
        Commitment.status.in_(["active", "review", "completed"]),
    ]
    if not organization_wide:
        scope.append(Commitment.owner_id == actor.id)
    preferred = (
        list(
            db.scalars(
                select(Commitment)
                .where(*scope, Commitment.id.in_(list(preferred_ids)))
                .limit(min(10, limit))
            )
        )
        if preferred_ids
        else []
    )
    words = list(dict.fromkeys(re.findall(r"[a-z0-9]{3,}", text.lower())))[:40]
    query = select(Commitment).where(*scope)
    if words and db.bind.dialect.name == "postgresql":
        # Must match the migration's expression index exactly.
        document = literal_column(
            "to_tsvector('english'::regconfig, coalesce(title, '') || ' ' || coalesce(source_statement, ''))"
        )
        search = func.to_tsquery("english", " | ".join(words))
        query = query.where(document.op("@@")(search)).order_by(
            func.ts_rank_cd(document, search).desc(), Commitment.id
        )
    elif words:
        query = query.where(
            or_(*[Commitment.title.ilike("%" + word + "%") for word in words[:8]])
        ).order_by(Commitment.created_at.desc(), Commitment.id)
    else:
        query = query.order_by(Commitment.created_at.desc(), Commitment.id)
    rows = list(db.scalars(query.limit(limit)))
    return list({row.id: row for row in preferred + rows}.values())[:limit]


def candidate_payload(rows):
    return [
        {
            "id": c.id,
            "title": c.title,
            "owner_id": c.owner_id,
            "owner": c.owner,
            "status": c.status,
            "due_date": c.due_date,
            "condition": c.condition[:500],
            "source": (c.source_statement or "")[:500],
        }
        for c in rows
    ]
