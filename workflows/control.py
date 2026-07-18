"""
workflows/control.py

Tiny one-shot workflow used as the ACTION for Temporal Schedules that need
to SIGNAL an existing workflow rather than start a new one — Schedules can
only start workflow executions, so this is the bridge (e.g. the daily
"stop the gift farm at night" schedule targets this workflow, which just
signals GiftFarmWorkflow and completes). See schedule_gift_farm.py.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from ._base import PERSIST_TASK_QUEUE

with workflow.unsafe.imports_passed_through():
    from pydantic import BaseModel

    from activities.control import send_workflow_signal


class SignalWorkflowParams(BaseModel):
    target_workflow_id: str
    signal_name: str


@workflow.defn
class SignalWorkflowAction:
    @workflow.run
    async def run(self, target_workflow_id: str, signal_name: str) -> None:
        params = SignalWorkflowParams(
            target_workflow_id=target_workflow_id,
            signal_name=signal_name,
        )
        target_workflow_id = params.target_workflow_id
        signal_name = params.signal_name

        await workflow.execute_activity(
            send_workflow_signal,
            args=[target_workflow_id, signal_name],
            task_queue=PERSIST_TASK_QUEUE,
            schedule_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
