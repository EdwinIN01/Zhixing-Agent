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
import re
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
_coord_in_text_re = None


def _extract_coord_from_text(text):
    """在长文本中找到第一个 'lng,lat' 格式的坐标（纯数字+逗号）。"""
    global _coord_in_text_re
    if _coord_in_text_re is None:
        import re
        _coord_in_text_re = re.compile(r'(-?\d{1,3}\.\d+)\s*[,，]\s*(-?\d{1,3}\.\d+)')
    if not text:
        return None
    m = _coord_in_text_re.search(text)
    if not m:
        return None
    try:
        lng = float(m.group(1))
        lat = float(m.group(2))
    except ValueError:
        return None
    if -180 <= lng <= 180 and -90 <= lat <= 90:
        return f"{lng:.6f},{lat:.6f}"
    return None


async def plan_route(state):
    """处理路线规划意图：地理编码 + 调用高德驾车路线 API"""
    slots = state["extracted_slots"]
    user_query = state["user_query"]

    if not isinstance(slots, dict):
        slots = {}

    origin_name = slots.get("origin") or ""
    dest_name = slots.get("destination") or ""

    origin_name = str(origin_name).strip()
    dest_name = str(dest_name).strip()

    coord_from_text = _extract_coord_from_text(user_query)

    # 模糊值列表（LLM 可能把位置为模糊词，需覆盖为坐标）
    _bad_locations = ("", "这个位置", "当前位置", "这里", "附近", "出发点", "当前的位置")

    # --- 1) 始终优先用从文本提取坐标覆盖模糊的 origin
    if coord_from_text and origin_name in _bad_locations:
        origin_name = coord_from_text
        print(f"[plan_route] 覆盖 origin: '{slots.get('origin', '')}' -> '{coord_from_text}'")

    # --- 2) 如果 origin 为空，从文本提取
    if not origin_name and coord_from_text:
        origin_name = coord_from_text

    # --- 3) "到" 字拆分（简单降级：如 "从北京到上海"）
    if (not origin_name or not dest_name) and "到" in user_query:
        # 去掉结尾的语气词
        q = re.sub(r'[?？!！。.\s]+$', '', user_query)
        parts = q.split("到")
        if len(parts) >= 2:
            left = parts[0].strip()
            right = parts[-1].strip()
            # 去掉前缀
            if left.startswith("从"):
                left = left[1:].strip()
            if not origin_name and left:
                origin_name = left
            if not dest_name and right:
                dest_name = right

    # --- 4) 从文本提取可能的第二个坐标作为 dest
    if not dest_name:
        # 查找第二个坐标（如果有两个）
        all_coords = re.findall(r'(-?\d{1,3}\.\d+)\s*[,，]\s*(-?\d{1,3}\.\d+)', user_query)
        if len(all_coords) >= 2:
            try:
                lng2, lat2 = all_coords[1]
                dest_name = f"{float(lng2):.6f},{float(lat2):.6f}"
                print(f"[plan_route] 从文本提取第二个坐标作为目的地: {dest_name}")
            except (ValueError, IndexError):
                pass

    # --- 5) simple_geocode 能处理纯坐标，直接透传 ---

    if not origin_name:
        return {
            "candidate_routes": [],
            "final_response": "请告诉我您的出发点，例如：从北京出发怎么走，或告诉我具体的地址/坐标。"
        }

    if not dest_name:
        return {
            "candidate_routes": [],
            "final_response": "我已获取到您的出发点，还需要您提供目的地。请告诉我您要去哪里，例如：到上海怎么走？"
        }

    try:
        print(f"[plan_route] 最终参数: origin='{origin_name}', destination='{dest_name}'")
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
                    "decoded_polyline": route.get("decoded_polyline", []),
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
# 常见 POI 关键词字典，用于 LLM slot 提取失败时兜底提取
_POI_KEYWORDS = [
    "加油站", "加气站", "充电桩", "充电站",
    "停车场", "停车位",
    "餐厅", "饭店", "餐馆", "美食", "吃饭",
    "咖啡厅", "咖啡馆", "咖啡",
    "酒店", "宾馆", "住宿",
    "便利店", "超市", "商场",
    "医院", "药店", "诊所",
    "银行", "ATM",
    "学校", "幼儿园",
    "公园", "景点", "景区", "博物馆",
    "卫生间", "厕所",
    "加油站", "银行",
]
_POI_KEYWORDS_PATTERN = re.compile('|'.join(re.escape(k) for k in _POI_KEYWORDS))


