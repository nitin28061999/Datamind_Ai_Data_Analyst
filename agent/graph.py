"""
The LangGraph workflow that powers the assistant.

Flow:
    classify_intent
         |
         +-- data_question --> plan_and_execute (LangChain tool-calling agent) --> END
         |
         +-- greeting/unsupported --> direct_response --> END

classify_intent and (optionally) the final synthesis text are routed through
Langbase pipes, with a local Gemini fallback — see langbase_client.py.
"""
import os
from typing import Literal

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, ToolMessage

from .state import AgentState
from .tools import TOOLS, store
from .langbase_client import run_langbase_pipe

llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    temperature=0,
)
llm_with_tools = llm.bind_tools(TOOLS)


def classify_intent_node(state: AgentState) -> AgentState:
    query = state["user_query"]

    def fallback(_msgs):
        prompt = (
            "Classify this user message into exactly one label: "
            "data_question, greeting, unsupported.\n"
            f'Message: "{query}"\n'
            "Reply with only the label."
        )
        return llm.invoke(prompt).content.strip().lower()

    label = run_langbase_pipe(
        "intent-classifier",
        [{"role": "user", "content": query}],
        fallback_fn=fallback,
    ).strip().lower()

    if "data" in label:
        intent = "data_question"
    elif "greet" in label:
        intent = "greeting"
    else:
        intent = "unsupported" if store.df is None else "data_question"

    return {**state, "intent": intent}


def route_after_intent(state: AgentState) -> Literal["plan_query", "direct_response"]:
    return "plan_query" if state["intent"] == "data_question" else "direct_response"


def direct_response_node(state: AgentState) -> AgentState:
    if state["intent"] == "greeting":
        response = (
            "Hi! I'm your AI data analyst. Load a dataset on the left, then ask "
            "me anything about it — totals, trends, comparisons, breakdowns."
        )
    else:
        response = "I can only answer questions about a loaded dataset right now — please upload a CSV first."
    return {**state, "final_response": response}


def plan_and_execute_node(state: AgentState) -> AgentState:
    """Runs the LangChain tool-calling agent to get real numbers out of the dataframe.
    Deliberately does NOT ask the LLM to write the final prose here — that's
    handed off to synthesize_insight_node so the datamind-ai-analyst pipe
    (or its local fallback) is the one framing the answer for the user.
    """
    messages = list(state["messages"]) + [HumanMessage(content=state["user_query"])]
    ai_msg = llm_with_tools.invoke(messages)
    messages.append(ai_msg)

    tool_outputs = []
    if getattr(ai_msg, "tool_calls", None):
        for call in ai_msg.tool_calls:
            tool_fn = next((t for t in TOOLS if t.name == call["name"]), None)
            result = tool_fn.invoke(call["args"]) if tool_fn else f"Unknown tool: {call['name']}"
            tool_outputs.append(f"{call['name']}({call['args']}) -> {result}")
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
    else:
        # Model answered without needing a tool (e.g. it could infer the answer
        # from context already in the conversation).
        tool_outputs.append(f"(no tool call) -> {ai_msg.content}")

    return {**state, "messages": messages, "tool_result": "\n".join(tool_outputs)}


def synthesize_insight_node(state: AgentState) -> AgentState:
    """
    Hands the user's question + the raw tool output to the datamind-ai-analyst
    Langbase pipe, which is prompted to behave like a data analyst: interpret
    the numbers, call out a business insight, and suggest a KPI or SQL/Python
    snippet where useful. Falls back to a local Gemini call with an equivalent
    instruction if Langbase isn't configured.
    """
    question = state["user_query"]
    tool_result = state["tool_result"] or "No tool output was produced."

    def fallback(_msgs):
        prompt = (
            "You are a data analyst. A user asked a question about their dataset, "
            "and a tool already computed the raw result below. Write a clear, "
            "professional answer that states the number plainly, adds one relevant "
            "insight or comparison if the data supports it, and stays concise "
            "(3-5 sentences). Do not invent numbers beyond what's given.\n\n"
            f"User question: {question}\n"
            f"Raw tool output: {tool_result}"
        )
        return llm.invoke(prompt).content

    response_text = run_langbase_pipe(
        "datamind-ai-analyst",
        [
            {
                "role": "user",
                "content": (
                    f"User question: {question}\n\n"
                    f"Raw computed result from the dataset: {tool_result}\n\n"
                    "Answer the user's question using this result. Add a brief "
                    "business insight or a KPI/SQL suggestion only if it's genuinely "
                    "useful — don't pad the answer."
                ),
            }
        ],
        fallback_fn=fallback,
    )
    return {**state, "final_response": response_text}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("plan_query", plan_and_execute_node)
    graph.add_node("synthesize_insight", synthesize_insight_node)
    graph.add_node("direct_response", direct_response_node)

    graph.set_entry_point("classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route_after_intent,
        {"plan_query": "plan_query", "direct_response": "direct_response"},
    )
    graph.add_edge("plan_query", "synthesize_insight")
    graph.add_edge("synthesize_insight", END)
    graph.add_edge("direct_response", END)

    return graph.compile()
