#!/usr/bin/env python3
"""
IEEE/论文抓取与筛选脚本
功能：从Semantic Scholar抓取近1个月的论文，使用MiniMax API进行AI评分，筛选Top 20写入JSON
支持备用ArXiv数据源
"""

import os
import json
import time
import requests
import arxiv
from datetime import datetime, timedelta, timezone

# ============== 配置 ==============
# Semantic Scholar API 搜索主题
SEARCH_QUERY = "power electronics neural network control"
MAX_PAPERS = 60          # 抓取论文数量
TOP_N = 20               # 筛选Top N
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "ieee_papers.json")

# MiniMax API 配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
MINIMAX_API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"
MODEL_NAME = "abab6.5s-chat"

# Semantic Scholar API（可选，需要申请API Key）
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

# 浏览器User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


# ============== 时间工具 ==============
def get_date_range() -> tuple:
    """获取过去1个月的日期范围"""
    today = datetime.now()
    start_date = today - timedelta(days=30)
    return start_date.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def get_date_range_utc() -> tuple:
    """获取过去1个月的UTC日期范围"""
    utc_now = datetime.now(timezone.utc)
    start_date = utc_now - timedelta(days=30)
    return start_date, utc_now


# ============== Semantic Scholar 抓取（带重试）==============
def fetch_with_retry(url: str, headers: dict, params: dict, max_retries: int = 3) -> dict:
    """带重试机制的请求"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 429:
                wait_time = 10 * (attempt + 1)  # 递增等待时间
                print(f"遇到429错误，第 {attempt + 1} 次重试，等待 {wait_time} 秒...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            print(f"请求超时，第 {attempt + 1} 次重试...")
            time.sleep(5)
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise

    return {}


def fetch_semantic_scholar_papers(query: str, max_results: int = 40) -> list:
    """从Semantic Scholar抓取近1个月的论文"""
    start_date, end_date = get_date_range()
    date_range = f"{start_date}:{end_date}"

    print(f"抓取范围: {start_date} ~ {end_date}")

    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT
    }

    params = {
        "query": query,
        "fields": "title,authors,abstract,url,year,publicationDate,externalIds",
        "limit": min(max_results, 100),
        "publicationDateOrYear": date_range,
        "sort": "relevance"
    }

    papers = []
    offset = 0
    batch_size = min(max_results, 100)
    max_retries = 3

    while len(papers) < max_results:
        params["offset"] = offset
        params["limit"] = min(batch_size, max_results - len(papers))

        try:
            result = fetch_with_retry(SEMANTIC_SCHOLAR_API, headers, params, max_retries)

            if not result:
                print("Semantic Scholar 请求失败，已达最大重试次数")
                break

            data = result.get("data", [])
            if not data:
                break

            for item in data:
                pub_date = item.get("publicationDate", "")
                if not pub_date:
                    year = item.get("year", "")
                    pub_date = f"{year}-01-01" if year else ""

                paper_id = item.get("paperId", "")
                external_ids = item.get("externalIds", {})
                arxiv_id = external_ids.get("ArXiv", "")
                doi = external_ids.get("DOI", "")

                url = item.get("url", "")
                if not url and doi:
                    url = f"https://doi.org/{doi}"
                elif not url and arxiv_id:
                    url = f"https://arxiv.org/abs/{arxiv_id}"

                authors_list = item.get("authors", [])
                authors = ", ".join([a.get("name", "") for a in authors_list[:5]])

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

            # 避免请求过快
            time.sleep(1)

        except Exception as e:
            print(f"抓取失败: {e}")
            break

    return papers


# ============== IEEE Xplore 抓取 ==============
def fetch_ieee_xplore_papers(query: str, max_results: int = 40) -> list:
    """从IEEE Xplore抓取近1个月的论文"""
    print("正在从 IEEE Xplore 抓取论文...")

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    headers = {
        'Accept': 'application/json,text/plain,*/*',
        'Accept-Encoding': 'gzip,deflate,br',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Referer': 'https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true',
        'User-Agent': USER_AGENT
    }

    url = 'https://ieeexplore.ieee.org/rest/search'

    papers = []
    page = 1
    while len(papers) < max_results:
        data = {
            "newsearch": "true",
            "queryText": query,
            "pageNumber": str(page),
        }

        try:
            response = requests.post(
                url=url,
                data=json.dumps(data),
                headers=headers,
                verify=False,
                timeout=30
            )

            if response.status_code != 200:
                print(f"IEEE Xplore 请求失败: HTTP {response.status_code}")
                break

            result = response.json()
            total_records = int(result.get("totalRecords", 0))

            if total_records == 0:
                print("IEEE Xplore 未找到相关论文")
                break

            records = result.get("records", [])
            if not records:
                break

            for record in records:
                try:
                    # 过滤：只保留期刊论文（Journal Articles），排除会议论文
                    content_type = record.get("contentType", "")
                    # 常见期刊类型: "Journals", "IEEE Journals", "Magazines"
                    # 会议类型: "Conferences", "Conference Proceedings"
                    if content_type and "Journal" not in content_type and "Magazine" not in content_type:
                        # 尝试从其他字段判断
                        is_journal = False
                        for key in record:
                            if isinstance(record.get(key), str) and "journal" in record.get(key, "").lower():
                                is_journal = True
                                break
                        if not is_journal:
                            continue

                    # 提取论文信息
                    title = record.get("articleTitle", "")
                    if not title:
                        continue

                    # 获取作者
                    authors_list = record.get("authors", [])
                    authors = ", ".join([a.get("name", "") for a in authors_list]) if authors_list else "未知作者"

                    # 获取摘要
                    abstract = record.get("abstract", "") or "暂无摘要"

                    # 获取发布日期
                    pub_date = ""
                    if record.get("publicationDate"):
                        pub_date = record.get("publicationDate", "")
                    elif record.get("year"):
                        pub_date = str(record.get("year", ""))

                    # 获取URL
                    article_id = record.get("articleNumber", "")
                    url_link = f"https://ieeexplore.ieee.org/document/{article_id}" if article_id else ""

                    paper = {
                        "id": article_id or f"ieee_{len(papers)}",
                        "title": title,
                        "authors": authors,
                        "author_info": "",
                        "abstract": abstract,
                        "url": url_link,
                        "published_date": pub_date
                    }
                    papers.append(paper)

                    if len(papers) >= max_results:
                        break

                except Exception as e:
                    print(f"解析论文失败: {e}")
                    continue

            # 检查是否还有更多页面
            total_pages = int(result.get("totalPages", 1))
            if page >= total_pages:
                break

            page += 1
            time.sleep(1)  # 避免请求过快

        except requests.exceptions.Timeout:
            print("IEEE Xplore 请求超时")
            break
        except requests.exceptions.RequestException as e:
            print(f"IEEE Xplore 请求错误: {e}")
            break
        except Exception as e:
            print(f"IEEE Xplore 抓取失败: {e}")
            break

    print(f"从 IEEE Xplore 成功抓取 {len(papers)} 篇论文")
    return papers


# ============== ArXiv 备用抓取 ==============
def fetch_arxiv_papers_fallback(query: str, max_results: int = 40) -> list:
    """从ArXiv抓取近1个月的论文（备用数据源）"""
    print("正在切换到 ArXiv 备用数据源...")

    start_date, end_date = get_date_range_utc()
    print(f"ArXiv 抓取范围: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} (UTC)")

    client = arxiv.Client()

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    papers = []
    for result in client.results(search):
        published_utc = result.published.replace(tzinfo=timezone.utc) if result.published.tzinfo is None else result.published

        # 过滤：只保留近1个月发布的论文
        if not (start_date <= published_utc <= end_date):
            continue

        paper = {
            "id": result.entry_id.split("/")[-1],
            "title": result.title,
            "authors": ", ".join([author.name for author in result.authors]),
            "author_info": "",
            "abstract": result.summary.replace("\n", " ") or "暂无摘要",
            "url": result.entry_id,
            "published_date": published_utc.strftime("%Y-%m-%d")
        }
        papers.append(paper)

    return papers


# ============== 主抓取函数 ==============
def fetch_ieee_papers(query: str, max_results: int = 40) -> list:
    """抓取论文，优先IEEE Xplore，失败则使用Semantic Scholar，最后ArXiv"""
    # 优先尝试 IEEE Xplore
    print("\n=== 尝试从 IEEE Xplore 抓取 ===")
    papers = fetch_ieee_xplore_papers(query, max_results)

    if len(papers) > 0:
        print(f"从 IEEE Xplore 成功抓取 {len(papers)} 篇论文")
        return papers

    # 备用：Semantic Scholar
    print("\n=== IEEE Xplore 无数据，尝试 Semantic Scholar ===")
    papers = fetch_semantic_scholar_papers(query, max_results)

    if len(papers) > 0:
        print(f"从 Semantic Scholar 成功抓取 {len(papers)} 篇论文")
        return papers

    # 最终备用：ArXiv
    print("\n=== Semantic Scholar 无数据，切换到 ArXiv ===")
    papers = fetch_arxiv_papers_fallback(query, max_results)
    print(f"从 ArXiv 成功抓取 {len(papers)} 篇论文")

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

    author_context = f"\n作者/机构信息: {author_info}" if author_info else ""

    prompt = f"""你是一个严格的AI学术论文评审专家。请根据以下论文的标题和摘要，评估其学术创新性并给出差异化评分。

