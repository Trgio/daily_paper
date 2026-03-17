#!/usr/bin/env python3
"""
AI论文抓取与筛选脚本
功能：从ArXiv抓取昨天发布的论文，使用MiniMax API进行AI评分，筛选Top 5写入JSON
"""

import os
import json
import requests
import arxiv
from datetime import datetime, timedelta, timezone

# ============== 配置 ==============
SEARCH_QUERY = "artificial intelligence OR machine learning OR deep learning"  # 搜索主题
MAX_PAPERS = 50          # 抓取论文数量（过滤后可能不足）
TOP_N = 5                # 筛选Top N
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "ai_papers.json")

# MiniMax API 配置（仅需 API Key）
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
# MiniMax API Endpoint (V2 接口，OpenAI 兼容模式)
MINIMAX_API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"
MODEL_NAME = "abab6.5s-chat"  # 性价比高，支持工具调用


# ============== ArXiv 抓取 ==============
def get_yesterday_date_utc() -> tuple:
    """获取昨天的UTC日期范围"""
    utc_now = datetime.now(timezone.utc)
    yesterday = utc_now - timedelta(days=1)
    yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    return yesterday_start, yesterday_end


def fetch_arxiv_papers(query: str, max_results: int = 50) -> list:
    """从ArXiv抓取昨天发布的论文"""
    client = arxiv.Client()

    # 获取昨天的UTC日期范围
    yesterday_start, yesterday_end = get_yesterday_date_utc()

    print(f"抓取范围: {yesterday_start.strftime('%Y-%m-%d')} ~ {yesterday_end.strftime('%Y-%m-%d')} (UTC)")

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    papers = []
    for result in client.results(search):
        # 获取发表日期（转换为UTC）
        published_utc = result.published.replace(tzinfo=timezone.utc) if result.published.tzinfo is None else result.published
        published_date = published_utc.strftime("%Y-%m-%d")

        # 过滤：只保留昨天发布的论文
        if not (yesterday_start <= published_utc <= yesterday_end):
            continue

        paper = {
            "id": result.entry_id.split("/")[-1],
            "title": result.title,
            "authors": ", ".join([author.name for author in result.authors]),
            "abstract": result.summary.replace("\n", " "),
            "url": result.entry_id,
            "published_date": published_date
        }
        papers.append(paper)

    return papers


# ============== MiniMax API 调用 ==============
def call_minimax_api(title: str, abstract: str) -> dict:
    """调用MiniMax API对论文进行评分"""
    if not MINIMAX_API_KEY:
        print("警告: MINIMAX_API_KEY 未设置，跳过评分")
        return {"score": 50, "summary": "API凭证未配置，跳过评分"}

    import re

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""你是一个AI领域专家，请评估该论文的创新性，仅输出JSON格式，包含得分(score)和精炼总结(summary)。

论文标题：{title}
论文摘要：{abstract}

请严格按照以下JSON格式输出：
{{"score": <0-100的整数>, "summary": <一句话中文精炼总结>}}
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一个专业的AI学术论文评审专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    try:
        response = requests.post(
            MINIMAX_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        # 检查HTTP状态码
        if response.status_code != 200:
            print(f"API错误: HTTP {response.status_code} - {response.text}")
            return {"score": 50, "summary": f"API调用失败(HTTP {response.status_code})"}

        result = response.json()

        # 检查API返回错误
        if "base_resp" in result:
            status_code = result["base_resp"].get("status_code", 0)
            if status_code != 0:
                print(f"API错误: {result['base_resp'].get('status_msg', '未知错误')}")
                return {"score": 50, "summary": f"API调用失败: {result['base_resp'].get('status_msg', '未知错误')}"}

        # 解析API返回的内容
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            print("警告: API返回内容为空")
            return {"score": 50, "summary": "API返回内容为空"}

        # 尝试提取JSON
        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            return json.loads(content)

    except requests.exceptions.Timeout:
        print("错误: API请求超时")
        return {"score": 50, "summary": "API请求超时"}
    except requests.exceptions.RequestException as e:
        print(f"错误: 网络请求失败 - {e}")
        return {"score": 50, "summary": f"网络请求失败: {str(e)}"}
    except json.JSONDecodeError as e:
        print(f"错误: JSON解析失败 - {e}")
        return {"score": 50, "summary": "JSON解析失败"}
    except Exception as e:
        print(f"错误: 未知异常 - {e}")
        return {"score": 50, "summary": f"未知错误: {str(e)}"}


# ============== AI 评分 ==============
def score_papers(papers: list) -> list:
    """对论文进行AI评分"""
    scored_papers = []

    for i, paper in enumerate(papers):
        print(f"正在评分第 {i+1}/{len(papers)} 篇论文: {paper['title'][:50]}...")

        # 调用API获取评分和总结
        ai_result = call_minimax_api(paper["title"], paper["abstract"])

        paper["ai_score"] = ai_result.get("score", 50)
        paper["ai_summary"] = ai_result.get("summary", "暂无总结")

        scored_papers.append(paper)

    return scored_papers


# ============== 主流程 ==============
def main():
    print("=" * 50)
    print("AI论文抓取与筛选系统")
    print("=" * 50)

    # 1. 抓取ArXiv论文（昨天发布的）
    print(f"\n[1/3] 正在从ArXiv抓取昨天发布的论文: {SEARCH_QUERY}")
    papers = fetch_arxiv_papers(SEARCH_QUERY, MAX_PAPERS)
    print(f"成功抓取 {len(papers)} 篇昨天发布的论文")

    if len(papers) == 0:
        print("\n警告: 昨天没有新发布的论文，跳过处理")
        return

    # 2. AI评分
    print(f"\n[2/3] 正在使用MiniMax API进行AI评分...")
    scored_papers = score_papers(papers)

    # 3. 排序并筛选Top N
    scored_papers.sort(key=lambda x: x["ai_score"], reverse=True)
    top_papers = scored_papers[:TOP_N]

    # 4. 写入JSON文件
    print(f"\n[3/3] 正在写入 Top {TOP_N} 到 {OUTPUT_FILE}")

    # 准备输出格式（移除临时字段）
    output_papers = []
    for paper in top_papers:
        output_papers.append({
            "id": paper["id"],
            "title": paper["title"],
            "authors": paper["authors"],
            "abstract": paper["abstract"],
            "ai_summary": paper["ai_summary"],
            "url": paper["url"],
            "published_date": paper["published_date"]
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_papers, f, ensure_ascii=False, indent=2)

    print(f"\n完成！已将 Top {TOP_N} 论文写入 {OUTPUT_FILE}")
    print("\n评分结果：")
    for i, paper in enumerate(top_papers, 1):
        print(f"  {i}. [{paper['ai_score']}分] {paper['title'][:60]}...")


if __name__ == "__main__":
    main()
