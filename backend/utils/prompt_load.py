from backend.utils.config_handler import prompts_config
from backend.utils.logger_handler import logger
from backend.utils.path_tool import get_abs_path


def _load_prompt(key: str) -> str:
    """通用的 prompt 加载函数"""
    try:
        path = prompts_config[key]
    except KeyError as e:
        logger.error(f"在yaml配置项中没有 {key} 配置项")
        raise e
    try:
        return open(get_abs_path(path), "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"加载提示词 [{key}] 出错，{str(e)}")
        raise e


def load_eval_prompts():
    return _load_prompt("eval_prompt_path")


def load_image_prompts():
    return _load_prompt("image_prompt_path")


def load_intent_prompts():
    return _load_prompt("intent_prompt_path")


def load_route_intro_prompts():
    return _load_prompt("route_intro_prompt_path")


def load_multi_route_prompts():
    return _load_prompt("multi_route_prompt_path")


def load_poi_selection_prompts():
    return _load_prompt("poi_selection_prompt_path")


def load_direct_reply_prompts():
    return _load_prompt("direct_reply_prompt_path")


def load_direct_reply_history_prompts():
    return _load_prompt("direct_reply_history_prompt_path")