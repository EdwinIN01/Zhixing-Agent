import os

def get_project_root() -> str:
    current_file = os.path.abspath(__file__)   # .../backend/utils/path_tool.py
    # 回溯三级：path_tool.py -> utils -> backend -> 项目根
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
    return project_root

def get_abs_path(relative_path: str) -> str:
    project_root=get_project_root()
    return os.path.join(project_root, relative_path)
