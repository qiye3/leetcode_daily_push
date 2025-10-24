# index.py
import requests
import json
import time
import re
from html import unescape
from typing import Optional
import os

# ---------- 配置示例 ----------
# config.json 示例：
# {
#   "WEBHOOK_URL": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
#   "LEETCODE_DOMAIN": "https://leetcode.cn"
# }

# ---------- LeetCode 获取每日一题 ----------
def get_leetcode_daily(domain: str = "https://leetcode.cn") -> Optional[dict]:
    url = f"{domain}/graphql/"
    query = {
        "query": """
        query questionOfToday {
          todayRecord {
            question {
              questionFrontendId
              titleSlug
              translatedTitle
              title
              difficulty
              translatedContent
            }
          }
        }
        """
    }
    try:
        resp = requests.post(url, json=query, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data or "data" not in data or not data["data"].get("todayRecord"):
            raise ValueError("未能从 LeetCode 返回今日题目数据")
        q = data["data"]["todayRecord"][0]["question"]
        return {
            "id": q.get("questionFrontendId"),
            "slug": q.get("titleSlug"),
            "title": q.get("translatedTitle") or q.get("title"),
            "difficulty": q.get("difficulty"),
            "content_html": q.get("translatedContent") or "",
            "url": f"{domain}/problems/{q.get('titleSlug')}"
        }
    except Exception as e:
        print("获取 LeetCode 每日一题失败：", e)
        return None

# ---------- HTML -> Markdown ----------
# ---------- HTML 转 Markdown ----------
def html_to_markdown(html: str) -> str:
    """
    将 LeetCode 返回的 HTML 内容转换为企业微信 Markdown。
    - 代码块用 > 引用风格显示（黑色字体）
    - 换行和段落保留
    - 去掉其他 HTML 标签
    """
    if not html:
        return ""
    
    # 将 <pre> 代码块改成引用风格
    def pre_to_quote(match):
        code = match.group(1)
        code = code.strip("\n")
        # 每行前加 '> '，微信引用显示黑色
        quoted_lines = ["> " + line for line in code.splitlines()]
        return "\n" + "\n".join(quoted_lines) + "\n"
    
    html = re.sub(r"<pre.*?>(.*?)</pre>", pre_to_quote, html, flags=re.S|re.I)
    # 换行处理
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    # 段落处理
    html = re.sub(r"(?i)</p\s*>", "\n\n", html)
    # 删除其他 HTML 标签
    html = re.sub(r"<.*?>", "", html, flags=re.S)
    # HTML 实体转义
    text = unescape(html)
    # 压缩多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 去除行首尾空白
    text = "\n".join([line.rstrip() for line in text.splitlines()])
    return text.strip()


# ---------- 企业微信群聊机器人发送 Markdown ----------
def send_robot_markdown(webhook_url: str, title: str, markdown_content: str) -> bool:
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"## {title}\n\n{markdown_content}"
        }
    }
    try:
        r = requests.post(webhook_url, json=payload, timeout=8)
        j = r.json()
        if j.get("errcode") == 0:
            print("消息推送成功")
            return True
        else:
            print("推送失败：", j)
            return False
    except Exception as e:
        print("发送消息异常：", e)
        return False

# ---------- 主入口 ----------
def main_handler(event, context):

    # 从 GitHub Actions Secrets 读取
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    LEETCODE_DOMAIN = os.environ.get("LEETCODE_DOMAIN", "https://leetcode.cn")

    if not WEBHOOK_URL:
        print("错误：请在环境变量中设置 WEBHOOK_URL")
        return {"status": "config_error"}

    # 获取今日题
    q = get_leetcode_daily(domain=LEETCODE_DOMAIN)
    if not q:
        print("❌ 获取 LeetCode 每日一题失败")
        return {"status": "leetcode_fetch_failed"}

    # 转换 HTML -> Markdown
    body_md = html_to_markdown(q.get("content_html", ""))
    markdown_msg = (
        f"> **题目**: {q.get('title')}\n"
        f"> **难度**: {q.get('difficulty')}\n"
        f"> **链接**: [点击查看题目]({q.get('url')})\n\n"
        f"{body_md}\n\n"
        f"—— 自动推送自github"
    )

    # 发送消息
    ok = send_robot_markdown(WEBHOOK_URL, "📘 LeetCode 每日一题", markdown_msg)
    return {"status": "ok" if ok else "send_failed"}

# ---------- 本地测试 ----------
if __name__ == "__main__":
    print("开始本地测试推送（请确保 config.json 已正确配置）...")
    result = main_handler({}, {})
    print("本地测试结果：", result)
