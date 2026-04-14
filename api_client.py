"""
DeepSeek API 调用封装
"""

import httpx
import os

API_KEY = open(os.path.expanduser("~/.api_keys/deepseek")).read().strip()
BASE_URL = "https://api.deepseek.com"

MODEL = "deepseek-chat"

SYSTEM_PROMPT = open(os.path.expanduser("~/math-error-analyzer/prompt.py")).read()


def analyze_image(image_b64: str, extra_context: str = "") -> dict:
    """
    发送图片到 DeepSeek，返回结构化 JSON 分析结果
    """
    user_content = f"""
这是一道数学错题的拍照图片。请分析并返回以下格式的 JSON（直接返回 JSON，不要加 markdown 标记）：

```json
{{
  "subject": "科目：初中数学",
  "grade": "年级：如初三",
  "error_type": "错误类型：计算错误/概念混淆/审题错误/知识点遗忘/其他",
  "knowledge_point": "涉及的具体知识点，如：一元二次方程根的判别式",
  "root_cause": "错误根因分析，2-3句话",
  "correct_solution": "正确解题思路",
  "similar_problems": ["同类题1", "同类题2", "同类题3"],
  "memory_tip": "记忆口诀或记忆技巧",
  "confidence": 0.0-1.0之间的置信度
}}
```

附加信息：{extra_context}
""".strip()

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": user_content
                    }
                ]
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{BASE_URL}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return content


def analyze_text(question: str, answer: str, student_answer: str, extra_context: str = "") -> dict:
    """
    纯文本模式分析（不需要图片时使用）
    """
    user_content = f"""
题目：{question}
正确答案：{answer}
学生答案：{student_answer}

请分析并返回以下格式的 JSON（直接返回 JSON，不要加 markdown 标记）：

```json
{{
  "subject": "科目",
  "grade": "年级",
  "error_type": "错误类型",
  "knowledge_point": "涉及知识点",
  "root_cause": "错误根因分析",
  "correct_solution": "正确解题思路",
  "similar_problems": ["同类题1", "同类题2", "同类题3"],
  "memory_tip": "记忆口诀或记忆技巧",
  "confidence": 0.0-1.0
}}
```

附加信息：{extra_context}
""".strip()

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{BASE_URL}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
