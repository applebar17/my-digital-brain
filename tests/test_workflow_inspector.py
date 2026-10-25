"""Functional checks for shared workflow execution and local configuration inspection."""

from threading import Thread
from urllib.request import urlopen

from pydantic import BaseModel

from product.application.workflows import BaseWorkflow, WorkflowContext, WorkflowStep
from product.application.workflows.inspection import inspect_workflow
from product.dev.sample_workflow import sample_workflow
from product.dev.workflow_inspector import make_server


class SourceDTO(BaseModel):
    text: str


class PreparedDTO(BaseModel):
    text: str


def _source_input(context: WorkflowContext) -> SourceDTO:
    return SourceDTO.model_validate(context.request)


def _prepare(source: SourceDTO) -> PreparedDTO:
    return PreparedDTO(text=source.text.strip())


def _dependent_input(context: WorkflowContext) -> PreparedDTO:
    return PreparedDTO.model_validate(context.results["prepare"])


def _finish(prepared: PreparedDTO) -> PreparedDTO:
    return PreparedDTO(text=prepared.text.upper())


def test_declared_dependencies_drive_execution_and_inspection() -> None:
    workflow = BaseWorkflow(
        "two_step_example",
        "Typed handoff example",
        [
            WorkflowStep("prepare", "Prepare", "Strip spaces", _source_input, _prepare),
            WorkflowStep(
                "finish",
                "Finish",
                "Uppercase text",
                _dependent_input,
                _finish,
                depends_on=("prepare",),
            ),
        ],
    )
    assert workflow.run(SourceDTO(text=" hello "))["finish"] == PreparedDTO(text="HELLO")
    inspected = inspect_workflow(workflow)
    assert inspected.steps[1].depends_on == ["prepare"]
    assert inspected.steps[1].input_model.name == "PreparedDTO"


def test_local_page_shows_assembled_agentic_configuration() -> None:
    workflow = sample_workflow()
    with make_server(workflow, port=0) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/workflow") as response:
                payload = response.read().decode("utf-8")
            with urlopen(f"http://127.0.0.1:{server.server_port}/") as response:
                page = response.read().decode("utf-8")
        finally:
            server.shutdown()
            thread.join(timeout=5)
    assert '"workflow_id":"sample_memory_ingestion"' in payload
    assert '"state_id":"sample_interpretation"' in payload
    assert '"toolbox_name":"sample_read_tools"' in payload
    assert '"reasoning":{' in payload
    assert '"planning":null' in payload
    assert "Workflow inspector" in page
