from langchain_core.tools import tool
import aiohttp
import json
import os
from backend.utils.logger_handler import logger
from backend.rag.retriever import RerankRetriever
from backend.rag.vectorstore import load_vectorstore

AMAP_KEY = os.getenv("AMAP_KEY")
AMAP_GEO_API_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_DRIVING_API_URL = "https://restapi.amap.com/v3/direction/driving"
AMAP_STATIC_MAP_URL = "https://restapi.amap.com/v3/staticmap"

_vectorstore = load_vectorstore("rag/chroma.db")
_retriever = RerankRetriever(_vectorstore)


def decode_amap_polyline(encoded):
    """解码高德地图 polyline 编码为 [[lng, lat], ...]"""
    if not encoded:
        return []
    result = []
    prev_x, prev_y = 0, 0
    i = 0
    while i < len(encoded):
        # 解码经度偏移
        byte = shift = result_byte = 0
        while True:
            byte = ord(encoded[i]) - 63
            i += 1
            result_byte |= (byte & 0x1f) << shift
            shift += 5
            if byte < 0x20:
                break
        dx = ~(result_byte >> 1) if (result_byte & 1) else (result_byte >> 1)
        prev_x += dx
        # 解码纬度偏移
        byte = shift = result_byte = 0
        while True:
            byte = ord(encoded[i]) - 63
            i += 1
            result_byte |= (byte & 0x1f) << shift
            shift += 5
            if byte < 0x20:
                break
        dy = ~(result_byte >> 1) if (result_byte & 1) else (result_byte >> 1)
        prev_y += dy
        result.append([prev_x / 1e5, prev_y / 1e5])
    return result


