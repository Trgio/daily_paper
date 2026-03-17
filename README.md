# 每日论文精选

一个自动化的论文抓取与展示系统，每天从 ArXiv 抓取最新论文，使用 AI 进行评分筛选，展示最具创新性的研究成果。

## 功能特点

- 自动从 ArXiv 抓取相关领域论文
- 使用 MiniMax API 进行 AI 评分和创新性总结
- 每日自动更新 Top 5 论文
- 静态网页展示，无需后端服务器

## 本地运行

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd daily_paper
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# Linux/Mac
export MINIMAX_API_KEY=你的API密钥

# Windows
set MINIMAX_API_KEY=你的API密钥
```

### 4. 运行论文抓取脚本

```bash
python scripts/fetch_papers.py
```

### 5. 启动本地服务器预览

```bash
# Python
python -m http.server 8080

# 或 Node.js
npx serve .
```

访问 http://localhost:8080 查看效果。

## 部署到 GitHub Pages

### 方式一：使用 GitHub Actions 自动部署

1. 在仓库设置中启用 GitHub Pages：
   - 进入 `Settings` > `Pages`
   - Source 选择 `Deploy from a branch`
   - Branch 选择 `gh-pages` / `docs`

2. 添加 GitHub Secrets：
   - 进入仓库 `Settings` > `Secrets and variables` > `Actions`
   - 点击 `New repository secret`
   - Name: `MINIMAX_API_KEY`
   - Value: 你的 MiniMax API Key

3. 工作流会自动每天北京时间 8:00 运行，也可以手动触发

### 方式二：手动部署

```bash
# 安装 gh-pages 依赖
npm install -g gh-pages

# 部署
gh-pages -d .
```

## 项目结构

```
daily_paper/
├── .github/
│   └── workflows/
│       └── daily_update.yml    # 自动更新工作流
├── data/
│   └── papers.json             # 论文数据
├── scripts/
│   └── fetch_papers.py         # 论文抓取脚本
├── js/
│   └── app.js                  # 前端渲染脚本
├── index.html                  # 主页面
├── requirements.txt            # Python 依赖
└── README.md
```

## 配置说明

### 修改搜索主题

编辑 `scripts/fetch_papers.py` 中的 `SEARCH_QUERY` 变量：

```python
SEARCH_QUERY = "你的研究主题"
```

### 修改抓取数量

```python
MAX_PAPERS = 20   # 抓取数量
TOP_N = 5         # 筛选数量
```

## 获取 MiniMax API Key

1. 访问 [MiniMax 开放平台](https://platform.minimax.io/)
2. 注册/登录账号
3. 在控制台创建 API Key
4. 将 Key 添加到 GitHub Secrets

## License

MIT
