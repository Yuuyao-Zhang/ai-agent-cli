"""LLM 调用模块.

该模块提供了调用通义千问（Qwen）模型的功能，使用标准库 urllib
直接发送 HTTP 请求，完全不依赖第三方库（如 openai 或 anthropic）。
支持重试机制和指数退避策略。
"""

import json
import sys
import time
import urllib.error
import urllib.request
from typing import List, Dict

from common.config import config
from common.constant import LLM_MAX_RETRIES
from common.io_utils import safe_text

# 引入语义 KV-Cache
try:
    from memory.kv_cache import kv_cache
    KV_CACHE_AVAILABLE = True
except ImportError:
    KV_CACHE_AVAILABLE = False


def _split_stream_text(text: str) -> tuple[str, str]:
    """分割流式文本，处理可能被截断的标签.

    在流式输出中，标签可能被截断，需要正确处理这种情况。

    Args:
        text: 要处理的文本

    Returns:
        (完整文本, 可能的标签后缀) 的元组
    """
    tags = ("<think>", "</think>")
    max_tag_len = max(len(tag) for tag in tags)
    max_check = min(max_tag_len - 1, len(text))
    for i in range(max_check, 0, -1):
        suffix = text[-i:]
        if any(tag.startswith(suffix) for tag in tags):
            return text[:-i], suffix
    return text, ""


def _render_stream_piece(
    piece: str, state: dict[str, bool | str], answer_parts: list[str]
) -> None:
    """渲染流式输出的一个片段.

    处理思考标签和回复内容的显示，支持流式输出。

    Args:
        piece: 要渲染的文本片段
        state: 渲染状态字典
        answer_parts: 用于收集回答内容的列表
    """
    remaining = piece
    while remaining:
        if state["in_think"]:
            idx = remaining.find("</think>")
            if idx == -1:
                if remaining:
                    if not state["think_header_printed"]:
                        print("\n[思考] ", end="", flush=True)
                        state["think_header_printed"] = True
                    print(safe_text(remaining), end="", flush=True)
                return
            think_text = remaining[:idx]
            if think_text:
                if not state["think_header_printed"]:
                    print("\n[思考] ", end="", flush=True)
                    state["think_header_printed"] = True
                print(safe_text(think_text), end="", flush=True)
            state["in_think"] = False
            remaining = remaining[idx + len("</think>"):]
        else:
            idx = remaining.find("<think>")
            if idx == -1:
                if remaining:
                    if not state["answer_header_printed"]:
                        print("\n[回复] ", end="", flush=True)
                        state["answer_header_printed"] = True
                    print(safe_text(remaining), end="", flush=True)
                    answer_parts.append(remaining)
                return
            answer_text = remaining[:idx]
            if answer_text:
                if not state["answer_header_printed"]:
                    print("\n[回复] ", end="", flush=True)
                    state["answer_header_printed"] = True
                print(safe_text(answer_text), end="", flush=True)
                answer_parts.append(answer_text)
            state["in_think"] = True
            remaining = remaining[idx + len("<think>"):]


