from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from backend.tools.tools import search_poi_around, get_driving_route, simple_geocode
from backend.agent.state import State
from backend.model.factory import visual_model, chat_model
from backend.rag.retriever import RerankRetriever
from backend.rag.vectorstore import load_vectorstore
from langchain_core.messages import HumanMessage, AIMessage
from backend.utils.prompt_load import (
    load_intent_prompts, load_image_prompts, load_eval_prompts,
    load_route_intro_prompts, load_multi_route_prompts,
    load_poi_selection_prompts, load_direct_reply_prompts,
    load_direct_reply_history_prompts
)
import json
from langgraph.types import interrupt

# ===== 加载所有 prompt 模板 =====
IMAGE_ANALYSIS_PROMPT = load_image_prompts()
INTENT_PROMPT = load_intent_prompts()
EVAL_PROMPT = load_eval_prompts()
ROUTE_INTRO_PROMPT = load_route_intro_prompts()
MULTI_ROUTE_PROMPT = load_multi_route_prompts()
POI_SELECTION_PROMPT = load_poi_selection_prompts()
DIRECT_REPLY_PROMPT = load_direct_reply_prompts()
DIRECT_REPLY_HISTORY_PROMPT = load_direct_reply_history_prompts()

_vectorstore = load_vectorstore("rag/chroma.db")
retriever = RerankRetriever(_vectorstore)

