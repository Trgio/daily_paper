#!/usr/bin/env python3
"""
IEEE/论文抓取与筛选脚本
功能：从Semantic Scholar抓取近1个月的论文，使用MiniMax API进行AI评分，筛选Top 20写入JSON
"""

import os
import json
import requests
from datetime import datetime, timedelta

# ============== 配置 ==============
# Semantic Scholar API 搜索主题
SEARCH_QUERY = "neural network control"
MAX_PAPERS = 60          # 抓取论文数量
TOP_N = 20               # 筛选Top N
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "ieee_papers.json")

# MiniMax API 配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
MINIMAX_API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"
MODEL_NAME = "abab6.5s-chat"

# Semantic Scholar API
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"


# ============== 时间工具 ==============
def get_date_range() -> tuple:
    """获取过去1个月的日期范围"""
    today = datetime.now()
    start_date = today - timedelta(days=30)
    return start_date.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


# ============== Semantic Scholar 抓取 ==============
def fetch_ieee_papers(query: str, max_results: int = 60) -> list:
    """从Semantic Scholar抓取近1个月的论文"""
    start_date, end_date = get_date_range()
    date_range = f"{start_date}:{end_date}"

    print(f"抓取范围: {start_date} ~ {end_date}")

    headers = {
        "Accept": "application/json"
    }

    params = {
        "query": query,
        "fields": "title,authors,abstract,url,year,publicationDate,externalIds",
        "limit": min(max_results, 100),  # API 最大支持 100
        "publicationDateOrYear": date_range,
        "sort": "relevance"
    }

    papers = []
    offset = 0
    batch_size = min(max_results, 100)

    while len(papers) < max_results:
        params["offset"] = offset
        params["limit"] = min(batch_size, max_results - len(papers))

        try:
            response = requests.get(
                SEMANTIC_SCHOLAR_API,
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            data = result.get("data", [])
            if not data:
                break

            for item in data:
                # 解析发表日期
                pub_date = item.get("publicationDate", "")
                if not pub_date:
                    year = item.get("year", "")
                    pub_date = f"{year}-01-01" if year else ""

                # 获取论文ID
                paper_id = item.get("paperId", "")
                external_ids = item.get("externalIds", {})
                arxiv_id = external_ids.get("ArXiv", "")
                doi = external_ids.get("DOI", "")

                # 构建URL
                url = item.get("url", "")
                if not url and doi:
                    url = f"https://doi.org/{doi}"
                elif not url and arxiv_id:
                    url = f"https://arxiv.org/abs/{arxiv_id}"

                # 获取作者和机构信息
                authors_list = item.get("authors", [])
                authors = ", ".join([a.get("name", "") for a in authors_list[:5]])

                # 尝试获取第一作者机构（如果API支持）
                author_info = ""
                if authors_list:
                    first_author = authors_list[0]
                    author_info = first_author.get("authorId", "")

                paper = {
                    "id": paper_id or arxiv_id or doi,
                    "title": item.get("title", ""),
                    "authors": authors,
                    "author_info": author_info,
                    "abstract": item.get("abstract", "") or "暂无摘要",
                    "url": url,
                    "published_date": pub_date
                }
                papers.append(paper)

            offset += len(data)
            if len(data) < batch_size:
                break

        except requests.exceptions.Timeout:
            print("警告: API请求超时")
            break
        except requests.exceptions.RequestException as e:
            print(f"警告: API请求失败 - {e}")
            break
        except json.JSONDecodeError:
            print("警告: 响应JSON解析失败")
            break

    return papers


# ============== MiniMax API 调用 ==============
def call_minimax_api(title: str, abstract: str, author_info: str = "") -> dict:
    """调用MiniMax API对论文进行评分"""
    if not MINIMAX_API_KEY:
        print("警告: MINIMAX_API_KEY 未设置，跳过评分")
        return {"score": 50, "summary": "API凭证未配置，跳过评分"}

    import re

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }

    # 包含作者信息的提示词
    author_context = f"\n作者/机构信息: {author_info}" if author_info else ""

    prompt = f"""你是一个AI学术论文评审专家。请根据以下论文的标题、摘要和作者信息，评估其学术创新性。

论文标题：{title}
论文摘要：{abstract}{author_context}

评分标准：
1. 创新性（40分）：研究问题、方法的独特性和突破程度
2. 技术水平（30分）：理论深度、技术实现的先进性
3. 应用价值（20分）：实际应用前景和影响力
4. 可复现性（10分）：描述清晰度

请严格按照以下JSON格式输出，不要包含任何markdown代码块标记：
{{"score": <0-100的整数>, "summary": <一句话中文精炼总结>}}
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一个专业的AI学术论文评审专家。请严格输出JSON格式。"},
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

        if response.status_code != 200:
            print(f"API错误: HTTP {response.status_code}")
            return {"score": 50, "summary": f"API调用失败(HTTP {response.status_code})"}

        result = response.json()

        if "base_resp" in result:
            status_code = result["base_resp"].get("status_code", 0)
            if status_code != 0:
                print(f"API错误: {result['base_resp'].get('status_msg', '未知错误')}")
                return {"score": 50, "summary": f"API调用失败: {result['base_resp'].get('status_msg', '未知错误')}"}

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            print("警告: API返回内容为空")
            return {"score": 50, "summary": "API返回内容为空"}

        # 移除可能的markdown代码块
        content_clean = re.sub(r'```json\s*', '', content)
        content_clean = re.sub(r'```\s*$', '', content_clean)

        # 使用正则提取第一个 { 到最后一个 } 之间的内容
        json_match = re.search(r'\{.+\}', content_clean, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                # 确保 score 转换为数值类型
                try:
                    score = float(parsed.get("score", 50))
                except (ValueError, TypeError):
                    score = 0.0
                # 确保 summary 有默认值
                summary = parsed.get("summary") or "无总结"
                return {"score": score, "summary": summary}
            except json.JSONDecodeError:
                # 如果正则提取的仍然解析失败，尝试更严格的匹配
                json_match_strict = re.search(r'\{"score":\s*\d+,\s*"summary":\s*".*"\}', content_clean)
                if json_match_strict:
                    parsed = json.loads(json_match_strict.group())
                    try:
                        score = float(parsed.get("score", 50))
                    except (ValueError, TypeError):
                        score = 0.0
                    summary = parsed.get("summary") or "无总结"
                    return {"score": score, "summary": summary}

        # 最终降级方案：返回默认评分
        print("警告: 无法解析API返回的JSON，使用默认评分")
        return {"score": 0.0, "summary": "无总结"}

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
        title = paper.get('title', '未知标题')
        print(f"正在评分第 {i+1}/{len(papers)} 篇论文: {title[:50]}...")
        print(f"当前处理到: {title}")

        ai_result = call_minimax_api(
            paper["title"],
            paper["abstract"],
            paper.get("author_info", "")
        )

        paper["ai_score"] = ai_result.get("score", 50)
        paper["ai_summary"] = ai_result.get("summary", "暂无总结")

        scored_papers.append(paper)

    return scored_papers


# ============== 主流程 ==============
def main():
    import traceback

    print("=" * 50)
    print("IEEE/论文抓取与筛选系统")
    print("=" * 50)

    try:
        # 1. 抓取论文
        print(f"\n[1/3] 正在从Semantic Scholar抓取论文: {SEARCH_QUERY}")
        papers = fetch_ieee_papers(SEARCH_QUERY, MAX_PAPERS)
        print(f"成功抓取 {len(papers)} 篇论文")

        if len(papers) == 0:
            print("\n警告: 没有抓取到论文，请检查API或搜索条件")
            return

        # 2. AI评分
        print(f"\n[2/3] 正在使用MiniMax API进行AI评分...")
        scored_papers = score_papers(papers)

        # 3. 排序并筛选Top N
        scored_papers.sort(key=lambda x: float(x.get("ai_score", 0)) if str(x.get("ai_score", "")).replace(".", "", 1).isdigit() else 0, reverse=True)
        top_papers = scored_papers[:TOP_N]

        # 4. 写入JSON文件
        print(f"\n[3/3] 正在写入 Top {TOP_N} 到 {OUTPUT_FILE}")

        # 检查是否有数据
        if not top_papers:
            print("警告: 没有获取到任何数据")
            return

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

    except Exception as e:
        print(f"\n脚本运行失败: {e}")
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()