def call_qwen(
    messages: List[Dict[str, str]],
    model: str = None,
    api_key: str | None = None,
    base_url: str = None,
    stream: bool = False,
    use_cache: bool = True  # 新增参数
) -> str:
    """调用通义千问（Qwen）模型的函数.

    使用标准库 urllib 直接发送 HTTP 请求。
    集成 Semantic KV-Cache 以避免重复计算。

    Args:
        messages: 对话历史列表
        model: 模型名称
        api_key: API 密钥
        base_url: API 基础 URL
        stream: 是否流式输出
        use_cache: 是否使用语义缓存 (默认 True)

    Returns:
        模型生成的文本内容
    """
    # 0. 检查缓存 (Semantic KV-Cache)
    if use_cache and KV_CACHE_AVAILABLE and not stream:
        # 将消息列表序列化为查询字符串 (Key)
        query_text = json.dumps(messages, ensure_ascii=False)
        cached_response = kv_cache.get(query_text)
        if cached_response:
            print("[LLM] Cache Hit! Using Semantic KV-Cache result.")
            return cached_response

    # 配置加载优先级：参数 > 环境变量 > 默认值
    model = model or config.get_llm_model()
    base_url = base_url or config.get_llm_base_url()
    api_key = api_key or config.get_llm_api_key()

    if not api_key:
        print(
            "[LLM Error] Missing API Key. Please set DASHSCOPE_API_KEY.",
            file=sys.stderr
        )
        return ""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 构造请求数据
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream
    }
    
    # 简单的可观测性：记录开始时间
    start_time = time.time()
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url, data=data, headers=headers, method="POST"
    )

    for attempt in range(LLM_MAX_RETRIES):
        try:
            with urllib.request.urlopen(req) as response:
                if stream:
                    answer_parts = []
                    stream_state: dict[str, bool | str] = {
                        "in_think": False,
                        "think_header_printed": False,
                        "answer_header_printed": False,
                        "pending": ""
                    }
                    for line in response:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data_json = json.loads(data_str)
                                chunk = data_json["choices"][0]["delta"].get("content", "")
                                if chunk:
                                    merged = str(stream_state["pending"]) + chunk
                                    piece, pending = _split_stream_text(merged)
                                    stream_state["pending"] = pending
                                    if piece:
                                        _render_stream_piece(
                                            piece, stream_state, answer_parts
                                        )
                            except json.JSONDecodeError:
                                continue
                    if stream_state["pending"]:
                        _render_stream_piece(
                            str(stream_state["pending"]), stream_state, answer_parts
                        )
                        stream_state["pending"] = ""
                    if (
                        stream_state["think_header_printed"]
                        or stream_state["answer_header_printed"]
                    ):
                        print()
                    content = "".join(answer_parts)
                    
                    # 记录结束时间和Token估算
                    duration = time.time() - start_time
                    print(f"[Metrics] Latency: {duration:.2f}s | Approx Tokens: {len(content)//4}")
                    
                    # 写入缓存
                    if use_cache and KV_CACHE_AVAILABLE and content:
                        query_text = json.dumps(messages, ensure_ascii=False)
                        kv_cache.set(query_text, content)
                        
                    return content
                else:
                    # 非流式处理
                    result = json.loads(response.read().decode("utf-8"))
                    content = result["choices"][0]["message"]["content"]
                    
                    # 记录结束时间和Token估算
                    duration = time.time() - start_time
                    print(f"[Metrics] Latency: {duration:.2f}s | Approx Tokens: {len(content)//4}")
                    
                    # 写入缓存
                    if use_cache and KV_CACHE_AVAILABLE and content:
                        query_text = json.dumps(messages, ensure_ascii=False)
                        kv_cache.set(query_text, content)
                        
                    return content
        except urllib.error.HTTPError as e:
            # 认证错误 (401/403) 和客户端错误 (400) 不应重试
            if e.code in (400, 401, 403):
                print(
                    f"[LLM Error] Authentication/Client error {e.code}: {e}",
                    file=sys.stderr
                )
                return ""
            # 服务器错误 (500, 502, 503, 504) 可以重试
            if attempt == LLM_MAX_RETRIES - 1:
                print(
                    f"[LLM Error] Request failed after {LLM_MAX_RETRIES} "
                    f"attempts: {e}",
                    file=sys.stderr
                )
                return ""

            # 指数退避: 1s, 2s, 4s
            wait_time = 2 ** attempt
            time.sleep(wait_time)
        except urllib.error.URLError as e:
            if attempt == LLM_MAX_RETRIES - 1:
                print(
                    f"[LLM Error] Request failed after {LLM_MAX_RETRIES} "
                    f"attempts: {e}",
                    file=sys.stderr
                )
                return ""

            # 指数退避: 1s, 2s, 4s
            wait_time = 2 ** attempt
            time.sleep(wait_time)
        except Exception as e:
            print(f"[LLM Error] Unexpected error: {e}", file=sys.stderr)
            return ""

    return ""


def call_qwen_embedding(
    text: str,
    model: str = "text-embedding-v4",
    api_key: str | None = None,
    embedding_url: str = None
) -> List[float]:
    embedding_url = embedding_url or config.get_llm_embedding_url()
    api_key = api_key or config.get_llm_api_key()

    if not api_key:
        print(
            "[LLM Error] Missing API Key. Please set DASHSCOPE_API_KEY.",
            file=sys.stderr
        )
        return []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "input": [text]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        embedding_url, data=data, headers=headers, method="POST"
    )

    for attempt in range(LLM_MAX_RETRIES):
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                data_items = result.get("data", [])
                if not data_items:
                    return []
                embedding = data_items[0].get("embedding", [])
                if isinstance(embedding, list):
                    return embedding
                return []
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403):
                print(
                    f"[LLM Error] Authentication/Client error {e.code}: {e}",
                    file=sys.stderr
                )
                return []
            if attempt == LLM_MAX_RETRIES - 1:
                print(
                    f"[LLM Error] Embedding request failed after {LLM_MAX_RETRIES} "
                    f"attempts: {e}",
                    file=sys.stderr
                )
                return []
            wait_time = 2 ** attempt
            time.sleep(wait_time)
        except urllib.error.URLError as e:
            if attempt == LLM_MAX_RETRIES - 1:
                print(
                    f"[LLM Error] Embedding request failed after {LLM_MAX_RETRIES} "
                    f"attempts: {e}",
                    file=sys.stderr
                )
                return []
            wait_time = 2 ** attempt
            time.sleep(wait_time)
        except Exception as e:
            print(f"[LLM Error] Unexpected embedding error: {e}", file=sys.stderr)
            return []

    return []


if __name__ == "__main__":
    # 示例用法
    test_messages = [{"role": "user", "content": "你好"}]
    print(call_qwen(test_messages))
