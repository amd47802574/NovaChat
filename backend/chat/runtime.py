import os

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from backend.chat.request_context import ChatRequestContext
from backend.tools import (
    analyze_text,
    calculate,
    get_current_time,
    get_current_weather,
    list_documents,
    make_analyze_conversation_history,
    make_search_knowledge_base,
    web_search,
)
from backend.tools.mcp import load_external_mcp_tools_sync

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
    "- 获得 search_knowledge_base 结果后，禁止再次调用任何工具（包括但不仅限于 get_current_weather 或 search_knowledge_base）"
    "知识库检索结果的处理规则："
    "- 如果工具返回以 NEEDS_CLARIFICATION 开头，说明需要澄清问题，请直接向用户提问，不要基于检索到的上下文回答"
    "- 如果工具返回以 NEEDS_SCOPE_SELECTION 开头，说明需要用户选择范围，请直接向用户提问，不要基于检索到的上下文回答"
    "- 如果工具返回以 NO_KNOWLEDGE 开头，请明确告知用户：知识库中未找到相关信息"
    "- 如果检索到的上下文信息不足，请诚实地表示不知道，不要编造事实"
    "- 基于检索到的内容回答时，必须在答案中引用来源索引，例如 [1] 或 [2][3]"
    "- 如果工具结果包含 Step-back Question/Answer，请使用其通用原则进行推理和回答，但不要向用户展示推理过程"
    "网页搜索结果引用规则："
    "- 当答案基于 web_search 工具结果时，必须在正文中相关结论或事实后面行内引用来源，"
    "使用 markdown 链接格式：[标题](链接) 紧跟在对应陈述句末尾"
    "- 不要在回答末尾统一列出「来源：」段落，每个链接就近放在对应内容之后"
    "- 引用的标题应与搜索结果标题保持一致，不要随意改写"
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
    # 动态生成包含模型信息的系统提示词
    model_info_prompt = f"""

【产品身份】
你是星智问答（NovaChat）智能助手。

【底层模型信息】
底层对话模型：{MODEL}
"""
    # 如果配置了不同的快速模型，也注入进去
    if FAST_MODEL and FAST_MODEL != MODEL:
        model_info_prompt += f"辅助/快速模型：{FAST_MODEL}\n"

    model_info_prompt += """
【回答身份相关问题时的规则】
当用户询问「你用什么大模型」时：
- 先说明产品身份（NovaChat）
- 再准确报出底层对话模型名称
- 不要编造厂商、版本或能力
- 如实回答，不要隐瞒或模糊处理
"""
    # 合并原有系统提示词和模型信息
    full_system_prompt = SYSTEM_PROMPT + model_info_prompt

    # 本地工具始终保留作为降级路径，避免 MCP 子进程瞬时失败后能力完全消失。
    local_tools = [
        get_current_weather,
        make_search_knowledge_base(ctx),
        list_documents,
        get_current_time,
        calculate,
        make_analyze_conversation_history(ctx),
        web_search,
        analyze_text,
    ]

    # MCP 工具加载成功时按名称覆盖本地工具；失败时继续使用本地实现。
    external_mcp_tools = load_external_mcp_tools_sync()
    tools_by_name = {tool.name: tool for tool in local_tools}
    tools_by_name.update({tool.name: tool for tool in external_mcp_tools})
    all_tools = list(tools_by_name.values())

    return create_agent(
        model=model,
        tools=all_tools,
        # system_prompt=SYSTEM_PROMPT,
        system_prompt=full_system_prompt,
    )
