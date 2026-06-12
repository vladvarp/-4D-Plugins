/* ========================================
   Общие утилиты и инициализация
======================================== */

// Ждём загрузки DOM перед инициализацией
document.addEventListener('DOMContentLoaded', () => {
    initPage();
});

// Определяем тип текущей страницы и запускаем нужные модули
function initPage() {
    const body = document.body;

    if (body.classList.contains('page-index')) {
        initIndexPage();
    }

    if (body.classList.contains('page-plugin')) {
        initPluginPage();
    }

    if (body.classList.contains('page-guide')) {
        initGuidePage();
    }

    // Инициализируем общие компоненты для всех страниц
    initCopyButtons();
    initTocHighlight();
}

/* ========================================
   Главная страница: загрузка списка плагинов
======================================== */

function initIndexPage() {
    const grid = document.getElementById('plugins-grid');
    const countEl = document.getElementById('plugins-count');

    if (!grid) return;

    // Список плагинов — добавляй сюда новые записи
    // Каждый объект: { id, title, description, icon, tags, version, mdFile }
    const plugins = [
        {
            id: '1',
            title: 'VAr Tools',
            description: 'Набор утилит для Cinema 4D, созданных для ускорения повседневной работы.',
            icon: '✦',
            tags: ['Моделирование', 'Процедурный', 'Автоматизация'],
            version: 'v2.28.0',
            mdFile: 'plugins/VAr_Tools.md'
        },
        {
            id: '2',
            title: 'Camera Resolution Manager',
            description: 'Управление разрешением рендера для каждой камеры в сцене — назначай, активируй и переключай форматы прямо из плавающей панели.',
            icon: '🎥',
            tags: ['Рендер', 'Автоматизация', 'Камера'],
            version: 'v1.4',
            mdFile: 'plugins/camera-resolution-manager.md'
        },
        {
            id: '3',
            title: 'Object Renamer PRO',
            description: 'инструмент для наведения порядка в сцене. Плагин решает одну из самых рутинных задач 3D-художника: быстрое и массовое переименование объектов с полным контролем над результатом.',
            icon: '🔬',
            tags: ['Автоматизация', 'Утилиты'],
            version: 'v2.4',
            mdFile: 'plugins/object-renamer-pro.md'
        }
    ];

    // Рендерим карточки плагинов
    renderPluginCards(grid, plugins);

    // Обновляем счётчик в заголовке секции
    if (countEl) {
        countEl.textContent = plugins.length;
    }

    // Анимируем статистику в hero
    animateStats(plugins.length);
}

// Строим HTML карточки и вставляем в сетку
function renderPluginCards(container, plugins) {
    container.innerHTML = '';

    plugins.forEach(plugin => {
        const card = createPluginCard(plugin);
        container.appendChild(card);
    });


}

// Создаём DOM-элемент карточки плагина
function createPluginCard(plugin) {
    const a = document.createElement('a');
    a.className = 'plugin-card animate-in';
    a.href = `plugin.html?md=${encodeURIComponent(plugin.mdFile)}`;
    a.setAttribute('aria-label', `Открыть страницу плагина ${plugin.title}`);

    // Формируем теги — первый всегда обычный, "Featured" — акцентный
    const tagsHTML = plugin.tags.map(tag => {
        const isFeatured = tag === 'Featured';
        return `<span class="card-tag ${isFeatured ? 'featured' : ''}">${tag}</span>`;
    }).join('');

    a.innerHTML = `
        <div class="card-header">
            <div class="card-icon">${plugin.icon}</div>
            <div class="card-tags">${tagsHTML}</div>
        </div>
        <div class="card-body">
            <h3 class="card-title">${escapeHtml(plugin.title)}</h3>
            <p class="card-description">${escapeHtml(plugin.description)}</p>
        </div>
        <div class="card-footer">
            <span class="card-version">${escapeHtml(plugin.version)}</span>
            <span class="card-arrow" aria-hidden="true">
                <svg viewBox="0 0 12 12" xmlns="http://www.w3.org/2000/svg">
                    <path d="M1 6h10M6 1l5 5-5 5" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </span>
        </div>
    `;

    return a;
}

// Анимируем числовые счётчики в hero секции
function animateStats(pluginCount) {
    const el = document.getElementById('stat-plugins');
    if (!el) return;

    // Считаем от 0 до нужного значения за 800мс
    animateNumber(el, 0, pluginCount, 800);
}

// Анимация числа от start до end
function animateNumber(el, start, end, duration) {
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Easing: ease-out
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (end - start) * eased);
        el.textContent = current;

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

/* ========================================
   Страница плагина: загрузка и рендеринг .md
======================================== */

