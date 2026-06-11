# 项目架构

## 前端 (frontend/)
- `frontend/index.html`：主页面，HTML结构 + CSS样式 + 脚本引用（442行）
- `frontend/js/utils.js`：全局状态管理、DOM辅助函数、消息渲染工具（76行）
- `frontend/js/history.js`：历史会话持久化（localStorage），新建/加载/清除对话（90行）
- `frontend/js/map.js`：高德地图集成，初始化和渲染路线、标记点、地图控件（258行）
- `frontend/js/chat.js`：聊天交互，发送消息、SSE流处理、路线选择卡片（236行）

## 后端 (backend/)
- `main.py`：FastAPI应用入口，API路由、SSE流、静态文件挂载
- `backend/agent/`：LangGraph Agent工作流节点
- `backend/tools/`：高德地图API工具（地理编码、路线规划、POI搜索）
- `backend/rag/`：RAG检索增强（ChromaDB + sentence-transformers）