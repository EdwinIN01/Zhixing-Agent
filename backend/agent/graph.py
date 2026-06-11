from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from backend.tools.tools import retrieve_traffic_knowledge
from backend.agent.nodes import (
    understand_image, understand_intent, retrieve_knowledge,
    plan_route, search_poi, evaluate_and_optimize,
    generate_response, direct_reply
)
from backend.agent.state import State
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3


def build_agent(checkpointer_type: str = "memory", db_path: str = "checkpoints.db"):
    builder = StateGraph(State)

    builder.add_node("understand_image", understand_image)
    builder.add_node("understand_intent", understand_intent)
    builder.add_node("retrieve_knowledge", retrieve_knowledge)
    builder.add_node("plan_route", plan_route)
    builder.add_node("search_poi", search_poi)
    builder.add_node("evaluate", evaluate_and_optimize)
    builder.add_node("generate_response", generate_response)
    builder.add_node("direct_reply", direct_reply)

    builder.add_edge(START, "understand_image")
    builder.add_edge("understand_image", "understand_intent")

    def route_by_intent(state: State) -> str:
        if state["intent"] == "route_plan":
            return "retrieve_knowledge"
        elif state["intent"] == "poi_search":
            return "search_poi"
        else:
            return "direct_reply"

    builder.add_conditional_edges("understand_intent", route_by_intent, {
        "retrieve_knowledge": "retrieve_knowledge",
        "search_poi": "search_poi",
        "direct_reply": "direct_reply",
    })

    builder.add_edge("retrieve_knowledge", "plan_route")
    builder.add_edge("plan_route", "evaluate")
    builder.add_edge("search_poi", "evaluate")
    builder.add_edge("evaluate", "generate_response")
    builder.add_edge("generate_response", END)
    builder.add_edge("direct_reply", END)

    if checkpointer_type == "sqlite":
        conn = sqlite3.connect(db_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
    else:
        checkpointer = MemorySaver()

    agent = builder.compile(checkpointer=checkpointer)
    return agent