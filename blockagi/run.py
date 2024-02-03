import os
import sys

from blockagi.chains import BlockAGIChain
from blockagi.schema import Findings
from blockagi.tools import DDGSearchAnswerTool, DDGSearchLinksTool, GoogleSearchLinksTool, VisitWebTool
from langchain.chat_models import ChatOpenAI

# commonモジュールをインポートする
COMMON_MOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../common"))
print("COMMON_MOD_DIR=", COMMON_MOD_DIR)
sys.path.append(COMMON_MOD_DIR)


from yka_langchain import yka_get_llm


def run_blockagi(
    agent_role,
    openai_api_key,
    openai_model,
    resource_pool,
    objectives,
    blockagi_callback,
    llm_callback,
    iteration_count,
):
    tools = []
    if os.getenv("GOOGLE_API_KEY") and os.getenv("GOOGLE_CSE_ID"):
        tools.append(GoogleSearchLinksTool(resource_pool))

    tools.extend(
        [
            DDGSearchAnswerTool(),
            DDGSearchLinksTool(resource_pool),
            VisitWebTool(resource_pool),
        ]
    )

    blockagi_callback.on_log_message(
        f"Using {len(tools)} tools:\n"
        + "\n".join([f"{idx+1}. {t.name} - {t.description}" for idx, t in enumerate(tools)])
    )
    llm = yka_get_llm()
    # llm = ChatOpenAI(
    #     temperature=0.8,
    #     streaming=True,
    #     model=openai_model,
    #     openai_api_key=openai_api_key,
    #     callbacks=[llm_callback],
    # )  # type: ignore

    inputs = {
        "objectives": objectives,
        "findings": Findings(
            narrative="Nothing",
            remark="",
            generated_objectives=[],
        ),
    }

    BlockAGIChain(
        iteration_count=iteration_count,
        agent_role=agent_role,
        llm=llm,
        tools=tools,
        resource_pool=resource_pool,
        callbacks=[blockagi_callback],
    )(inputs=inputs)