function initPluginPage() {
    // Читаем параметр ?md= из URL
    const params = new URLSearchParams(window.location.search);
    const mdFile = params.get('md');

    if (!mdFile) {
        showPluginError('Не указан файл плагина', 'Добавь параметр ?md=путь/к/файлу.md в URL страницы.');
        return;
    }

    // Загружаем .md файл и рендерим страницу
    loadAndRenderPlugin(mdFile);
}

// Загружаем .md файл через fetch
async function loadAndRenderPlugin(mdFile) {
    const contentEl = document.getElementById('plugin-content');
    const loadingEl = document.getElementById('plugin-loading');

    try {
        const response = await fetch(mdFile);

        if (!response.ok) {
            throw new Error(`Файл не найден (${response.status})`);
        }

        const markdown = await response.text();

        // Скрываем индикатор загрузки
        if (loadingEl) loadingEl.style.display = 'none';

        // Парсим frontmatter и контент
        const { meta, content } = parseFrontmatter(markdown);

        // Заполняем hero секцию мета-данными
        renderPluginHero(meta);

        // Рендерим основной контент
        if (contentEl) {
            contentEl.innerHTML = renderMarkdown(content);
            contentEl.classList.add('md-content');
        }

        // Заполняем боковую панель
        renderPluginSidebar(meta);

        // Обновляем заголовок страницы
        if (meta.title) {
            document.title = `${meta.title} — C4D Plugins`;
        }

    } catch (error) {
        console.error('Ошибка загрузки плагина:', error);
        if (loadingEl) loadingEl.style.display = 'none';
        showPluginError('Не удалось загрузить плагин', error.message);
    }
}

