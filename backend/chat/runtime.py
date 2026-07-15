import os

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from backend.chat.request_context import ChatRequestContext
from backend.tools import get_current_weather, make_search_knowledge_base

API_KEY = os.getenv("ARK_API_KEY")
MODEL = os.getenv("MODEL")
FAST_MODEL = os.getenv("FAST_MODEL") or MODEL
BASE_URL = os.getenv("BASE_URL")

SYSTEM_PROMPT = (
    "你是星智问答（NovaChat）的智能助手，专注于基于知识库为用户提供准确、可靠的问答服务。"
    "当用户提出问题时，你可以使用工具来协助回答。"
    "对于文档、知识类问题，请使用 search_knowledge_base 工具进行检索。"
    "工具使用规则："
    "- 每轮对话中，同一个工具最多调用一次，禁止重复调用"
    "- 一旦调用了 search_knowledge_base 并获得结果，必须立即基于该结果生成最终答案"
    "- 获得 search_knowledge_base 结果后，禁止再次调用任何工具（包括 get_current_weather 或 search_knowledge_base）"
    "知识库检索结果的处理规则："
    "- 如果工具返回以 NEEDS_CLARIFICATION 开头，说明需要澄清问题，请直接向用户提问，不要基于检索到的上下文回答"
    "- 如果工具返回以 NEEDS_SCOPE_SELECTION 开头，说明需要用户选择范围，请直接向用户提问，不要基于检索到的上下文回答"
    "- 如果工具返回以 NO_KNOWLEDGE 开头，请明确告知用户：知识库中未找到相关信息"
    "- 如果检索到的上下文信息不足，请诚实地表示不知道，不要编造事实"
    "- 基于检索到的内容回答时，必须在答案中引用来源索引，例如 [1] 或 [2][3]"
    "- 如果工具结果包含 Step-back Question/Answer，请使用其通用原则进行推理和回答，但不要向用户展示推理过程"
    "当知识库中没有答案时，请诚实承认不知道，保持专业和可靠。"
)


model = init_chat_model(
    model=MODEL,
    model_provider="openai",
    api_key=API_KEY,
    base_url=BASE_URL,
    temperature=0.3,
    stream_usage=True,
)

fast_model = init_chat_model(
    model=FAST_MODEL,
    model_provider="openai",
    api_key=API_KEY,
    base_url=BASE_URL,
    temperature=0.2,
    stream_usage=True,
)


def create_agent_for_request(ctx: ChatRequestContext):
    return create_agent(
        model=model,
        tools=[
            get_current_weather,
            make_search_knowledge_base(ctx),
        ],
        system_prompt=SYSTEM_PROMPT,
    )
