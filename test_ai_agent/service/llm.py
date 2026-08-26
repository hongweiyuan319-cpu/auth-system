"""
service/llm.py —— LLM 调用封装（外部依赖适配层）

职责：
  1. 统一配置：API key、模型名、接口地址（从环境变量读）
  2. chat()：发一组消息，拿回文本回复（最底层）
  3. chat_json()：让 LLM 返回「严格 JSON」并解析成 Python 对象，失败自动重试
     —— 这是给 requirements.py / debugger.py 用的主力接口

约定：core 里的模块不直接碰 API，都走这一层；
      LLM 输出必须能被 json 解析，由本层保证，解析不了就重试/报错。
"""
import json
import os

import requests

# ── 配置（环境变量，可用 .env.example 作为模板）──
API_KEY = os.getenv("LLM_API_KEY", "")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))


def chat(messages: list, temperature: float = 0.0, max_tokens: int = 2000) -> str:
    """
    最低层：发一组消息给 LLM，返回文本回复。

    messages 示例：
        [{"role": "system", "content": "你是测试工程师"},
         {"role": "user", "content": "请解析以下需求……"}]
    """
    if not API_KEY:
        raise RuntimeError(
            "未配置 LLM_API_KEY。请在环境变量设置后重试：\n"
            "  export LLM_API_KEY=你的key\n"
            "可选：LLM_BASE_URL / LLM_MODEL（默认 DeepSeek）"
        )

    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _extract_json(text: str) -> str:
    """从回复里抠出 JSON：LLM 常会带 ```json ``` 围栏或前后废话。"""
    text = text.strip()
    # 去掉 markdown 围栏
    if text.startswith("```"):
        parts = text.split("\n", 1)
        text = parts[1] if len(parts) > 1 else ""
        text = text.rsplit("```", 1)[0].strip()
    # 掐头去尾到第一个 {/[ 到最后一个 }/]
    start = next((i for i, c in enumerate(text) if c in "{["), -1)
    end = max((i for i, c in enumerate(text) if c in "}]"), default=-1)
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return text


def chat_json(prompt: str, system: str = None, retries: int = 2):
    """
    让 LLM 返回严格 JSON 并解析成 Python 对象（dict / list）。

    流程：发 prompt → 拿文本 → 抠 JSON → 解析
      - 解析失败：重试（retries 次）后仍失败 → 抛异常，由调用方决定怎么处理

    这是 requirements.py / debugger.py 应该用的接口：
      规则、bug 单都是结构化数据，必须由 LLM 按我们的 schema 返回。
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_text = ""
    for attempt in range(retries + 1):
        last_text = chat(messages, temperature=0.0)
        try:
            return json.loads(_extract_json(last_text))
        except json.JSONDecodeError:
            if attempt >= retries:
                break
    raise RuntimeError(f"LLM 返回的不是合法 JSON（重试 {retries} 次后放弃）：\n{last_text[:500]}")