async def simple_geocode(address):
    """简单的地理编码函数，不使用装饰器"""
    if not AMAP_KEY or AMAP_KEY == "your_amap_api_key":
        raise ValueError("请设置环境变量 AMAP_API_KEY")

    params = {
        "key": AMAP_KEY,
        "address": address
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(AMAP_GEO_API_URL, params=params) as response:
                response.raise_for_status()
                data = await response.json()

            logger.info(f"地理编码响应: {data}")
            
            if isinstance(data, dict) and data.get("status") == "1" and data.get("geocodes"):
                return data["geocodes"][0]["location"]
            else:
                info = data.get("info", "未知错误") if isinstance(data, dict) else "未知错误"
                raise ValueError(f"无法找到地址 '{address}': {info}")
        except Exception as e:
            logger.error(f"地理编码失败: {e}")
            raise ValueError(f"地理编码失败: {str(e)}")


@tool
async def geocode(address):
    """
    将地名转换为高德坐标。用于获取起点、终点、途经点的经纬度坐标。

    Args:
        address: 地点名称，如 "北京天安门"

    Returns:
        坐标字符串，格式为 "lng,lat"，如 "116.397455,39.909187"
    """
    return await simple_geocode(address)


@tool
async def search_poi_around(location, keywords, radius=2000):
    """
    在指定坐标周围搜索地点（POI）。

    Args:
        location: 中心点坐标，格式为 "lng,lat"
        keywords: 搜索关键词，如 "加油站"、"停车场"
        radius: 搜索半径（米），默认2000米

    Returns:
        符合条件的地点列表。
    """
    if not AMAP_KEY or AMAP_KEY == "your_amap_api_key":
        raise ValueError("请设置环境变量 AMAP_API_KEY")

    params = {
        "key": AMAP_KEY,
        "location": location,
        "keywords": keywords,
        "radius": radius
        # 移除硬编码的 types，让它根据关键词搜索所有类型
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://restapi.amap.com/v3/place/around", params=params) as response:
                response.raise_for_status()
                data = await response.json()

            pois = []
            if isinstance(data, dict) and data.get("pois"):
                pois_list = data["pois"]
                if isinstance(pois_list, list):
                    for i, poi in enumerate(pois_list[:5]):
                        if isinstance(poi, dict):
                            pois.append({
                                "type": "poi",
                                "id": f"poi_{i}",
                                "name": poi.get("name", ""),
                                "address": poi.get("address", ""),
                                "location": poi.get("location", ""),
                                "distance": poi.get("distance", 0),
                                "rating": poi.get("rating", ""),
                                "summary": poi.get("name", "")
                            })

            return pois
        except Exception as e:
            logger.error(f"POI搜索失败: {e}")
            return []


async def get_driving_route(origin, destination, avoid_tolls=False, strategy=10, waypoints=None, show_fields="cost,polyline"):
    """
    通过高德驾车路径规划API，获取两点之间的驾车路线信息。
    """
    if not AMAP_KEY or AMAP_KEY == "your_amap_api_key":
        raise ValueError("请设置环境变量 AMAP_API_KEY")

    params = {
        "key": AMAP_KEY,
        "origin": origin,
        "destination": destination,
        "strategy": strategy,
        "extensions": "all",
        "show_fields": show_fields
    }

    if avoid_tolls:
        params["strategy"] = 1
        logger.info("已启用避让收费路段策略")

    if waypoints:
        params["waypoints"] = waypoints
        logger.info(f"添加途经点: {waypoints}")

    async with aiohttp.ClientSession() as session:
        try:
            logger.info(f"请求高德驾车路径规划API: {AMAP_DRIVING_API_URL}")
            async with session.get(AMAP_DRIVING_API_URL, params=params) as response:
                response.raise_for_status()
                raw_response = await response.json()

            return _parse_driving_response(raw_response)

        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {e}")
            return {"status": 0, "error": str(e), "routes": []}
        except json.JSONDecodeError as e:
            logger.error(f"响应解析失败: {e}")
            return {"status": 0, "error": "无效的JSON响应", "routes": []}


def _parse_driving_response(raw_response):
    """
    解析高德驾车路径规划API的原始响应。
    """
    if not isinstance(raw_response, dict):
        logger.error(f"原始响应不是字典: {raw_response}")
        return {"status": 0, "error": "无效的响应格式", "routes": []}

    status_code = raw_response.get("status")
    if status_code != "1":
        info = raw_response.get("info", "UNKNOWN_ERROR")
        infocode = raw_response.get("infocode", "")
        logger.error(f"API返回错误: status={status_code}, info={info}, infocode={infocode}")
        return {
            "status": 0,
            "error": f"[{infocode}] {info}",
            "routes": [],
            "raw_response": raw_response
        }

    route_obj = raw_response.get("route", {})
    if not isinstance(route_obj, dict):
        route_obj = {}
    
    routes_data = route_obj.get("paths", [])
    if not isinstance(routes_data, list):
        routes_data = []
    
    # 高德API返回的 origin 和 destination 是字符串，不是对象
    # 格式如："116.397455,39.9085"
    origin_coord = ""
    dest_coord = ""
    
    # 直接从 route 对象获取字符串坐标
    origin_str = route_obj.get("origin", "")
    dest_str = route_obj.get("destination", "")
    
    if isinstance(origin_str, str) and origin_str:
        origin_coord = origin_str
    elif isinstance(origin_str, dict):
        origin_coord = origin_str.get("location", "")
    
    if isinstance(dest_str, str) and dest_str:
        dest_coord = dest_str
    elif isinstance(dest_str, dict):
        dest_coord = dest_str.get("location", "")
    
    # 如果还是空的，尝试从原始响应中直接获取
    if not origin_coord:
        origin_coord = raw_response.get("origin", "")
    if not dest_coord:
        dest_coord = raw_response.get("destination", "")
    
    logger.info(f"地图坐标 - 起点: {origin_coord}, 终点: {dest_coord}")
    logger.info(f"原始响应 keys: {list(raw_response.keys())}")
    logger.info(f"route 对象 keys: {list(route_obj.keys())}")
    
    if not routes_data:
        logger.warning("API返回成功，但未找到可用路线")
        return {"status": 1, "routes": [], "raw_response": raw_response}

    parsed_routes = []
    for path in routes_data:
        if not isinstance(path, dict):
            continue
            
        distance = int(path.get("distance", 0))
        duration = int(path.get("duration", 0))
        tolls = float(path.get("tolls", 0))
        traffic_lights = int(path.get("traffic_lights", 0))
        restriction = path.get("restriction", "")
        polyline = path.get("polyline", "")
        steps = path.get("steps", [])
        
        if not isinstance(steps, list):
            steps = []

        formatted_steps = []
        for step in steps:
            if isinstance(step, dict):
                formatted_steps.append({
                    "instruction": step.get("instruction", ""),
                    "road": step.get("road", ""),
                    "distance": int(step.get("distance", 0)),
                    "duration": int(step.get("duration", 0)),
                    "polyline": step.get("polyline", ""),
                    "orientation": step.get("orientation", ""),
                    "assistant_action": step.get("assistant_action", "")
                })

        map_url = generate_static_map_url(origin_coord, dest_coord, polyline)

        parsed_routes.append({
            "type": "route",
            "id": f"route_{len(parsed_routes)}",
            "summary": f"距离 {distance / 1000:.1f} 公里，耗时 {duration / 60:.0f} 分钟",
            "distance": distance,
            "duration": duration,
            "tolls": tolls,
            "traffic_lights": traffic_lights,
            "restriction": restriction,
            "polyline": polyline,
            "steps": formatted_steps,
            "map_url": map_url
        })

    logger.info(f"成功解析 {len(parsed_routes)} 条驾车路线")
    return {
        "status": 1,
        "routes": parsed_routes,
        "raw_response": raw_response
    }


def generate_static_map_url(origin, destination, polyline, width=600, height=400):
    """
    生成高德地图静态地图URL，用于显示路线图片。
    """
    if not AMAP_KEY or AMAP_KEY == "your_amap_api_key":
        logger.warning("AMAP_KEY未设置，无法生成地图URL")
        return ""

    try:
        # 验证坐标格式
        if not origin or not destination:
            logger.warning("坐标为空，无法生成地图URL")
            return ""
        
        origin_parts = origin.split(",")
        dest_parts = destination.split(",")
        
        if len(origin_parts) != 2 or len(dest_parts) != 2:
            logger.warning(f"坐标格式错误 - origin: {origin}, destination: {destination}")
            return ""
        
        origin_lng, origin_lat = origin_parts
        dest_lng, dest_lat = dest_parts
        
        # 构建 markers 参数
        markers = f"markers=mid,0xFF0000,A:{origin_lat},{origin_lng}|mid,0x00FF00,B:{dest_lat},{dest_lng}"
        
        # 构建 paths 参数（路线）
        paths = ""
        if polyline and isinstance(polyline, str) and polyline.strip():
            # 将 polyline 转换为静态地图API所需的格式
            # polyline格式: lng1,lat1;lng2,lat2;...
            # 静态地图 paths 格式: weight|color|透明度|polyline
            paths = f"&paths=2|0xFF0000|1|{polyline}"
        
        # 构建完整URL - 包含标记点和路线
        url = f"{AMAP_STATIC_MAP_URL}?key={AMAP_KEY}&size={width}*{height}&{markers}{paths}"
        
        logger.info(f"生成的地图URL: {url[:200]}")
        return url
        
    except Exception as e:
        logger.error(f"生成静态地图URL失败: {e}")
        import traceback
        traceback.print_exc()
        return ""


@tool
def retrieve_traffic_knowledge(query):
    """
    查询交通管制，道路施工、景区开放等实时信息。
    
    Args:
        query: 自然语言查询语句（如 "北京到八达岭 沿途交通管制"）
    
    Returns:
        最相关的前5条文档内容（用换行符分隔）。
    """
    docs = _retriever.retrieve(query, top_n=5)
    if not docs:
        return "未找到相关的交通/景区信息。"
    return "\n\n".join([f"- {doc.page_content}" for doc in docs])


@tool
def retrieve_scenic_info(query):
    """
    从本地知识库检索与行程相关的实时信息，包括交通管制，道路施工、
    景区开放时间、充电桩位置等。
    
    Args:
        query: 自然语言查询，如 "北京到八达岭 沿途交通管制"。
    
    Returns:
        最相关的前 3 条知识片段，以换行分隔。
    """
    docs = _retriever.retrieve(query, top_n=3)
    if not docs:
        return "未找到相关景区信息。"
    return "\n\n".join([f"- {doc.page_content}" for doc in docs])