// Парсим YAML-подобный frontmatter из .md файла
// Формат: --- ключ: значение --- в начале файла
function parseFrontmatter(markdown) {
    const frontmatterRegex = /^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/;
    const match = markdown.match(frontmatterRegex);

    if (!match) {
        // Frontmatter не найден — возвращаем пустые мета и весь текст как контент
        return { meta: {}, content: markdown };
    }

    const frontmatterText = match[1];
    const content = match[2];
    const meta = {};

    // Построчный парсинг ключ: значение
    frontmatterText.split('\n').forEach(line => {
        const colonIndex = line.indexOf(':');
        if (colonIndex === -1) return;

        const key = line.slice(0, colonIndex).trim();
        let value = line.slice(colonIndex + 1).trim();

        // Убираем обрамляющие кавычки если есть
        if ((value.startsWith('"') && value.endsWith('"')) ||
            (value.startsWith("'") && value.endsWith("'"))) {
            value = value.slice(1, -1);
        }

        // Парсим массивы вида [a, b, c]
        if (value.startsWith('[') && value.endsWith(']')) {
            value = value.slice(1, -1)
                .split(',')
                .map(v => v.trim().replace(/^["']|["']$/g, ''))
                .filter(Boolean);
        }

        meta[key] = value;
    });

    return { meta, content };
}

// Заполняем hero секцию на странице плагина
function renderPluginHero(meta) {
    // Иконка
    setElement('plugin-icon', meta.icon || '⬡');

    // Теги
    const tagsEl = document.getElementById('plugin-tags');
    if (tagsEl && meta.tags) {
        const tags = Array.isArray(meta.tags) ? meta.tags : [meta.tags];
        tagsEl.innerHTML = tags.map(tag =>
            `<span class="card-tag">${escapeHtml(tag)}</span>`
        ).join('');
    }

    // Основные поля
    setElement('plugin-name', meta.title || 'Без названия');
    setElement('plugin-tagline', meta.tagline || '');
    setElement('plugin-version', meta.version || '—');
    setElement('plugin-author', meta.author || '—');
    setElement('plugin-updated', meta.updated || '—');
    setElement('plugin-license', meta.license || '—');

    // Ссылка на скачивание
    const downloadBtn = document.getElementById('plugin-download');
    if (downloadBtn && meta.download) {
        downloadBtn.href = meta.download;
    } else if (downloadBtn) {
        downloadBtn.style.display = 'none';
    }

    // Ссылка на GitHub
    const githubBtn = document.getElementById('plugin-github');
    if (githubBtn && meta.github) {
        githubBtn.href = meta.github;
    } else if (githubBtn) {
        githubBtn.style.display = 'none';
    }
}

// Заполняем боковую панель
function renderPluginSidebar(meta) {
    // Совместимость
    const compatEl = document.getElementById('sidebar-compat');
    if (compatEl) {
        const items = [
            { name: 'Cinema 4D', value: meta.cinema4d || '—' },
            { name: 'ОС', value: meta.os || '—' },
            { name: 'Рендерер', value: meta.renderer || '—' },
        ];

        compatEl.innerHTML = items
            .filter(item => item.value !== '—')
            .map(item => `
                <li>
                    <span class="compat-name">${escapeHtml(item.name)}</span>
                    <span class="compat-value">${escapeHtml(item.value)}</span>
                </li>
            `).join('');
    }

    // Теги в боковой панели
    const sideTagsEl = document.getElementById('sidebar-tags');
    if (sideTagsEl && meta.tags) {
        const tags = Array.isArray(meta.tags) ? meta.tags : [meta.tags];
        sideTagsEl.innerHTML = tags.map(tag =>
            `<span class="card-tag">${escapeHtml(tag)}</span>`
        ).join('');
    }
}

/* ========================================
   Конвертер Markdown → HTML
======================================== */

function renderMarkdown(markdown) {
    let html = markdown;

    // Экранируем HTML в исходном тексте для безопасности
    // НО: сохраняем блоки кода отдельно, чтобы не сломать их
    const codeBlocks = [];
    html = html.replace(/```([\w]*)\n([\s\S]*?)```/g, (_, lang, code) => {
        const idx = codeBlocks.length;
        codeBlocks.push(`<pre><code class="language-${lang}">${escapeHtml(code.trimEnd())}</code></pre>`);
        return `%%CODEBLOCK_${idx}%%`;
    });

    // Инлайн код — сохраняем аналогично
    const inlineCodes = [];
    html = html.replace(/`([^`]+)`/g, (_, code) => {
        const idx = inlineCodes.length;
        inlineCodes.push(`<code>${escapeHtml(code)}</code>`);
        return `%%INLINE_${idx}%%`;
    });

    // --- Специальные блоки нашего синтаксиса ---

    // Callout блоки: :::[type] текст :::
    html = html.replace(/:::(info|warning|danger|tip)\n([\s\S]*?):::/g, (_, type, content) => {
        const icons = { info: 'ℹ️', warning: '⚠️', danger: '🚫', tip: '💡' };
        const icon = icons[type] || 'ℹ️';
        return `<div class="callout callout-${type}">
            <span class="callout-icon">${icon}</span>
            <div class="callout-content"><p>${content.trim()}</p></div>
        </div>`;
    });

    // Сетка фич: ::::features ... :::: с пунктами ### Иконка Название / описание
    html = html.replace(/::::features\n([\s\S]*?)::::/g, (_, content) => {
        const items = content.trim().split(/\n(?=###)/).map(block => {
            const lines = block.trim().split('\n');
            const header = lines[0].replace(/^###\s*/, '');
            // Первый символ — иконка, остальное — название
            const iconMatch = header.match(/^(\S+)\s+(.*)/);
            const icon = iconMatch ? iconMatch[1] : '●';
            const title = iconMatch ? iconMatch[2] : header;
            const text = lines.slice(1).join(' ').trim();

            return `<div class="feature-item">
                <div class="feature-icon">${icon}</div>
                <div class="feature-title">${escapeHtml(title)}</div>
                <div class="feature-text">${escapeHtml(text)}</div>
            </div>`;
        });

        return `<div class="feature-grid">${items.join('')}</div>`;
    });

    // Блок changelog: ::::changelog ... ::::
    html = html.replace(/::::changelog\n([\s\S]*?)::::/g, (_, content) => {
        const entries = content.trim().split(/\n(?=###)/).map(block => {
            const lines = block.trim().split('\n');
            const header = lines[0].replace(/^###\s*/, '');
            const [version, date] = header.split(' — ');
            const items = lines.slice(1)
                .filter(l => l.trim().startsWith('-'))
                .map(l => `<div>• ${escapeHtml(l.replace(/^-\s*/, ''))}</div>`)
                .join('');

            return `<div class="changelog-entry">
                <div class="changelog-version">${escapeHtml(version || '')}</div>
                <div>
                    <div class="changelog-date">${escapeHtml(date || '')}</div>
                    <div class="changelog-items">${items}</div>
                </div>
            </div>`;
        });

        return `<div class="changelog">${entries.join('')}</div>`;
    });

    // --- Стандартный Markdown ---

    // Заголовки (от h4 до h1, порядок важен)
    html = html.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');

    // Горизонтальная линия
    html = html.replace(/^---$/gm, '<hr>');

    // Жирный и курсив
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Ссылки и изображения
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" loading="lazy">');
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');

    // Цитата
    html = html.replace(/^>\s+(.+)$/gm, '<blockquote><p>$1</p></blockquote>');

    // Таблицы Markdown
    html = renderMarkdownTables(html);

    // Ненумерованный список
    html = html.replace(/^(\s*[-*+]\s+.+\n?)+/gm, match => {
        const items = match.trim().split('\n')
            .filter(l => l.trim())
            .map(l => `<li>${l.replace(/^\s*[-*+]\s+/, '')}</li>`)
            .join('');
        return `<ul>${items}</ul>`;
    });

    // Нумерованный список
    html = html.replace(/^(\s*\d+\.\s+.+\n?)+/gm, match => {
        const items = match.trim().split('\n')
            .filter(l => l.trim())
            .map(l => `<li>${l.replace(/^\s*\d+\.\s+/, '')}</li>`)
            .join('');
        return `<ol>${items}</ol>`;
    });

    // Параграфы: оборачиваем строки текста не обёрнутые в теги
    html = html.replace(/^(?!<[a-z\/]|%%)(.*\S.*)$/gm, '<p>$1</p>');

    // Восстанавливаем сохранённые блоки кода
    codeBlocks.forEach((block, idx) => {
        html = html.replace(`%%CODEBLOCK_${idx}%%`, block);
    });

    inlineCodes.forEach((code, idx) => {
        html = html.replace(`%%INLINE_${idx}%%`, code);
    });

    return html;
}

// Конвертируем таблицы Markdown
function renderMarkdownTables(html) {
    return html.replace(/(\|.+\|\n\|[-| :]+\|\n(?:\|.+\|\n?)+)/g, tableBlock => {
        const rows = tableBlock.trim().split('\n');
        const headerCells = rows[0].split('|').filter(c => c.trim());
        const bodyRows = rows.slice(2); // пропускаем строку с ---

        const thead = `<thead><tr>${headerCells.map(c => `<th>${c.trim()}</th>`).join('')}</tr></thead>`;
        const tbody = `<tbody>${bodyRows.map(row => {
            const cells = row.split('|').filter(c => c.trim());
            return `<tr>${cells.map(c => `<td>${c.trim()}</td>`).join('')}</tr>`;
        }).join('')}</tbody>`;

        return `<table>${thead}${tbody}</table>`;
    });
}

/* ========================================
   Страница руководства по синтаксису
======================================== */

function initGuidePage() {
    // Инициализируем подсветку активного раздела в оглавлении
    initTocHighlight();
}

/* ========================================
   Подсветка активного пункта в оглавлении
======================================== */

function initTocHighlight() {
    const tocLinks = document.querySelectorAll('.toc-list a');
    if (!tocLinks.length) return;

    // Собираем секции соответствующие пунктам оглавления
    const sections = Array.from(tocLinks).map(link => {
        const id = link.getAttribute('href')?.replace('#', '');
        return id ? document.getElementById(id) : null;
    }).filter(Boolean);

    // Обновляем активный пункт при скролле
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const activeId = entry.target.id;
                tocLinks.forEach(link => {
                    const isActive = link.getAttribute('href') === `#${activeId}`;
                    link.classList.toggle('active', isActive);
                });
            }
        });
    }, { rootMargin: '-20% 0px -60% 0px' });

    sections.forEach(section => observer.observe(section));
}

