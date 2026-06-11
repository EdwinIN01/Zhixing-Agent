from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn
import uuid
import json
import asyncio
import os
from backend.agent.graph import build_agent
from backend.agent.state import get_initial_state
from langchain_core.messages import HumanMessage, AIMessage

app = FastAPI(title="路线规划智能体 API")

# 挂载前端静态文件
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="frontend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = build_agent()
sessions = {}

class ChatRequest(BaseModel):
    user_query: str
    image_base64: Optional[str] = None
    session_id: Optional[str] = None

class RouteSelection(BaseModel):
    session_id: str
    selected_route_id: str

@app.post("/api/select-route")
async def select_route(request: RouteSelection):
    """处理用户选择路线的请求"""
    if request.session_id not in sessions:
        return {
            "status": "error",
            "response": "会话不存在或已过期"
        }
    
    session = sessions[request.session_id]
    pending_interrupt = session.get("pending_interrupt")
    
    if not pending_interrupt or pending_interrupt.get("type") != "route_selection":
        return {
            "status": "error",
            "response": "当前没有待选择的路线"
        }
    
    routes = pending_interrupt.get("routes", [])
    selected_route = None
    
    # 找到用户选择的路线
    for route in routes:
        if route.get("id") == request.selected_route_id:
            selected_route = route
            break
    
    if not selected_route:
        return {
            "status": "error",
            "response": f"未找到ID为 {request.selected_route_id} 的路线"
        }
    
    # 生成选中路线的详细回复
    if selected_route.get("type") == "route":
        # 路线详情
        response_text = f"✅ 您选择了以下路线：\n\n"
        response_text += f"📍 {selected_route.get('summary', '路线详情')}\n\n"
        
        # 添加距离和耗时
        distance = selected_route.get('distance', 0)
        duration = selected_route.get('duration', 0)
        response_text += f"🚗 距离：{distance/1000:.1f} 公里\n"
        response_text += f"⏱️ 耗时：{duration/60:.0f} 分钟\n\n"
        
        # 如果有收费信息
        tolls = selected_route.get('tolls', 0)
        if tolls > 0:
            response_text += f"💰 过路费：{tolls:.2f} 元\n\n"
        
        # 添加地图链接
        map_url = selected_route.get('map_url', '')
        if map_url:
            origin_coord = selected_route.get('origin_coord', '')
            dest_coord = selected_route.get('dest_coord', '')
            
            # 由于高德静态图API限制，提供坐标链接
            if origin_coord and dest_coord:
                map_link = f"https://uri.amap.com/marker?position={dest_coord}&src=route_planner&callnative=1"
                response_text += f"🗺️ **查看路线地图：**\n"
                response_text += f"点击链接在地图上查看：{map_link}\n\n"
                response_text += f"或者复制以下坐标到高德地图APP：\n"
                response_text += f"起点：{origin_coord}\n"
                response_text += f"终点：{dest_coord}\n"
        
        # 添加步骤信息
        steps = selected_route.get('steps', [])
        if steps:
            response_text += f"📋 **导航步骤：**\n"
            for i, step in enumerate(steps[:5]):  # 只显示前5步
                instruction = step.get('instruction', '')
                if instruction:
                    response_text += f"{i+1}. {instruction}\n"
            
            if len(steps) > 5:
                response_text += f"...（共 {len(steps)} 步）\n"
    else:
        # POI详情
        response_text = f"✅ 您选择了：\n\n"
        response_text += f"📍 **{selected_route.get('name', '地点名称')}**\n"
        
        address = selected_route.get('address', '')
        if address:
            response_text += f"📬 地址：{address}\n"
        
        distance = selected_route.get('distance', 0)
        if distance:
            response_text += f"📏 距离：{distance} 米\n"
        
        rating = selected_route.get('rating', '')
        if rating:
            response_text += f"⭐ 评分：{rating}\n"
    
    session["pending_interrupt"] = None
    
    return {
        "status": "success",
        "response": response_text
    }

@app.get("/")
async def read_root():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "路线规划智能体 API 服务"}

async def generate_chunks(text: str, chunk_size: int = 10):
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]
        await asyncio.sleep(0.05)

