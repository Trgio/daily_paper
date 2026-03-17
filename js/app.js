// 默认数据源
const DEFAULT_DATA_SOURCE = './data/papers.json';

// 更新页面日期
function initPage() {
    const dateElement = document.getElementById('update-date');
    if (dateElement) {
        dateElement.textContent = `更新时间: ${new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })}`;
    }
}

// 获取论文数据并渲染
async function loadPapers() {
    initPage();

    // 优先使用全局指定的数据源，否则使用默认
    const dataSource = window.PAPER_DATA_SOURCE || DEFAULT_DATA_SOURCE;

    try {
        const response = await fetch(dataSource);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const papers = await response.json();
        renderPapers(papers);
    } catch (error) {
        console.error('加载论文数据失败:', error);
        const container = document.getElementById('papers-container');
        if (container) {
            container.innerHTML = `
                <div class="text-center py-12">
                    <p class="text-red-500 mb-4">加载数据失败: ${error.message}</p>
                    <p class="text-gray-500">请确保数据文件存在或稍后刷新重试</p>
                </div>
            `;
        }
    }
}

// 渲染论文卡片
function renderPapers(papers) {
    const container = document.getElementById('papers-container');
    if (!container) return;

    if (!papers || papers.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-center">暂无论文数据</p>';
        return;
    }

    const papersHTML = papers.map(paper => createPaperCard(paper)).join('');
    container.innerHTML = papersHTML;
}

// 创建单个论文卡片
function createPaperCard(paper) {
    // 构建期刊和作者单位信息
    let metaInfo = '';

    // 添加期刊名称（如果有）
    if (paper.publication_title) {
        metaInfo += `<p class="text-purple-600 text-sm mb-1"><strong>期刊:</strong> ${paper.publication_title}</p>`;
    }

    // 添加作者
    if (paper.authors) {
        metaInfo += `<p class="text-gray-600 text-sm mb-1"><strong>作者:</strong> ${paper.authors}</p>`;
    }

    // 添加作者单位（如果有）
    if (paper.author_info) {
        metaInfo += `<p class="text-gray-500 text-sm mb-3"><strong>单位:</strong> ${paper.author_info}</p>`;
    }

    return `
        <article class="bg-white rounded-lg shadow-md mb-8 p-6">
            <h2 class="text-xl font-bold text-gray-800 mb-2">
                <a href="${paper.url}" target="_blank" class="hover:text-blue-600 transition-colors">
                    ${paper.title}
                </a>
            </h2>
            ${metaInfo}
            <div class="bg-blue-50 border-l-4 border-blue-500 p-3 mb-4">
                <p class="text-gray-700 font-medium">${paper.ai_summary}</p>
            </div>
            <p class="text-gray-600 mb-4">${paper.abstract}</p>
            <div class="flex justify-between items-center text-sm">
                <span class="text-gray-400">发表日期: ${paper.published_date}</span>
                <a href="${paper.url}" target="_blank" class="text-blue-500 hover:text-blue-700">查看原文 →</a>
            </div>
        </article>
    `;
}

// 页面加载完成后获取数据
document.addEventListener('DOMContentLoaded', loadPapers);
