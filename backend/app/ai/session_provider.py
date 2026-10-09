class SessionAwareProvider:
    def __init__(self, provider, db):
        self.provider, self.db = provider, db

    async def json(self, instruction, payload):
        if self.db.new or self.db.dirty or self.db.deleted:
            raise RuntimeError("AI calls must occur before transactional writes")
        self.db.commit()  # release read-only transaction and pooled connection
        return await self.provider.json(instruction, payload)
