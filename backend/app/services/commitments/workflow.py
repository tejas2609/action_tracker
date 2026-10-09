"""Compatibility facade composing focused workflow capabilities.
Routes keep their public contract; graph, meeting, commitment and AI-assistance
policies can be replaced independently. Dependencies are injected by API DI.
"""

from app.services.commitments.graph_workflow import GraphWorkflow
from app.services.meetings.meeting_workflow import MeetingWorkflow
from app.services.commitments.commitment_workflow import CommitmentWorkflow
from app.services.commitments.assistance_workflow import AssistanceWorkflow


class Workflow(GraphWorkflow, MeetingWorkflow, CommitmentWorkflow, AssistanceWorkflow):
    def __init__(self, store, ai):
        self.s, self.ai = store, ai