# ===== 图片理解节点 =====
async def understand_image(state):
    if not state["image_base64"]:
        return {}
    llm = visual_model
    msg = HumanMessage(content=[
        {"type": "text", "text": IMAGE_ANALYSIS_PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{state['image_base64']}"}}
    ])
    response = await llm.ainvoke([msg])
    desc = response.content
    enhanced_query = state["user_query"]
    if desc:
        enhanced_query = f"{state['user_query']}\n【图片信息】{desc}" if state["user_query"] else desc
    return {"image_description": desc, "user_query": enhanced_query}

# ===== 意图识别节点 =====
async def understand_intent(state):
    prompt = ChatPromptTemplate.from_template(INTENT_PROMPT)
    llm = chat_model
    chain = prompt | llm | JsonOutputParser()
    try:
        result = await chain.ainvoke({"user_query": state["user_query"]})
        if isinstance(result, str):
            result = json.loads(result)
        intent = result.get("intent", "general_chat") if isinstance(result, dict) else "general_chat"
        slots = result.get("slots", {}) if isinstance(result, dict) else {}
        if not isinstance(slots, dict):
            slots = {}
        return {"intent": intent, "extracted_slots": slots}
    except Exception as e:
        print(f"[ERROR] understand_intent 失败: {e}")
        return {"intent": "general_chat", "extracted_slots": {}}

# ===== 知识检索节点 =====
async def retrieve_knowledge(state):
    slots = state["extracted_slots"]
    origin = slots.get("origin", "")
    destination = slots.get("destination", "")
    keyword = slots.get("keyword", "")

    queries = [f"{origin} 到 {destination} 沿途 交通管制 道路封闭 施工"]
    if keyword:
        queries.append(f"{origin} 附近 {keyword}")

    all_docs = []
    seen_contents = set()
    for q in queries:
        docs = retriever.retrieve(q, top_n=5)
        for doc in docs:
            if doc.page_content not in seen_contents:
                all_docs.append(doc)
                seen_contents.add(doc.page_content)

    knowledge = "\n\n".join([doc.page_content for doc in all_docs[:5]])
    return {"retrieved_knowledge": knowledge}

# ===== 路线规划节点（从 plan_routes 拆分出来）=====
async def plan_route(state):
    """处理路线规划意图：地理编码 + 调用高德驾车路线 API"""
    slots = state["extracted_slots"]
    user_query = state["user_query"]

    if not isinstance(slots, dict):
        slots = {}

    origin_name = slots.get("origin")
    dest_name = slots.get("destination")

    # 简单降级解析
    if (not origin_name or not dest_name) and "到" in user_query:
        parts = user_query.split("到")
        if len(parts) >= 2:
            origin_name = parts[0].strip()
            dest_name = parts[1].strip()

    if not origin_name or not dest_name:
        return {"candidate_routes": [], "final_response": "请提供明确的起点和终点，例如：从北京到上海怎么走"}

    try:
        origin_coord = await simple_geocode(origin_name)
        dest_coord = await simple_geocode(dest_name)

        route_result = await get_driving_route(
            origin=origin_coord,
            destination=dest_coord,
            avoid_tolls=slots.get("avoid_tolls", False)
        )

        routes_list = route_result.get("routes", []) if isinstance(route_result, dict) else []

        routes = []
        for i, route in enumerate(routes_list):
            if isinstance(route, dict):
                routes.append({
                    "type": "route",
                    "id": f"route_{i}",
                    "summary": route.get("summary", f"路线{i+1}"),
                    "distance": route.get("distance", 0),
                    "duration": route.get("duration", 0),
                    "polyline": route.get("polyline", ""),
                    "map_url": route.get("map_url", ""),
                    "steps": route.get("steps", []),
                    "tolls": route.get("tolls", 0),
                    "origin_coord": origin_coord,
                    "dest_coord": dest_coord,
                })

        if not routes:
            return {"candidate_routes": [], "final_response": f"正在帮您查找从{origin_name}到{dest_name}的路线，当前网络可能有些延迟，请换个方式描述试试。"}
        return {"candidate_routes": routes}
    except Exception as e:
        print(f"[ERROR] plan_route 失败: {e}")
        return {"candidate_routes": [], "final_response": f"抱歉，规划路线时遇到问题：{str(e)}"}

# ===== POI 搜索节点（从 plan_routes 拆分出来）=====
async def search_poi(state):
    """处理 POI 搜索意图"""
    slots = state["extracted_slots"]
    if not isinstance(slots, dict):
        slots = {}

    location_name = slots.get("location") or slots.get("origin")
    keyword = slots.get("keyword")
    radius = slots.get("radius", 2000)

    if not location_name or not keyword:
        return {"candidate_routes": [], "final_response": "请告诉我您想在哪儿搜索什么，例如：天安门附近的停车场"}

    try:
        center_coord = await simple_geocode(location_name)
        pois = await search_poi_around.ainvoke({"location": center_coord, "keywords": keyword, "radius": radius})
        if not isinstance(pois, list):
            pois = []
        return {"candidate_routes": pois}
    except ValueError as e:
        return {"candidate_routes": [], "final_response": str(e)}
    except Exception as e:
        print(f"[ERROR] search_poi 失败: {e}")
        return {"candidate_routes": [], "final_response": f"地点搜索失败: {str(e)}"}

# ===== 评估和优化节点 =====
async def evaluate_and_optimize(state):
    routes = state["candidate_routes"]
    final_response = state.get("final_response")
    intent = state.get("intent", "")

    if final_response:
        return {"final_response": final_response}

    if not routes:
        if intent == "poi_search":
            return {"final_response": "没有找到相关的地点，请调整搜索关键词或位置。"}
        elif intent == "route_plan":
            return {"final_response": "没有找到可行的路线，请调整起终点或偏好。"}
        else:
            return {"final_response": "抱歉，我无法处理这个请求。"}

    is_poi_search = len(routes) > 0 and routes[0].get("type") == "poi"

    # ---- 单条路线 ----
    if len(routes) == 1 and not is_poi_search:
        route = routes[0]
        prompt = ChatPromptTemplate.from_template(ROUTE_INTRO_PROMPT)
        chain = prompt | chat_model

        distance = route.get("distance", 0)
        duration = route.get("duration", 0)

        response = await chain.ainvoke({
            "summary": route.get("summary", ""),
            "distance": f"{distance/1000:.1f}公里",
            "duration": f"{duration/60:.0f}分钟",
        })

        response_text = response.content

        origin_coord = route.get("origin_coord", "")
        dest_coord = route.get("dest_coord", "")
        if dest_coord:
            map_link = f"https://uri.amap.com/marker?position={dest_coord}&src=route_planner&callnative=1"
            response_text += f"\n\n📍 点击查看地图：{map_link}"

        return {"final_response": response_text}

    # ---- 多条 POI 结果 ----
    if is_poi_search:
        items_summary = "\n".join([
            f"{i+1}. {r.get('name', '')} - {r.get('address', '')}"
            for i, r in enumerate(routes)
        ])
        prompt = ChatPromptTemplate.from_template(POI_SELECTION_PROMPT)
        intro_resp = await chat_model.ainvoke(prompt.format_messages(items_summary=items_summary))
        intro_msg = intro_resp.content.strip()

        items_info = "\n".join([
            f"{i+1}. **{r.get('name', '')}** - {r.get('address', '')}"
            for i, r in enumerate(routes)
        ])
        response_text = f"{intro_msg}\n\n地点选项：\n{items_info}\n\n请告诉我你想选择哪一个（输入数字1、2或3）？"
    else:
        # 多条路线
        routes_summary = "\n".join([
            f"{i+1}. {r.get('summary', '')}" for i, r in enumerate(routes)
        ])
        prompt = ChatPromptTemplate.from_template(MULTI_ROUTE_PROMPT)
        intro_resp = await chat_model.ainvoke(prompt.format_messages(routes_summary=routes_summary))
        intro_msg = intro_resp.content.strip()

        routes_info = []
        for i, route in enumerate(routes):
            info = f"{i+1}. **{route.get('summary', '')}**"
            routes_info.append(info)
        response_text = f"{intro_msg}\n\n路线选项：\n" + "\n".join(routes_info) + "\n\n请告诉我你想选择哪一条路线（输入数字1、2或3）？"

        if routes and routes[0].get("dest_coord"):
            map_link = f"https://uri.amap.com/marker?position={routes[0].get('dest_coord')}&src=route_planner&callnative=1"
            response_text += f"\n\n📍 点击查看地图概览：{map_link}"

    return {"final_response": response_text, "pending_selection": True, "routes": routes}

# ===== 生成最终回复节点 =====
async def generate_response(state):
    text = state["final_response"] or "抱歉，我暂时无法处理这个请求。"
    return {"messages": [AIMessage(content=text)]}

# ===== 直接回复节点 =====
async def direct_reply(state):
    messages = state.get("message", [])
    conversation_history = "\n".join([
        f"{'用户' if isinstance(msg, HumanMessage) else '助手'}: {msg.content}"
        for msg in messages[:-1]
    ])

    if conversation_history:
        prompt = ChatPromptTemplate.from_template(DIRECT_REPLY_HISTORY_PROMPT)
        chain = prompt | chat_model
        resp = await chain.ainvoke({
            "conversation_history": conversation_history,
            "user_query": state["user_query"],
        })
    else:
        prompt = ChatPromptTemplate.from_template(DIRECT_REPLY_PROMPT)
        chain = prompt | chat_model
        resp = await chain.ainvoke({"user_query": state["user_query"]})

    return {"messages": [AIMessage(content=resp.content)], "final_response": resp.content}