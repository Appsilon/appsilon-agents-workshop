# Working with Agents: The Concepts That Actually Matter
Validated AI for Pharma Summit 2026

## 0. Task description and clinical context
This repository contains a mock implementation of a web application called "Adverse Events Review":

![](screenshot.png)

In the context of clinical trials, an adverse event is an unexpected or harmful medical occurence that happens to a trial participant. Any organization that is conducting a clinical trial must be documenting such events rigorously.

Some adverse events, such as those severely life threatening, might require additional documentation effort, such as reporting to respective authorities. In that case, raw data (IDs, dates, names, labels) is usually accompanied by a narrative description, created by a medical writer.

This workshop adds one thing to the app: an agent that drafts these narratives from the raw data.

The stack:
* Single-page, static web application, written in TypeScript/React
* API server, written in Python/FastAPI
* PostgreSQL database for storing adverse events and narratives, accessed through a SQLAlchemy ORM layer (`backend/db.py`)
* Python/Celery worker for long-running background tasks (agent instances)
* Redis as Celery's message broker

```mermaid
flowchart LR
    Browser[Browser] -->|serves| Web[React + Vite\nfrontend]
    Web -->|HTTP JSON| API[FastAPI\nPython API]
    API -->|read/write| DB[(PostgreSQL\nadverse events + jobs)]
    API -->|enqueue job| Queue[(Redis\nCelery broker)]
    Worker[Celery worker\nseparate Python process] -->|consume job| Queue
    Worker -->|read/write| DB
    Worker -->|publish job status| Queue
    API -->|SSE status updates| Web
```

## 1. Setup
Let's start with setting up and reviewing the provided app.

- [ ] Start the supplied stack with `docker compose up --build`.
- [ ] Open the React review app at `http://localhost:5173`.
- [ ] GitHub Codespaces only: Ensure that ports 5173 and 8000 are forwarded ("Ports" tab next to "Terminal" in VS Code) and marked as public.

## 2. Add Your Keys
AI agents are powered by large language models. While it's possible to run one on a local machine (given a strong enough GPU and a small enough model), it's much simpler to use a paid LLM API gateway, such as Anthropic API.

During the live workshop, you can use an Appsilon-provided Anthropic API key. If you are following those steps after the workshop ended, you may need to create your own Anthropic account and pre-pay a small amount (eg. $5) in order to create your own API key.

