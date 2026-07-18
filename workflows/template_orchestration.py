"""
workflows/template_orchestration.py

Visual Calibration Template Orchestration workflow.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from pydantic import BaseModel

    from activities.diagnostics import (
        capture_template_screen,
        extract_templates_from_screen,
        verify_matching_templates,
    )


class TemplateOrchestrationParams(BaseModel):
    target: str = "hud"
    resolution: str = "2560x1440"


@workflow.defn
class TemplateOrchestrationWorkflow:
    """
    Workflow to automate template capture and visual verification.

    Parameters:
        target (str): "hud" or "workshop"
        resolution (str): "2560x1440"
    """

    @workflow.run
    async def run(self, target: str = "hud", resolution: str = "2560x1440") -> dict:
        params = TemplateOrchestrationParams(target=target, resolution=resolution)
        target = params.target
        resolution = params.resolution

        workflow.logger.info("TemplateOrchestrationWorkflow started for target: %s", target)

        if target == "hud":
            screenshot = await workflow.execute_activity(
                capture_template_screen,
                args=["hud_base", "", ""],
                schedule_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        elif target == "workshop":
            screenshot = await workflow.execute_activity(
                capture_template_screen,
                args=["workshop_base", "e", "escape"],
                schedule_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        else:
            raise ValueError(f"Unknown target: {target}")

        extracted = await workflow.execute_activity(
            extract_templates_from_screen,
            args=[screenshot, target, resolution],
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        template_names = list(extracted.keys())
        verification = await workflow.execute_activity(
            verify_matching_templates,
            args=[template_names],
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        return {
            "screenshot": screenshot,
            "extracted_templates": extracted,
            "verification_results": verification,
        }
