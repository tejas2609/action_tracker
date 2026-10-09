import re

from sqlalchemy import func, select

from app.models.entities import Commitment


def find_candidates(db, actor, text, preferred_ids=(), limit=40):
    scope = (
        Commitment.owner_id == actor.id,
        Commitment.organization_id == actor.organization_id,
        Commitment.status.in_(["active", "review", "completed"]),
    )

    preferred = []

    if preferred_ids:
        preferred = list(
            db.scalars(
                select(Commitment)
                .where(
                    *scope,
                    Commitment.id.in_(list(preferred_ids)),
                )
                .order_by(Commitment.id)
                .limit(10)
            )
        )

    words = list(dict.fromkeys(re.findall(r"[a-z0-9]{3,}", text.lower())))[:80]

    document = func.to_tsvector(
        "english",
        func.coalesce(Commitment.title, "")
        + " "
        + func.coalesce(Commitment.source_statement, ""),
    )

    query = select(Commitment).where(*scope)

    if words:
        search = func.to_tsquery("english", " | ".join(words))

        query = query.order_by(
            func.ts_rank_cd(document, search).desc(),
            Commitment.id,
        )
    else:
        query = query.order_by(Commitment.id)

    rows = list(db.scalars(query.limit(limit)))

    return list({commitment.id: commitment for commitment in preferred + rows}.values())


def candidate_payload(rows):
    return [
        {
            "id": commitment.id,
            "title": commitment.title,
            "status": commitment.status,
            "due_date": commitment.due_date,
            "condition": commitment.condition,
            "source": (commitment.source_statement or "")[:1000],
        }
        for commitment in rows
    ]
