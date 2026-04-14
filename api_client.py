"""
DeepSeek API 调用封装
"""

import os
import httpx

API_KEY = os.environ.get("DEEPSEEK_API_KEY") or open(os.path.expanduser("~/.api_keys/deepseek")).read().strip()
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

SYSTEM_PROMPT = os.environ.get("PROMPT_CONTENT") or """你是一个专业的初中数学教师，擅长分析学生的错题，帮助找出错误根因，并提供记忆技巧。

## 角色定位
- 你是初中数学教学专家，尤其擅长分析学生的错误类型
- 你能用学生能理解的语言解释问题，不使用过于专业的术语
- 你善于归纳总结，帮助学生举一反三

## 分析维度
### 错误类型分类
- 计算错误：四则运算、符号处理、移项等基础计算失误
- 概念混淆：对数学概念理解不清，如混淆了方程与不等式的解法
- 审题错误：没有正确理解题目条件，漏看或误解关键信息
- 知识点遗忘：对某些公式、定理记忆模糊或错误
- 思路错误：解题思路整体方向偏离

### 输出要求
- 始终返回结构化 JSON，不包含 markdown 代码块标记
- confidence 字段表示 AI 对分析结果的置信度（0.0-1.0）
- similar_problems 是字符串数组，包含 3 道同类题
- 语言简洁，适合初中生理解"""


def analyze_image(image_b64: str, extra_context: str = "") -> str:
    user_content = f"""这是一道数学错题的拍照图片。请分析并返回以下格式的 JSON（直接返回 JSON，不要加 markdown 标记）：

{{
  "subject": "科目：初中数学",
  "grade": "年级：如初三",
  "error_type": "错误类型：计算错误/概念混淆/审题错误/知识点遗忘/其他",
  "knowledge_point": "涉及的具体知识点",
  "root_cause": "错误根因分析，2-3句话",
  "correct_solution": "正确解题思路",
  "similar_problems": ["同类题1", "同类题2", "同类题3"],
  "memory_tip": "记忆口诀或记忆技巧",
  "confidence": 0.0-1.0之间的置信度
}}

附加信息：{extra_context}""".strip()

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": user_content}
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
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