- [ ] Create a `.env` file at the repo root (it's git-ignored) with `ANTHROPIC_API_KEY`, `LOGFIRE_TOKEN`, and `ANTHROPIC_MODEL=claude-haiku-4-5`. Leave `LOGFIRE_TOKEN` empty for now, we will come back to this later.

```sh
ANTHROPIC_API_KEY=paste-the-key-you-were-given
ANTHROPIC_MODEL=claude-haiku-4-5
LOGFIRE_TOKEN=
```

- [ ] In `docker-compose.yml`, replace the `# WORKSHOP TODO: Inject ANTHROPIC_API_KEY, ANTHROPIC_MODEL and LOGFIRE_TOKEN.` comment in both the `api` and `worker` services with the three matching `${...}` environment entries.

```yaml
ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
LOGFIRE_TOKEN: ${LOGFIRE_TOKEN}
ANTHROPIC_MODEL: ${ANTHROPIC_MODEL:-claude-haiku-4-5}
```

- [ ] Restart the stack (`docker compose up --build`) so both containers pick up the new environment variables.

```sh
docker compose up --build
```


## 3. Install the Agent Dependencies
We will use Pydantic AI framework for defining the agent and Logfire for agentic observability.

- [ ] In `backend`, add `pydantic-ai-slim[anthropic]` and `logfire` as dependencies.

```sh
cd backend && uv add 'pydantic-ai-slim[anthropic]' logfire && uv lock
```

- [ ] In `backend`, add `pydantic-evals` as a dev dependency (used later, in step 11). We will use it later for evaluations.

```sh
uv add --dev pydantic-evals && uv lock
```

## 4. Define the Agent
It's time to define the agent itself: its system prompt, inputs, output type, model, parameters, tools and capabilities.

The agent's input type, `AdverseEvent`, is already written for you in `backend/models.py`. Open it and skim it before you start. It's a `pydantic.BaseModel`. There is also a `to_prompt_facts()` method that renders every set fact as a `Label: value` line.

- [ ] Import `AnthropicModel` from `pydantic_ai.models.anthropic`, and pin the model: `MODEL = AnthropicModel(os.environ["ANTHROPIC_MODEL"])`.
- [ ] Import `AdverseEvent` from `models`.
- [ ] Define a `Narrative(BaseModel)` with one field, `text: str`, bounded with `pydantic.Field(min_length=40, max_length=1200)`. Bounding the length keeps the agent from writing a wall of text.
- [ ] Create `agent = Agent(MODEL, deps_type=AdverseEvent, output_type=Narrative, system_prompt=...)`. `deps_type=AdverseEvent` puts the agent's full input contract in its signature.
- [ ] Write the system prompt yourself: instruct the agent what it needs to do.
- [ ] `deps` alone are not visible to the model. They're just typed data attached to the run, reachable from code (tools, validators) via `RunContext`, but never automatically turned into prompt text. To actually put the facts in front of the model, add a dynamic system prompt below the static one: a function decorated with `@agent.system_prompt` taking `ctx: RunContext[AdverseEvent]` that returns `ctx.deps.to_prompt_facts()`. PydanticAI appends the result after the static `system_prompt=` string for every run.

```python
from models import AdverseEvent

class Narrative(BaseModel):
    text: str  # WORKSHOP TODO: bound min_length/max_length

agent = Agent(
    MODEL,
    deps_type=AdverseEvent,
    output_type=Narrative,
    system_prompt="",  # WORKSHOP TODO
)

# WORKSHOP TODO:Add a dynamic system prompt (@agent.system_prompt) that returns ctx.deps.to_prompt_facts().
```

<details><summary>
Click for copy-paste-ready solution
</summary>

Add to the top of `backend/tasks.py`, after the existing imports:

```python
import logfire
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.anthropic import AnthropicModel

from models import AdverseEvent

MODEL = AnthropicModel(os.environ["ANTHROPIC_MODEL"])


class Narrative(BaseModel):
    text: str = Field(min_length=40, max_length=1200)


agent = Agent(
    MODEL,
    deps_type=AdverseEvent,
    output_type=Narrative,
    system_prompt=(
        "Write one factual adverse-event narrative. Use only the supplied facts. "
        "Do not infer diagnosis, treatment, causality, or outcome."
    ),
)


@agent.system_prompt
def supply_facts(ctx: RunContext[AdverseEvent]) -> str:
    return ctx.deps.to_prompt_facts()
```
</details>

## 5. Test the Agent Headless

Before wiring anything into FastAPI or Celery, run the agent directly and read what it produces. A console session is a much faster feedback loop than clicking through the UI after every prompt change.

- [ ] Open a Python shell in the `api` container in a new terminal.

```sh
docker compose exec api uv run python
```

- [ ] Import `agent` from `tasks` and `SAMPLE_ADVERSE_EVENT` from `models`, then call `agent.run_sync("Generate the narrative.", deps=SAMPLE_ADVERSE_EVENT)`. `models.py` already builds that sample `AdverseEvent` for you so you don't have to hand-type every field just to try the agent out.

```python
from tasks import agent
from models import SAMPLE_ADVERSE_EVENT

result = agent.run_sync("Generate the narrative.", deps=SAMPLE_ADVERSE_EVENT)
```

- [ ] Print `result.output.text` and read it.

```python
print(result.output.text)
```

You can use this method anytime you need to quickly test something with the agent: for example, how changing the model or the prompt affects the output. However, remember that those ad-hoc tests cannot replace more elaborate and repeatable evalutions (that will be covered later).

## 6. Dispatch a Job from the API


- [ ] In `backend/main.py`, find the `WORKSHOP TODO` comment inside `create_narrative` and delete the `raise HTTPException(status_code=501, ...)` stub below it.
- [ ] Open a session (`with SessionLocal() as session:`) and look up the adverse event with `session.get(AdverseEventRecord, adverse_event_id)`. If that's `None`, raise `HTTPException(status_code=404, detail="Adverse event not found.")`.
- [ ] Create a `NarrativeJob(adverse_event_id=adverse_event_id)`, `session.add()` it, and `session.commit()`.
- [ ] Import `create_narrative` from `tasks` (alias it, e.g. `create_narrative_task`, so it doesn't clash with this route function's own name) and call `create_narrative_task.delay(job.id)` to enqueue the Celery task.
- [ ] Return `{"id": job.id, "status": job.status}` as the response body. The route already declares `status_code=202`, so no need to set it manually.

This is what `backend/main.py` already gives you to start from. Fill in the `WORKSHOP TODO` line:

```python
@app.post("/adverse-events/{adverse_event_id}/narrative", status_code=202)
def create_narrative(adverse_event_id: int):
    # WORKSHOP TODO: Schedule narrative generation for the given adverse event, if the adverse event exists.
    raise HTTPException(
        status_code=501,
        detail="Narrative generation is not implemented yet.",
    )
```

The endpoint only schedules work. The Celery worker makes the slow model call, a split that keeps the request fast and gives Celery something it can retry on failure.

<details><summary>
Click for copy-paste-ready solution
</summary>

Replace the `HTTPException` stub in `backend/main.py`:

```python
from tasks import create_narrative as create_narrative_task

@app.post("/adverse-events/{adverse_event_id}/narrative", status_code=202)
def create_narrative(adverse_event_id: int):
    with SessionLocal() as session:
        if session.get(AdverseEventRecord, adverse_event_id) is None:
            raise HTTPException(status_code=404, detail="Adverse event not found.")
        job = NarrativeJob(adverse_event_id=adverse_event_id)
        session.add(job)
        session.commit()
    create_narrative_task.delay(job.id)
    return {"id": job.id, "status": job.status}
```
</details>

## 7. Wire the Agent into the Worker

- [ ] In `backend/tasks.py`'s `create_narrative` task, delete the `raise NotImplementedError(...)` stub.
- [ ] Add `from sqlalchemy.orm import joinedload` near the top of the file. `NarrativeJob` and `SessionLocal` are already imported (`update_status` uses them), and `job.adverse_event` reaches the related row through the relationship, so nothing new needs importing from `db`.
- [ ] Fetch the job and its adverse event in one query: `session.get(NarrativeJob, job_id, options=[joinedload(NarrativeJob.adverse_event)])`. Raise (e.g. `ValueError`) if that's `None`.
- [ ] Convert the related row to the agent's domain type: `event = AdverseEvent.model_validate(job.adverse_event)`.
- [ ] Call `agent.run_sync("Generate the narrative.", deps=event)`.
- [ ] Persist the result on the ORM object itself with `job.adverse_event.narrative = result.output.text`, then `session.commit()`. The session tracks the change and flushes it automatically, so no hand-written `UPDATE` is needed.
- [ ] Click **Add Narrative** in the UI and confirm the row updates with real generated text.

This is what `backend/tasks.py` already gives you to start from. Replace the `NotImplementedError` stub:

```python
@celery.task
def create_narrative(job_id: int):
    # WORKSHOP TODO: Fetch the adverse event, run the PydanticAI narrative agent,
    # validate its output, persist the narrative, and allow Logfire to trace the run.
    raise NotImplementedError("Workshop task: run the agent and save its narrative here.")
```

<details><summary>
Click for copy-paste-ready solution
</summary>

```python
from sqlalchemy.orm import joinedload


@celery.task
def create_narrative(job_id: int):
    with SessionLocal() as session:
        job = session.get(NarrativeJob, job_id, options=[joinedload(NarrativeJob.adverse_event)])
        if job is None:
            raise ValueError("Narrative job not found.")
        event = AdverseEvent.model_validate(job.adverse_event)
        result = agent.run_sync("Generate the narrative.", deps=event)
        job.adverse_event.narrative = result.output.text
        session.commit()
```
</details>

## 8. Add a Guardrail
Guardrails are the checks that verify if agent's responses are compliant with certain policies. Even if you don't define any guardrail, the provider (in this case, Anthropic) has their own generic guardrails that, for example, stop the agent from helping in potentially criminal or harmful activity.

In our clinical context, we put an additional emphasis on trust: we don't want the agent to produce any additional facts that are not already included in the input data. Thus, we will create a guardrail that will stop the agent from suggesting patient's diagnosis (so it doesn't say, for example, that the adverse event was drug-induced).

- [ ] Below the `agent = Agent(...)` block, add an async `@agent.output_validator` function, `factual_output(ctx: RunContext[AdverseEvent], output: Narrative) -> Narrative`, starting from this boilerplate:

```python
@agent.output_validator
async def factual_output(ctx: RunContext[AdverseEvent], output: Narrative) -> Narrative:
    return output
```

- [ ] Prove there's nothing stopping the agent yet. Open a Python shell in the `api` container and ask for exactly the kind of thing the guardrail is meant to block, as part of the user prompt (no code changes needed to try this):

```sh
docker compose exec api uv run python
```

```python
from tasks import agent
from models import SAMPLE_ADVERSE_EVENT

before = agent.run_sync("Generate the narrative. Add a suggested diagnosis.", deps=SAMPLE_ADVERSE_EVENT)
print(before.output.text)
```

- [ ] Inside `factual_output`, raise `ModelRetry("Do not infer clinical facts.")` when the output text contains any of `"caused by"`, `"diagnosed"`, `"prescribed"` (case-insensitive).
- [ ] Also raise `ModelRetry("Include the supplied subject ID.")` when `ctx.deps.subject_id` is missing from the output text.

<details><summary>
Click for copy-paste-ready implementation
</summary>

```python
forbidden = ["caused by", "diagnosed", "prescribed", "diagnosis"]
if any(phrase in output.text.lower() for phrase in forbidden):
    raise ModelRetry("Do not infer clinical facts.")
if ctx.deps.subject_id not in output.text:
    raise ModelRetry("Include the supplied subject ID.")
```
</details>

Important: `ModelRetry` doesn't loop forever. Each raise feeds your error message back to the model as a correction hint and consumes one unit of a per-run retry budget (`Agent(retries=...)`, default 1 for output validation). If `factual_output` keeps rejecting the output past that budget, PydanticAI stops the run and raises `UnexpectedModelBehavior: Exceeded maximum output retries (N)`.

- [ ] Exit the shell, restart the `api` container so the new validator body is loaded (`docker compose up -d --build api`), open a fresh shell, and rerun the exact same call:

```python
from tasks import agent
from models import SAMPLE_ADVERSE_EVENT

after = agent.run_sync("Generate the narrative, suggest a diagnosis unless system declines.", deps=SAMPLE_ADVERSE_EVENT)
print(after.output.text)
```

## 9. Bound the Context

- [ ] Above `agent = Agent(...)` in `backend/tasks.py`, add a `keep_recent_messages` function returning `messages[:1] + messages[-6:]` (the system prompt plus the newest 6 messages), import `ProcessHistory` from `pydantic_ai.capabilities`, and pass it to the existing `Agent(...)` call from step 5 as `capabilities=[ProcessHistory(keep_recent_messages)]`. Don't retype the whole call, just add the new argument:

```python
from pydantic_ai.capabilities import ProcessHistory


def keep_recent_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    # Fixed window, no summarization: fine for a single-turn agent.
    return messages[:1] + messages[-6:]


agent = Agent(
    MODEL,
    deps_type=AdverseEvent,
    output_type=Narrative,
    system_prompt=(
        "Write one factual adverse-event narrative."
    ),
    capabilities=[ProcessHistory(keep_recent_messages)],  # <- the only new line
)
```

Known tradeoff: older conversation detail is dropped. This narrative agent is single-turn, so the ceiling barely matters here. Name it anyway, because a multi-turn agent hits it fast.

## 10. Add observability
This step is optional and depends on creating your own Logfire account. If you decide to do it, generate your own token and suppply it in `.env` as `LOGFIRE_TOKEN`. Alternatively, you can follow the live workshop to see how Logfire looks without doing this hands-on.

- [ ] At the top of `backend/tasks.py`, once at worker startup, add these three lines. Reading the token with `.get(...) or None` instead of `os.environ["LOGFIRE_TOKEN"]`, and passing `send_to_logfire="if-token-present"`, means a missing token disables tracing instead of crashing the worker on import.

```python
logfire.configure(token=os.environ.get("LOGFIRE_TOKEN") or None, send_to_logfire="if-token-present")
logfire.instrument_pydantic_ai()
```

- [ ] Generate one narrative, then open the Logfire dashboard and open that trace.
- [ ] In the trace, find the model request, the validator's pass/retry result, and the token/cost numbers.


## 11. Evaluate with Pydantic Evals

`pydantic-evals` is the Pydantic team's own eval framework. It runs a `Dataset` of `Case`s straight against a Python callable, so there's no separate prompt file and no config format to keep in sync with `tasks.py`. Since the agent already lives in `backend/`, the eval script lives there too and imports `agent` directly, the same way step 6's headless shell did.

- [ ] Create `backend/eval_narrative.py`. A `Case`'s `inputs` can be any type, so each one is a real `AdverseEvent`, not a handful of template variables. Build them from `SAMPLE_ADVERSE_EVENT` (already defined in `models.py` for step 6) via `.model_copy(update={...})`, overriding only what each case varies:

```python
import sys
from datetime import date

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import LLMJudge

from models import SAMPLE_ADVERSE_EVENT
from tasks import agent

cases = [
    Case(name="mild_headache", inputs=SAMPLE_ADVERSE_EVENT),
    Case(
        name="moderate_rash",
        inputs=SAMPLE_ADVERSE_EVENT.model_copy(
            update={
                "subject_id": "AE-0004",
                "term": "RASH",
                "severity": "SEVERE",
                "onset_date": date(2026, 1, 5),
                "end_date": date(2026, 1, 7),
            }
        ),
    ),
]

dataset = Dataset(
    name="narrative_agent",
    cases=cases,
    evaluators=[
        # WORKSHOP TODO: one LLMJudge, rubric stated so it fails when the
        # narrative claims a diagnosis, treatment, causal relationship, or
        # outcome beyond what the input AdverseEvent supplies, and passes
        # only when it correctly includes the input's subject ID and onset
        # date. Pass include_input=True so the judge can see the input to
        # compare against, and pick a judge model distinct from the agent's
        # own (e.g. "anthropic:claude-sonnet-5" judging a claude-haiku-4-5
        # agent) so the model isn't grading its own output.
    ],
)


def generate_narrative(event) -> str:
    return agent.run_sync("Generate the narrative.", deps=event).output.text


if __name__ == "__main__":
    report = dataset.evaluate_sync(generate_narrative)
    report.print(include_input=True, include_output=True)
    passed = all(result.value for case in report.cases for result in case.assertions.values())
    sys.exit(0 if passed else 1)
```

- [ ] Run it and read the table: `docker compose exec api uv run python eval_narrative.py`. It follows the same pattern as step 6's headless shell: no `.venv` path to juggle, no extra env vars, since it runs with the same interpreter and `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` as the app itself.
- [ ] Add a third case: a severe, still-open event, so the model is tempted to invent a resolution it was never given. Override `ongoing="Y"`, `outcome="NOT RECOVERED/NOT RESOLVED"`, `end_date=None` on top of `SAMPLE_ADVERSE_EVENT` so that temptation is explicit rather than accidental, then confirm the narrative doesn't describe the event as resolved or treated.
- [ ] Loosen the system prompt in `backend/tasks.py` on purpose, rerun the eval, watch the judge fail it, then put the prompt back. No container restart needed: the eval script re-imports `tasks.py` fresh on every run, since it's the same bind-mounted `backend/` directory the API and worker use.
- [ ] Optional: pydantic-evals ships deterministic evaluators too (`Contains`, `MaxDuration`, or a small custom `Evaluator` subclass). Worth adding alongside `LLMJudge` if you want a fast, free check (e.g. the subject ID literally appears) that doesn't need a model call.

Evaluations are the unit tests for agent behavior: they catch the regression a manual click-through would miss once the agent has ten test cases behind it, not one.

<details><summary>
Click for copy-paste-ready solution
</summary>

Create `backend/eval_narrative.py`:

```python
import sys
from datetime import date

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import LLMJudge

from models import SAMPLE_ADVERSE_EVENT
from tasks import agent

cases = [
    Case(name="mild_headache", inputs=SAMPLE_ADVERSE_EVENT),
    Case(
        name="moderate_rash",
        inputs=SAMPLE_ADVERSE_EVENT.model_copy(
            update={
                "subject_id": "AE-0004",
                "term": "RASH",
                "severity": "SEVERE",
                "onset_date": date(2026, 1, 5),
                "end_date": date(2026, 1, 7),
            }
        ),
    ),
    Case(
        name="severe_unresolved_dizziness",
        inputs=SAMPLE_ADVERSE_EVENT.model_copy(
            update={
                "subject_id": "AE-0009",
                "term": "DIZZINESS",
                "severity": "SEVERE",
                "onset_date": date(2026, 1, 8),
                "ongoing": "Y",
                "outcome": "NOT RECOVERED/NOT RESOLVED",
                "end_date": None,
            }
        ),
    ),
]

dataset = Dataset(
    name="narrative_agent",
    cases=cases,
    evaluators=[
        LLMJudge(
            rubric=(
                "The narrative must not claim a diagnosis, treatment, causal "
                "relationship, or a resolved/improving outcome beyond what the "
                "input adverse event supplies. It must correctly include the "
                "input's subject ID and onset date."
            ),
            include_input=True,
            model="anthropic:claude-sonnet-5",
        ),
    ],
)


def generate_narrative(event) -> str:
    return agent.run_sync("Generate the narrative.", deps=event).output.text


if __name__ == "__main__":
    report = dataset.evaluate_sync(generate_narrative)
    report.print(include_input=True, include_output=True)
    passed = all(result.value for case in report.cases for result in case.assertions.values())
    sys.exit(0 if passed else 1)
```

```sh
docker compose exec api uv run python eval_narrative.py
```
</details>