/* ========================================
   Кнопки копирования кода
======================================== */

function initCopyButtons() {
    // Назначаем обработчики всем кнопкам копирования
    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', handleCopyClick);
    });
}

async function handleCopyClick(e) {
    const btn = e.currentTarget;
    // Ищем блок кода внутри родительского .code-example
    const codeEl = btn.closest('.code-example')?.querySelector('code');
    if (!codeEl) return;

    try {
        await navigator.clipboard.writeText(codeEl.textContent || '');
        // Даём визуальный фидбек
        btn.textContent = '✓ Скопировано';
        setTimeout(() => {
            btn.textContent = 'Копировать';
        }, 2000);
    } catch {
        btn.textContent = 'Ошибка';
    }
}

/* ========================================
   Вспомогательные функции
======================================== */

// Безопасное обновление текста элемента по id
function setElement(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

// Экранирование HTML-спецсимволов
function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Показываем блок с ошибкой на странице плагина
function showPluginError(title, message) {
    const container = document.getElementById('plugin-main');
    if (!container) return;

    container.innerHTML = `
        <div class="error-state">
            <div class="error-icon">⚠️</div>
            <div class="error-title">${escapeHtml(title)}</div>
            <p class="error-message">${escapeHtml(message)}</p>
            <a href="index.html" class="btn btn-secondary" style="margin-top:16px">← Вернуться к плагинам</a>
        </div>
    `;
}