def _normalize_keywords(raw_text):
    """把 '加油站、餐厅、停车场' 等多关键词文本标准化为 '加油站|餐厅|停车场'"""
    if not raw_text:
        return ""
    # 去掉多余的 "等"、"实用地点" 等尾部词汇
    cleaned = re.sub(r'(等|实用地点|附近的|周边的|地方)[的]*', '', raw_text)
    # 统一分隔符为 |
    normalized = re.sub(r'[、，,\s;；\|]+', '|', cleaned)
    normalized = normalized.strip('|')
    # 去重并保留顺序
    seen = set()
    parts = []
    for p in normalized.split('|'):
        if p and p not in seen:
            parts.append(p)
            seen.add(p)
    # 高德 API 限制最多 3 个关键词
    return '|'.join(parts[:3])


async def search_poi(state):
    """处理 POI 搜索意图"""
    slots = state["extracted_slots"]
    user_query = state.get("user_query", "")
    if not isinstance(slots, dict):
        slots = {}

    location_name = slots.get("location") or slots.get("origin") or ""
    keyword = slots.get("keyword") or ""
    radius = slots.get("radius", 2000)

    location_name = str(location_name).strip()
    keyword = str(keyword).strip()

    # --- 1) 始终尝试从用户查询提取坐标（优先级最高，避免 LLM 识别为"这个位置"等模糊值）---
    coord_from_text = _extract_coord_from_text(user_query)

    # 如果 slot 的 location 不像坐标也不是明确地址，或者从文本提取到了坐标，优先用坐标
    looks_like_coord = bool(coord_from_text)
    location_looks_bad = location_name in ("", "这个位置", "当前位置", "这里", "附近")
    if looks_like_coord and location_looks_bad:
        location_name = coord_from_text
        print(f"[search_poi] 覆盖 location: '{slots.get('location', '')}' -> '{coord_from_text}'")
    elif not location_name and looks_like_coord:
        location_name = coord_from_text

    # --- 2) 关键词兜底提取 ---
    if not keyword:
        found = _POI_KEYWORDS_PATTERN.findall(user_query)
        if found:
            # 去重保留顺序
            seen = set()
            unique = []
            for k in found:
                if k not in seen:
                    unique.append(k)
                    seen.add(k)
            keyword = '|'.join(unique[:3])
            print(f"[search_poi] 从文本提取关键词: {keyword}")

    # --- 3) 标准化关键词分隔符 ---
    keyword = _normalize_keywords(keyword)

    if not location_name:
        return {
            "candidate_routes": [],
            "final_response": "请告诉我您想搜索的具体位置（地址或坐标），例如：天安门附近的停车场。"
        }

    if not keyword:
        keyword = "加油站|餐厅|停车场"  # 最后兜底：给一组默认实用关键词
        print(f"[search_poi] keyword 为空，使用默认: {keyword}")

    # radius 验证
    try:
        radius = int(radius)
        if radius <= 0 or radius > 50000:
            radius = 2000
    except (ValueError, TypeError):
        radius = 2000

    try:
        print(f"[search_poi] 最终参数: location='{location_name}', keywords='{keyword}', radius={radius}")
        center_coord = await simple_geocode(location_name)
        pois = await search_poi_around.ainvoke({"location": center_coord, "keywords": keyword, "radius": radius})
        if not isinstance(pois, list):
            pois = []
        print(f"[search_poi] 返回 POI 数量: {len(pois)}")
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