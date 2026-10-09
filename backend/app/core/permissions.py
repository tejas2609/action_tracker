from fastapi import HTTPException


def can_read(actor, commitment):
    return bool(
        commitment
        and commitment.organization_id == actor.organization_id
        and (commitment.status != "review" or commitment.owner_id == actor.id)
    )


def require_edit(actor, commitment):
    if not can_read(actor, commitment):
        raise HTTPException(404, "Commitment not found")
    if commitment.owner_id != actor.id and actor.role != "Product Manager":
        raise HTTPException(
            403, "Only the owner or a Product Manager can edit this commitment"
        )
    return commitment
