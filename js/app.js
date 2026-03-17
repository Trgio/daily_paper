// 更新页面日期
document.getElementById('update-date').textContent = `更新时间: ${new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })}`;

// 获取论文数据并渲染
async function loadPapers() {
    try {
        const response = await fetch('./data/papers.json');
        const papers = await response.json();
        renderPapers(papers);
    } catch (error) {
        console.error('加载论文数据失败:', error);
        document.getElementById('papers-container').innerHTML = '<p class="text-red-500 text-center">加载数据失败，请刷新页面重试。</p>';
    }
}

// 渲染论文卡片
function renderPapers(papers) {
    const container = document.getElementById('papers-container');
    const papersHTML = papers.map(paper => createPaperCard(paper)).join('');
    container.innerHTML = papersHTML;
}

// 创建单个论文卡片
function createPaperCard(paper) {
    return `
        <article class="bg-white rounded-lg shadow-md mb-8 p-6">
            <h2 class="text-xl font-bold text-gray-800 mb-2">
                <a href="${paper.url}" target="_blank" class="hover:text-blue-600 transition-colors">
                    ${paper.title}
                </a>
            </h2>
            <p class="text-gray-600 text-sm mb-4">${paper.authors}</p>
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