async def stream_response(session_id: str, user_query: str, image_base64: Optional[str] = None):
    if session_id not in sessions:
        initial_state = get_initial_state()
        sessions[session_id] = {
            "config": {"configurable": {"thread_id": session_id}},
            "pending_interrupt": None,
            "state": initial_state
        }
    
    session = sessions[session_id]
    config = session["config"]
    current_state = session["state"]
    
    # 重置临时状态字段，但保留对话历史
    current_state["user_query"] = user_query
    current_state["image_base64"] = image_base64
    current_state["intent"] = ""  # 重置意图
    current_state["extracted_slots"] = {}  # 重置提取的槽
    current_state["candidate_routes"] = []  # 重置候选路线
    current_state["retrieved_knowledge"] = ""  # 重置检索到的知识
    current_state["final_response"] = None  # 重置最终响应
    current_state["user_selected_route_id"] = None  # 重置用户选择的路线
    current_state["image_description"] = None  # 重置图片描述
    
    if "message" not in current_state:
        current_state["message"] = []
    current_state["message"].append(HumanMessage(content=user_query))
    
    try:
        result = await agent.ainvoke(current_state, config)
        session["state"] = result
        
        # 安全检查 result 类型
        if isinstance(result, dict) and result.get("pending_selection"):
            routes = result.get("routes", [])
            # 确保 routes 是列表
            if not isinstance(routes, list):
                routes = []
                
            # 安全获取推荐 ID
            recommended_id = ""
            if routes and len(routes) > 0 and isinstance(routes[0], dict):
                recommended_id = routes[0].get("id", "")
            
            session["pending_interrupt"] = {
                "type": "route_selection",
                "routes": routes,
                "recommended_id": recommended_id
            }
            
            response_msg = result.get("final_response", "请选择路线") if isinstance(result, dict) else "请选择路线"
            session["state"]["message"].append(AIMessage(content=response_msg))
            
            pending_data = {
                "type": "pending_selection",
                "message": response_msg,
                "data": session["pending_interrupt"],
                "session_id": session_id
            }
            yield f"data: {json.dumps(pending_data)}\n\n"
            return
        
        session["pending_interrupt"] = None
        
        final_response = result.get("final_response") if isinstance(result, dict) else None
        if final_response is None:
            final_response = "处理完成"
        
        session["state"]["message"].append(AIMessage(content=final_response))
        
        async for chunk in generate_chunks(str(final_response)):
            stream_data = {"type": "stream", "content": chunk}
            yield f"data: {json.dumps(stream_data)}\n\n"
        
        yield 'data: {"type": "end", "content": "", "session_id": "' + session_id + '"}\n\n'
        
    except Exception as e:
        print(f"[ERROR] stream_response: {e}")
        import traceback
        traceback.print_exc()
        error_data = {"type": "error", "content": f"处理请求时出错: {str(e)}"}
        yield f"data: {json.dumps(error_data)}\n\n"

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.session_id:
        request.session_id = str(uuid.uuid4())
    
    return StreamingResponse(
        stream_response(request.session_id, request.user_query, request.image_base64),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": request.session_id
        }
    )

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not request.session_id:
        request.session_id = str(uuid.uuid4())
    
    if request.session_id not in sessions:
        initial_state = get_initial_state()
        sessions[request.session_id] = {
            "config": {"configurable": {"thread_id": request.session_id}},
            "pending_interrupt": None,
            "state": initial_state
        }
    
    session = sessions[request.session_id]
    config = session["config"]
    current_state = session["state"]
    
    # 重置临时状态字段，但保留对话历史
    current_state["user_query"] = request.user_query
    current_state["image_base64"] = request.image_base64
    current_state["intent"] = ""  # 重置意图
    current_state["extracted_slots"] = {}  # 重置提取的槽
    current_state["candidate_routes"] = []  # 重置候选路线
    current_state["retrieved_knowledge"] = ""  # 重置检索到的知识
    current_state["final_response"] = None  # 重置最终响应
    current_state["user_selected_route_id"] = None  # 重置用户选择的路线
    current_state["image_description"] = None  # 重置图片描述
    
    if "message" not in current_state:
        current_state["message"] = []
    current_state["message"].append(HumanMessage(content=request.user_query))
    
    try:
        result = await agent.ainvoke(current_state, config)
        
        session["state"] = result
        
        # 安全检查 result 类型
        if isinstance(result, dict) and result.get("pending_selection"):
            routes = result.get("routes", [])
            # 确保 routes 是列表
            if not isinstance(routes, list):
                routes = []
                
            # 安全获取推荐 ID
            recommended_id = ""
            if routes and len(routes) > 0 and isinstance(routes[0], dict):
                recommended_id = routes[0].get("id", "")
            
            session["pending_interrupt"] = {
                "type": "route_selection",
                "routes": routes,
                "recommended_id": recommended_id
            }
            
            response_msg = result.get("final_response", "请选择路线") if isinstance(result, dict) else "请选择路线"
            session["state"]["message"].append(AIMessage(content=response_msg))
            
            return {
                "session_id": request.session_id,
                "status": "pending_selection",
                "message": response_msg,
                "data": session["pending_interrupt"]
            }
        
        session["pending_interrupt"] = None
        
        final_response = result.get("final_response") if isinstance(result, dict) else None
        if final_response is None:
            final_response = "处理完成"
        
        session["state"]["message"].append(AIMessage(content=final_response))
        
        return {
            "session_id": request.session_id,
            "status": "success",
            "response": str(final_response)
        }
        
    except Exception as e:
        print(f"[ERROR] chat: {e}")
        import traceback
        traceback.print_exc()
        return {
            "session_id": request.session_id,
            "status": "error",
            "response": f"处理请求时出错: {str(e)}"
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
