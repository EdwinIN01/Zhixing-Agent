from typing import Optional, List, Annotated, TypedDict, Dict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class State(TypedDict):
    message: Annotated[list[BaseMessage], add_messages]
    user_query: str
    intent: str
    extracted_slots: dict
    candidate_routes: list[dict]
    retrieved_knowledge: str
    final_response: Optional[str]
    user_selected_route_id: Optional[str]
    image_base64: Optional[str]
    image_description: Optional[str]

def get_initial_state():
    return {
        "message": [],
        "user_query": "",
        "intent": "",
        "extracted_slots": {},
        "candidate_routes": [],
        "retrieved_knowledge": "",
        "final_response": None,
        "user_selected_route_id": None,
        "image_base64": None,
        "image_description": None
    }
