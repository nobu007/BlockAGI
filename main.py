import os
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import dotenv
import typer
import uvicorn
from blockagi.chains.base import BlockAGICallbackHandler
from blockagi.resource_pool import ResourcePool
from blockagi.run import run_blockagi
from blockagi.schema import Findings, Narrative, Objective, Resource
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from langchain.callbacks.base import BaseCallbackHandler
from starlette.responses import FileResponse

app = FastAPI()


@app.get("/")
def get_index():
    return FileResponse("dist/index.html")


@app.get("/api/state")
def get_api_state():
    app.state.blockagi_state.resource_pool = app.state.resource_pool
    return app.state.blockagi_state


app.mount("/", StaticFiles(directory="dist"), name="dist")


@dataclass
class StepHistory:
    timestamp: str
    value: str


@dataclass
class AgentLog:
    timestamp: str
    round: int
    message: str


@dataclass
class Status:
    step: str
    round: int


@dataclass
class LLMLog:
    prompt: str
    response: str


@dataclass
class BlockAGIState:
    start_time: str
    end_time: Optional[str]
    agent_role: str
    status: Status
    agent_logs: list[AgentLog]
    historical_steps: list[StepHistory]
    objectives: list[Objective]
    findings: list[Findings]
    resource_pool: ResourcePool
    llm_logs: list[LLMLog]
    narratives: list[Narrative]

    def add_agent_log(self, message: str):
        self.agent_logs.append(
            AgentLog(
                timestamp=datetime.utcnow().isoformat(),
                round=self.status.round,
                message=message,
            )
        )


@app.on_event("startup")
def on_startup():
    app.state.resource_pool = ResourcePool()

    def target(**kwargs):
        try:
            run_blockagi(**kwargs)
        except Exception as e:
            app.state.blockagi_state.add_agent_log(f"Error: {e}")
            print("XXXX", e)
        app.state.blockagi_state.end_time = datetime.utcnow().isoformat()

    threading.Thread(
        target=target,
        kwargs=dict(
            agent_role=app.state.blockagi_state.agent_role,
            openai_api_key=app.state.openai_api_key,
            openai_model=app.state.openai_model,
            resource_pool=app.state.resource_pool,
            objectives=app.state.blockagi_state.objectives,
            blockagi_callback=BlockAGICallback(app.state.blockagi_state),
            llm_callback=LLMCallback(app.state.blockagi_state),
            iteration_count=app.state.iteration_count,
        ),
    ).start()
    webbrowser.open(f"http://{app.state.host}:{app.state.port}")


@app.on_event("shutdown")
def on_shutdown():
    os._exit(0)


class BlockAGICallback(BlockAGICallbackHandler):
    state: BlockAGIState

    def __init__(self, blockagi_state):
        self.state = blockagi_state

    def on_iteration_start(self, inputs: Dict[str, Any]) -> Any:
        self.state.status.round += 1

    def on_log_message(self, message: str) -> Any:
        self.state.add_agent_log(message)

    def on_step_start(self, step, inputs, **kwargs):
        self.state.status.step = step

    def on_step_end(self, step, inputs, outputs, **kwargs):
        if step == "PlanChain":
            pass
        elif step == "ResearchChain":
            pass
        elif step == "NarrateChain":
            self.state.narratives.append(outputs["narrative"])
        elif step == "EvaluateChain":
            self.state.objectives = outputs["updated_objectives"]
            self.state.findings = outputs["updated_findings"]


class LLMCallback(BaseCallbackHandler):
    state: BlockAGIState

    def __init__(self, blockagi_state):
        self.state = blockagi_state

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.state.llm_logs.append(
            LLMLog(
                prompt="".join(prompts),
                response="",
            )
        )

    def on_llm_new_token(self, token: str, **kwargs):
        self.state.llm_logs[-1].response += token


def main(
    host: str = typer.Option(envvar="WEB_HOST"),
    port: int = typer.Option(envvar="WEB_PORT"),
    agent_role: str = typer.Option(envvar="BLOCKAGI_AGENT_ROLE"),
    iteration_count: int = typer.Option(envvar="BLOCKAGI_ITERATION_COUNT"),
    objectives: list[str] = typer.Option(None, "--objectives", "-o"),
    openai_api_key: str = typer.Option(envvar="OPENAI_API_KEY"),
    openai_model: str = typer.Option(envvar="OPENAI_MODEL"),
):
    app.state.host = host
    app.state.port = port
    if not objectives:
        for index in range(1, 11):
            key = f"BLOCKAGI_OBJECTIVE_{index}"
            if objective := os.getenv(key):
                objectives.append(objective.strip())
    if not objectives:
        raise ValueError("No objectives specified")

    app.state.openai_api_key = openai_api_key
    app.state.openai_model = openai_model
    app.state.iteration_count = iteration_count
    app.state.blockagi_state = BlockAGIState(
        start_time=datetime.utcnow().isoformat(),
        end_time=None,
        agent_role=agent_role,
        status=Status(step="PlanChain", round=0),
        historical_steps=[],
        agent_logs=[
            AgentLog(datetime.utcnow().isoformat(), 0, f"You are {agent_role}"),
            AgentLog(datetime.utcnow().isoformat(), 0, f"Using {openai_model}"),
        ],
        objectives=[Objective(topic=topic, expertise=0.0) for topic in objectives],
        findings=[],
        resource_pool=ResourcePool(),
        llm_logs=[],
        narratives=[],
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    dotenv.load_dotenv()
    typer.run(main)
