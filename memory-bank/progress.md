# 开发进度

## 2026-06-10: 前端文件拆分
- 将 `frontend/index.html` 从 1101 行拆分为 5 个文件
- 主 JS 代码（664行）按职责拆分为 4 个模块：utils.js(76)、history.js(90)、map.js(258)、chat.js(236)
- 每个文件均 ≤ 300 行，符合 CLAUDE.md 规则
- 修复引用路径：使用 `/static/js/*.js` 匹配后端 FastAPI StaticFiles 挂载
- 备份原文件到 `index.html.backup`
- 拆分后 index.html 从 1101 行缩减至 442 行