"""Functional checks for shared workflow execution and local configuration inspection."""

from threading import Thread
from urllib.request import urlopen

from pydantic import BaseModel

from product.application.workflows import BaseWorkflow, WorkflowContext, WorkflowStep
from product.application.workflows.inspection import inspect_workflow
from product.dev.current_configuration import current_application_configuration
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


def test_local_page_shows_current_assembled_application_configuration() -> None:
    configuration = current_application_configuration()
    with make_server(configuration, port=0) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(
                f"http://127.0.0.1:{server.server_port}/api/configuration"
            ) as response:
                payload = response.read().decode("utf-8")
            with urlopen(f"http://127.0.0.1:{server.server_port}/") as response:
                page = response.read().decode("utf-8")
        finally:
            server.shutdown()
            thread.join(timeout=5)
    assert '"state_id":"conversation_entry"' in payload
    assert '"state_id":"memory_query"' in payload
    assert '"workflow_id":"memory_ingestion"' in payload
    assert '"state_id":"ingestion_reasoning"' in payload
    assert '"toolbox_name":"conversation_entry"' in payload
    assert '"name":"query_memory"' in payload
    assert '"name":"ingest_memory"' in payload
    assert '"name":"search_memory"' in payload
    assert '"name":"ConversationEntryRequestDTO"' in payload
    assert '"name":"IngestionReasoningResultDTO"' in payload
    assert '"reasoning":null' in payload
    assert '"planning":null' in payload
    assert "AI configuration inspector" in page
    assert "Reasoning" in page
    assert "Planning" in page
    assert "Tools" in page
    assert "Input" in page
    assert "Output" in page
