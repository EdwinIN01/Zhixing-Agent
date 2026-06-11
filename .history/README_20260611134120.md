# 智能路线规划助手

一个基于 FastAPI + HTML/JS/CSS 的智能路线规划应用，集成了 AI 大模型、高德地图 API 和本地知识库检索。

## 项目结构

```
- agent-main/
├── backend/              # 后端代码
│   ├── agent/           # Agent逻辑（LangGraph工作流）
│   ├── model/           # 模型工厂
│   ├── rag/             # 知识检索（ChromaDB）
│   ├── tools/           # 工具函数（地图API、POI搜索等）
│   └── utils/           # 工具类（Prompt管理等）
├── frontend/            # 前端代码（纯 HTML/JS/CSS）
│   ├── js/
│   │   ├── utils.js     # 状态管理 + 工具函数
│   │   ├── history.js   # 历史会话持久化
│   │   ├── map.js       # 地图可视化
│   │   └── chat.js      # 聊天交互 + 路线选择
│   ├── index.html       # 主页面
│   └── style.css        # 样式
├── memory-bank/         # 知识库文档
├── main.py             # FastAPI 主入口
└── .env               # 环境变量配置
```

## 环境配置

在项目根目录创建 `.env` 文件，配置以下内容：

```env
# 高德地图 API Key（地图可视化 + 路线规划 + POI搜索必需）
AMAP_KEY=your_amap_api_key_here

# 阿里云 DashScope API（AI 大模型必需）
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

## 安装依赖


```bash
pip install fastapi uvicorn aiohttp python-dotenv langgraph chromadb sentence-transformers
```

## 运行项目

在项目根目录运行：

```bash
python main.py
```

服务将在 **http://localhost:8000** 启动，浏览器打开该地址即可使用。

## 功能特性

- 🧭 **智能路线规划** — 识别起点/终点，支持纯坐标格式（`lng,lat`）
- 🏙️ **POI 搜索推荐** — 周边加油站、餐厅、停车场等实用地点
- 📍 **地图可视化** — 路线在地图上实时绘制，POI 带彩色标签标记
- 📡 **浏览器定位** — 一键获取当前位置并搜索周边 POI
- 📷 **图片理解支持** — 上传图片辅助识别地点
- 📚 **本地知识库检索** — RAG 增强，基于文档内容回答
- 💾 **多轮对话持久化** — 刷新页面不丢失历史，支持新建对话
- 🎨 **现代化 UI 设计** — 可调整地图高度，路线悬停高亮

## API 接口

### GET /
返回前端主页面（index.html）

### POST /api/chat/stream
发送聊天消息（SSE 流式响应，推荐使用）

请求体：
```json
{
  "user_query": "从北京到上海怎么走",
  "image_base64": null,
  "session_id": null
}
```

### POST /api/chat
发送聊天消息（非流式，返回完整结果）

### POST /api/select-route
选择路线

请求体：
```json
{
  "session_id": "xxx",
  "selected_route_id": "route_0"
}
```

## 技术栈

- **后端**：FastAPI, LangGraph, DashScope (通义千问), aiohttp
- **前端**： HTML/CSS/JavaScript, Marked.js (Markdown渲染), 高德地图 JS API
- **AI**：通义千问大模型, 通义向量模型, 通义重排模型
- **地图**：高德地图 REST API + 高德地图 JS API
- **知识检索**：ChromaDB + sentence-transformers