论文标题：{title}
论文摘要：{abstract}

评分要求：
- 评分范围0-100分，平均分约50-70分
- 只有真正突破性的论文才能得85分以上
- 平庸或常规论文应在40-60分之间
- 不要给所有论文都打高分，必须有差异化

输出格式（必须是有效的JSON）：
{{"score": <整数>, "summary": "<一句话中文总结>"}}
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

        content_clean = re.sub(r'```json\s*', '', content)
        content_clean = re.sub(r'```\s*$', '', content_clean)

        json_match = re.search(r'\{.+\}', content_clean, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                # 提取score，确保是数值
                score_val = parsed.get("score")
                if score_val is not None:
                    score = float(score_val)
                else:
                    # 尝试从其他可能的字段提取
                    score = 50.0

                summary = parsed.get("summary") or "无总结"

                # 调试：打印API返回内容
                print(f"  API返回: score={score}, summary={summary[:20]}...")
                return {"score": score, "summary": summary}
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                print(f"JSON解析错误: {e}, 内容: {content_clean[:100]}...")

        print("警告: 无法解析API返回的JSON，使用默认评分")
        return {"score": 50.0, "summary": "解析失败"}

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

        # 确保score是数值类型
        score_val = ai_result.get("score", 50)
        try:
            paper["ai_score"] = float(score_val)
        except (ValueError, TypeError):
            paper["ai_score"] = 50.0

        paper["ai_summary"] = ai_result.get("summary", "暂无总结")

        # 打印实际得分，便于调试
        print(f"  -> 得分: {paper['ai_score']}, 总结: {paper['ai_summary'][:30]}...")

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
        print(f"\n[1/3] 正在抓取论文: {SEARCH_QUERY}")
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
