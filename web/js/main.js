/* ========================================
   Общие утилиты и инициализация
======================================== */

const modalBlocks = {};

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
    initMdComponents();
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
            icon: 'ico/Var_tools/varp_tools.png',
            tags: ['Моделирование', 'Процедурный', 'Анимация', 'Автоматизация'],
            version: 'v3.29.9',
            mdFile: 'plugins/VAr_Tools.md'
        },
        {
            id: '2',
            title: 'Camera Resolution Manager',
            description: 'Управление разрешением рендера для каждой камеры в сцене — назначай, активируй и переключай форматы прямо из плавающей панели.',
            icon: 'ico/CameraResolution.png',
            tags: ['Рендер', 'Автоматизация', 'Камера'],
            version: 'v1.7.1',
            mdFile: 'plugins/camera-resolution-manager.md'
        },
        {
            id: '3',
            title: 'Object Renamer PRO',
            description: 'Инструмент для наведения порядка в сцене. Плагин решает одну из самых рутинных задач 3D-художника: быстрое и массовое переименование объектов с полным контролем над результатом.',
            icon: 'ico/ObjectRenamerPRO.png',
            tags: ['Автоматизация', 'Утилиты'],
            version: 'v2.6.1',
            mdFile: 'plugins/object-renamer-pro.md'
        },
        {
            id: '4',
            title: 'Snapshot',
            description: 'Мгновенно превращает анимацию объекта в набор статичных мешей — по одному на каждый кадр — и объединяет их в единый полигональный снепшот.',
            icon: 'ico/Snapshot.png',
            tags: ['Анимация', 'Автоматизация', 'Утилиты'],
            version: 'v1.7.1',
            mdFile: 'plugins/snapshot.md'
        },
        {
            id: '5',
            title: 'Selection Sets',
            description: 'Сохранение и восстановление наборов выделения объектов. Каждый набор — это тег (Selection Set Tag) на нулевом объекте внутри контейнера "Selection Sets". Тег хранит имя набора и ссылки на объекты в пользовательских данных (UserData).',
            icon: 'ico/SelectionSet/icon_plugin.png',
            tags: [`Выделение`, `Утилиты`, `Организация`],
            version: 'v1.4.1',
            mdFile: 'plugins/SelectionSet.md'
        },
        {
            id: '6',
            title: 'Floor Generator',
            description: 'Процедурный генератор напольных покрытий — ёлочка, паркет, шеврон, соты — с фаской, швами и рандомизированными UV.',
            icon: 'ico/FloorGenerator.png',
            tags: [`Моделирование`, `Процедурный`],
            version: 'v3.0.1',
            mdFile: 'plugins/floor-generator.md'
        },
        {
            id: '7',
            title: 'Cloud Wizard',
            description: 'Процедурный генератор облаков — кучевые, перистые, грозовые, слоистые и высококучевые.',
            icon: 'ico/CloudWizard.png',
            tags: [`Генератор`, `Процедурный`, `Облака`],
            version: 'v1.8.2',
            mdFile: 'plugins/cloud-wizard.md'
        },
        {
            id: '8',
            title: 'Action Recorder',
            description: 'Записывает действия пользователя в виде Python-кода, автоматически генерируются скрипты, которые можно сохранить, редактировать и запускать одной кнопкой.',
            icon: 'ico/ActionRecorder/Manager.png',
            tags: [`Автоматизация`],
            version: 'v1.14',
            mdFile: 'plugins/action-recorder.md'
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
            <div class="card-icon">${isImagePath(plugin.icon) ? `<img src="${escapeHtml(plugin.icon.trim())}" alt="" loading="lazy" class="card-icon-img">` : plugin.icon}</div>
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
            initMdComponents(contentEl);
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
    // Иконка: либо emoji/символ, либо путь к PNG/SVG/JPG (рендерится как <img>)
    setPluginIcon('plugin-icon', meta.icon);

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

    // --- Специальные блоки нашего синтаксиса ---
    // Сохраняем их в заглушки, чтобы applyStandardMarkdown не обернул
    // внутренние строки в лишние <p>-теги

    const blockSlots = [];
    const saveBlock = (html) => {
        const idx = blockSlots.length;
        blockSlots.push(html);
        return `%%BLOCK_${idx}%%`;
    };

    html = html.replace(/<mdc-n'([^']+)'-s(\d+)\*(\d+)>([\s\S]*?)<\/mdc>/g, (_, id, w, h, content) => {
        modalBlocks[id] = { w: parseInt(w), h: parseInt(h), raw: content };
        return '';
    });

    // Раскрывающийся блок (развёрнут по умолчанию): ::::details-open
    html = html.replace(/::::details-open\n([\s\S]*?)::::/g, (_, content) => {
        return saveBlock(renderDetailsBlock(content, true));
    });

    // Раскрывающийся блок (свёрнут по умолчанию): ::::details
    html = html.replace(/::::details\n([\s\S]*?)::::/g, (_, content) => {
        return saveBlock(renderDetailsBlock(content, false));
    });

    // Вкладки: ::::tabs
    html = html.replace(/::::tabs\n([\s\S]*?)::::/g, (_, content) => {
        return saveBlock(renderTabsBlock(content));
    });

    // Пошаговая инструкция: ::::steps
    html = html.replace(/::::steps\n([\s\S]*?)::::/g, (_, content) => {
        return saveBlock(renderStepsBlock(content));
    });

    // Видео: ::::video
    html = html.replace(/::::video\n([\s\S]*?)::::/g, (_, content) => {
        return saveBlock(renderVideoBlock(content));
    });

    // Callout блоки: :::[type] текст :::
    html = html.replace(/:::(info|warning|danger|tip)\n([\s\S]*?):::/g, (_, type, content) => {
        const icons = { info: 'ℹ️', warning: '⚠️', danger: '🚫', tip: '💡' };
        const icon = icons[type] || 'ℹ️';
        return saveBlock(`<div class="callout callout-${type}"><span class="callout-icon">${icon}</span><div class="callout-content">${renderInlineContent(content.trim())}</div></div>`);
    });

    // Сетка фич: ::::features ... ::::
    html = html.replace(/::::features\n([\s\S]*?)::::/g, (_, content) => {
        const items = content.trim().split(/\n(?=###)/).map(block => {
            const lines = block.trim().split('\n');
            const header = lines[0].replace(/^###\s*/, '');
            const iconMatch = header.match(/^(\S+)\s+(.*)/);
            const icon = iconMatch ? iconMatch[1] : '●';
            const title = iconMatch ? iconMatch[2] : header;
            const text = lines.slice(1).join(' ').trim();
            return `<div class="feature-item"><div class="feature-icon">${icon}</div><div class="feature-title">${renderInlineContent(title)}</div><div class="feature-text">${renderInlineContent(text)}</div></div>`;
        });
        return saveBlock(`<div class="feature-grid">${items.join('')}</div>`);
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
            return `<div class="changelog-entry"><div class="changelog-version">${escapeHtml(version || '')}</div><div><div class="changelog-date">${escapeHtml(date || '')}</div><div class="changelog-items">${items}</div></div></div>`;
        });
        return saveBlock(`<div class="changelog">${entries.join('')}</div>`);
    });

    // Фотокарусель: ===photo -n[Title] -sWxH -c1 -asc200 -asp500 ===
    html = html.replace(/===photo(?:_\w+)?\s*(?:-n\[([^\]]*)\])?\s*(?:-s(\d+)[x*](\d+))?\s*(?:-c([1-3]))?\s*(?:-asc(\d+))?\s*(?:-asp(\d+))?\n([\s\S]*?)===/g, (_, title, w, h, align, asc, asp, content) => {
        return saveBlock(renderPhotoCarousel('photo', title, w, h, content, align, asc, asp));
    });

    // Сравнение фото: ===leveling -n[Title] -sWxH -c1 -asc200 -asp500 ===
    html = html.replace(/===leveling\s*(?:-n\[([^\]]*)\])?\s*(?:-s(\d+)[x*](\d+))?\s*(?:-c([1-3]))?\s*(?:-asc(\d+))?\s*(?:-asp(\d+))?\n([\s\S]*?)===/g, (_, title, w, h, align, asc, asp, content) => {
        return saveBlock(renderLeveling(title || 'Сравнение', parseInt(w) || 600, parseInt(h) || 400, content, align, asc, asp));
    });

    // Колонки: <column>...</column>
    html = html.replace(/<column([^>]*)>([\s\S]*?)<\/column>/g, (_, params, inner) => {
        return saveBlock(renderColumns(inner, params));
    });

    // Экранируем HTML в исходном тексте для безопасности
    // НО: сохраняем блоки кода отдельно, чтобы не сломать их
    const codeBlocks = [];
    const icoSlots = [];
    html = html.replace(/```([\s\S]*?)\n([\s\S]*?)```/g, (_, header, code) => {
        const idx = codeBlocks.length;
        let raw = code.trimEnd();
        const hasIco = header.includes('-ico');
        const hasNum = header.includes('-num');
        const sizeMatch = header.match(/-s(\d+)/);
        const fontSize = sizeMatch ? sizeMatch[1] : '';
        const limitMatch = header.match(/-l(\d+)/);
        const lineHeight = limitMatch ? limitMatch[1] : '';
        const lang = header.replace(/\s*-ico\s*/, '').replace(/\s*-num\s*/, '').replace(/\s*-s\d+\s*/, '').replace(/\s*-l\d+\s*/, '').trim();
        if (hasIco) {
            raw = raw.replace(/\[\[ico:'([^']+)'(?:-(\d+))?\]\]/g, (_, src, h) => {
                const icoIdx = icoSlots.length;
                const style = h
                    ? `height:${h}px;width:auto;object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;`
                    : 'width:36px;height:36px;object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;';
                icoSlots.push(`<img class="md-ico md-ico-code" src="${escapeHtml(src)}" alt="" loading="lazy" style="${style}">`);
                return `%%ICO_${icoIdx}%%`;
            });
        }
        let attrs = '';
        if (fontSize) attrs = ` style="font-size:${fontSize}px"`;
        let codeBlock;
        if (hasNum) {
            const lines = raw.split('\n');
            const lineCount = lines.length;
            const charCount = raw.length;
            const numberedLines = lines.map((line, i) => `<tr><td class="code-num-gutter-cell">${i + 1}</td><td class="code-num-content-cell"><code class="language-${lang}"${attrs}>${escapeHtml(line)}</code></td></tr>`).join('');
            codeBlock = `<div class="code-num" data-code="${escapeHtml(raw)}"><div class="code-num-header"><span class="code-num-lang">${escapeHtml(lang)}</span><button class="code-num-copy" title="Копировать">Копировать</button></div><div class="code-num-body"><table class="code-num-table"><tbody>${numberedLines}</tbody></table></div><div class="code-num-status"><span>${lineCount} ${lineCount === 1 ? 'строка' : lineCount < 5 ? 'строки' : 'строк'}</span><span>${charCount} ${charCount === 1 ? 'символ' : charCount < 5 ? 'символа' : 'символов'}</span></div></div>`;
        } else {
            raw = escapeHtml(raw);
            icoSlots.forEach((ico, i) => { raw = raw.replace(`%%ICO_${i}%%`, ico); });
            codeBlock = `<pre><code class="language-${lang}"${attrs}>${raw}</code></pre>`;
        }
        if (lineHeight) {
            codeBlocks.push(`<div class="code-scroll" style="height:${lineHeight}px;overflow-y:auto">${codeBlock}</div>`);
        } else {
            codeBlocks.push(codeBlock);
        }
        return `%%CODEBLOCK_${idx}%%`;
    });

    // Инлайн код — сохраняем аналогично
    const inlineCodes = [];
    html = html.replace(/`([^`]+)`/g, (_, code) => {
        const idx = inlineCodes.length;
        inlineCodes.push(`<code>${escapeHtml(code)}</code>`);
        return `%%INLINE_${idx}%%`;
    });

    // --- Стандартный Markdown ---

    html = applyStandardMarkdown(html);

    // Восстанавливаем сохранённые блоки кода
    codeBlocks.forEach((block, idx) => {
        html = html.replace(`%%CODEBLOCK_${idx}%%`, block);
    });

    inlineCodes.forEach((code, idx) => {
        html = html.replace(`%%INLINE_${idx}%%`, code);
    });

    // Восстанавливаем спецблоки
    blockSlots.forEach((block, idx) => {
        html = html.replace(`%%BLOCK_${idx}%%`, block);
    });

    // Инлайн-элементы: badge, button, kbd
    html = renderInlineSyntax(html);

    return html;
}

// Раскрывающийся блок: первая строка — заголовок, остальное — содержимое
function renderDetailsBlock(content, isOpen) {
    const lines = content.trim().split('\n');
    const title = lines[0] || 'Подробнее';
    const body = lines.slice(1).join('\n').trim();
    const openAttr = isOpen ? ' open' : '';

    return `<details class="md-details${isOpen ? ' md-details-open' : ''}"${openAttr}>
        <summary class="md-details-summary">
            <span class="md-details-title">${escapeHtml(title)}</span>
            <span class="md-details-chevron" aria-hidden="true"></span>
        </summary>
        <div class="md-details-content">${renderInlineContent(body)}</div>
    </details>`;
}

// Вкладки: каждая секция начинается с ### Название
function renderTabsBlock(content) {
    const tabs = content.trim().split(/\n(?=###)/).filter(Boolean).map((block, index) => {
        const lines = block.trim().split('\n');
        const title = lines[0].replace(/^###\s*/, '');
        const body = lines.slice(1).join('\n').trim();
        const activeClass = index === 0 ? ' active' : '';

        return {
            title: escapeHtml(title),
            nav: `<button type="button" class="md-tab-btn${activeClass}" data-tab="${index}" role="tab" aria-selected="${index === 0}">${escapeHtml(title)}</button>`,
            panel: `<div class="md-tab-panel${activeClass}" data-tab="${index}" role="tabpanel">${renderInlineContent(body)}</div>`
        };
    });

    return `<div class="md-tabs">
        <div class="md-tabs-scroll-wrap">
            <div class="md-tabs-scrollbar"><div class="md-tabs-scrollbar-thumb"></div></div>
            <div class="md-tabs-nav" role="tablist">${tabs.map(t => t.nav).join('')}</div>
        </div>
        <div class="md-tabs-panels">${tabs.map(t => t.panel).join('')}</div>
    </div>`;
}

// Пошаговая инструкция
function renderStepsBlock(content) {
    const steps = content.trim().split(/\n(?=###)/).filter(Boolean).map(block => {
        const lines = block.trim().split('\n');
        const title = lines[0].replace(/^###\s*/, '');
        const body = lines.slice(1).join('\n').trim();

        return `<li class="md-step">
            <div class="md-step-title">${escapeHtml(title)}</div>
            <div class="md-step-content">${renderInlineContent(body)}</div>
        </li>`;
    });

    return `<ul class="md-steps">${steps.join('')}</ul>`;
}

// Видео-блок: первая строка — URL, вторая (опционально) — подпись
function renderVideoBlock(content) {
    const lines = content.trim().split('\n').filter(Boolean);
    const url = lines[0] || '';
    const caption = lines[1] || '';
    const embedUrl = getVideoEmbedUrl(url);

    if (!embedUrl) {
        return `<div class="md-video md-video-error">
            <p>Не удалось встроить видео. Проверьте URL.</p>
            <a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(url)}</a>
        </div>`;
    }

    const captionHtml = caption
        ? `<figcaption class="md-video-caption">${escapeHtml(caption)}</figcaption>`
        : '';

    return `<figure class="md-video">
        <div class="md-video-wrapper">
            <iframe src="${escapeHtml(embedUrl)}" title="${escapeHtml(caption || 'Видео')}" loading="lazy" allowfullscreen allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"></iframe>
        </div>
        ${captionHtml}
    </figure>`;
}

// YouTube / Vimeo → embed URL
function getVideoEmbedUrl(url) {
    const youtubeMatch = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([\w-]+)/);
    if (youtubeMatch) {
        return `https://www.youtube.com/embed/${youtubeMatch[1]}`;
    }

    const vimeoMatch = url.match(/vimeo\.com\/(\d+)/);
    if (vimeoMatch) {
        return `https://player.vimeo.com/video/${vimeoMatch[1]}`;
    }

    return null;
}

// Упрощённый Markdown для содержимого внутри блоков
function renderInlineContent(text) {
    if (!text) return '';

    let html = text;

    // Сохраняем блоки кода
    const codeBlocks = [];
    const icoSlots = [];
    html = html.replace(/```([\s\S]*?)\n([\s\S]*?)```/g, (_, header, code) => {
        const idx = codeBlocks.length;
        let raw = code.trimEnd();
        const hasIco = header.includes('-ico');
        const hasNum = header.includes('-num');
        const sizeMatch = header.match(/-s(\d+)/);
        const fontSize = sizeMatch ? sizeMatch[1] : '';
        const limitMatch = header.match(/-l(\d+)/);
        const lineHeight = limitMatch ? limitMatch[1] : '';
        const lang = header.replace(/\s*-ico\s*/, '').replace(/\s*-num\s*/, '').replace(/\s*-s\d+\s*/, '').replace(/\s*-l\d+\s*/, '').trim();
        if (hasIco) {
            raw = raw.replace(/\[\[ico:'([^']+)'(?:-(\d+))?\]\]/g, (_, src, h) => {
                const icoIdx = icoSlots.length;
                const style = h
                    ? `height:${h}px;width:auto;object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;`
                    : 'width:36px;height:36px;object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;';
                icoSlots.push(`<img class="md-ico md-ico-code" src="${escapeHtml(src)}" alt="" loading="lazy" style="${style}">`);
                return `%%ICO_${icoIdx}%%`;
            });
        }
        let attrs = '';
        if (fontSize) attrs = ` style="font-size:${fontSize}px"`;
        let codeBlock;
        if (hasNum) {
            const lines = raw.split('\n');
            const lineCount = lines.length;
            const charCount = raw.length;
            const numberedLines = lines.map((line, i) => `<tr><td class="code-num-gutter-cell">${i + 1}</td><td class="code-num-content-cell"><code class="language-${lang}"${attrs}>${escapeHtml(line)}</code></td></tr>`).join('');
            codeBlock = `<div class="code-num" data-code="${escapeHtml(raw)}"><div class="code-num-header"><span class="code-num-lang">${escapeHtml(lang)}</span><button class="code-num-copy" title="Копировать">Копировать</button></div><div class="code-num-body"><table class="code-num-table"><tbody>${numberedLines}</tbody></table></div><div class="code-num-status"><span>${lineCount} ${lineCount === 1 ? 'строка' : lineCount < 5 ? 'строки' : 'строк'}</span><span>${charCount} ${charCount === 1 ? 'символ' : charCount < 5 ? 'символа' : 'символов'}</span></div></div>`;
        } else {
            raw = escapeHtml(raw);
            icoSlots.forEach((ico, i) => { raw = raw.replace(`%%ICO_${i}%%`, ico); });
            codeBlock = `<pre><code class="language-${lang}"${attrs}>${raw}</code></pre>`;
        }
        if (lineHeight) {
            codeBlocks.push(`<div class="code-scroll" style="height:${lineHeight}px;overflow-y:auto">${codeBlock}</div>`);
        } else {
            codeBlocks.push(codeBlock);
        }
        return `%%CODEBLOCK_${idx}%%`;
    });
    const inlineCodes = [];
    html = html.replace(/`([^`]+)`/g, (_, code) => {
        const idx = inlineCodes.length;
        inlineCodes.push(`<code>${escapeHtml(code)}</code>`);
        return `%%INLINE_${idx}%%`;
    });

    // Вложенные спец-блоки
    html = html.replace(/::::tabs\n([\s\S]*?)::::/g, (_, content) => renderTabsBlock(content));
    html = html.replace(/::::steps\n([\s\S]*?)::::/g, (_, content) => renderStepsBlock(content));
    html = html.replace(/::::details-open\n([\s\S]*?)::::/g, (_, content) => renderDetailsBlock(content, true));
    html = html.replace(/::::details\n([\s\S]*?)::::/g, (_, content) => renderDetailsBlock(content, false));
    html = html.replace(/:::(info|warning|danger|tip)\n([\s\S]*?):::/g, (_, type, content) => {
        const icons = { info: 'ℹ️', warning: '⚠️', danger: '🚫', tip: '💡' };
        return `<div class="callout callout-${type}"><span class="callout-icon">${icons[type]}</span><div class="callout-content">${renderInlineContent(content.trim())}</div></div>`;
    });

    html = html.replace(/===photo(?:_\w+)?\s*(?:-n\[([^\]]*)\])?\s*(?:-s(\d+)[x*](\d+))?\s*(?:-c([1-3]))?\s*(?:-asc(\d+))?\s*(?:-asp(\d+))?\n([\s\S]*?)===/g, (_, title, w, h, align, asc, asp, content) => {
        return renderPhotoCarousel('photo', title, w, h, content, align, asc, asp);
    });

    html = html.replace(/===leveling\s*(?:-n\[([^\]]*)\])?\s*(?:-s(\d+)[x*](\d+))?\s*(?:-c([1-3]))?\s*(?:-asc(\d+))?\s*(?:-asp(\d+))?\n([\s\S]*?)===/g, (_, title, w, h, align, asc, asp, content) => {
        return renderLeveling(title || 'Сравнение', parseInt(w) || 600, parseInt(h) || 400, content, align, asc, asp);
    });

    // Колонки: <column>...</column>
    html = html.replace(/<column([^>]*)>([\s\S]*?)<\/column>/g, (_, params, inner) => {
        return renderColumns(inner, params);
    });

    html = html.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^###\s+(.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^##\s+(.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^\s*---\s*$/gm, '<hr>');
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" loading="lazy">');
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
    html = html.replace(/^>\s+(.+)$/gm, '<blockquote><p>$1</p></blockquote>');
    html = renderMarkdownTables(html);
    html = html.replace(/^(\s*[-*+]\s+.+\n?)+/gm, match => {
        const items = match.trim().split('\n')
            .filter(l => l.trim())
            .map(l => `<li>${l.replace(/^\s*[-*+]\s+/, '')}</li>`)
            .join('');
        return `<ul>${items}</ul>`;
    });
    html = html.replace(/^(\s*\d+\.\s+.+\n?)+/gm, match => {
        const items = match.trim().split('\n')
            .filter(l => l.trim())
            .map(l => `<li>${l.replace(/^\s*\d+\.\s+/, '')}</li>`)
            .join('');
        return `<ol>${items}</ol>`;
    });
    html = html.replace(/^(?!<[a-z\/]|%%)(.*\S.*)$/gm, '<p>$1</p>');

    // Восстанавливаем блоки кода
    codeBlocks.forEach((block, idx) => {
        html = html.replace(`%%CODEBLOCK_${idx}%%`, block);
    });
    inlineCodes.forEach((code, idx) => {
        html = html.replace(`%%INLINE_${idx}%%`, code);
    });

    return renderInlineSyntax(html);
}

// Стандартный Markdown (заголовки, списки, таблицы и т.д.)
function applyStandardMarkdown(html) {
    html = html.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');

    // Горизонтальная линия
    html = html.replace(/^\s*---\s*$/gm, '<hr>');

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

    return html;
}

function renderIcoInline(text) {
    let r = text;
    r = r.replace(/\[\[ico:'([^']+)'-(x|\d+)(?:-c([1-3]))?\]\]/g, (_, src, size, align) => {
        const ac = align ? ` md-ico-wrap-${['','left','center','right'][align]}` : '';
        const wo = align ? `<span class="md-ico-wrap${ac}">` : '';
        const wc = align ? '</span>' : '';
        if (size === 'x') return `${wo}<img class="md-ico" src="${escapeHtml(src)}" alt="" loading="lazy" style="object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;">${wc}`;
        const h = parseInt(size);
        return `${wo}<img class="md-ico" src="${escapeHtml(src)}" height="${h}" alt="" loading="lazy" style="height:${h}px;width:auto;object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;">${wc}`;
    });
    r = r.replace(/\[\[ico:'([^']+)'\[|:](\d+)[x*](\d+)(?:-c([1-3]))?\]\]/g, (_, src, w, h, align) => {
        const ac = align ? ` md-ico-wrap-${['','left','center','right'][align]}` : '';
        const wo = align ? `<span class="md-ico-wrap${ac}">` : '';
        const wc = align ? '</span>' : '';
        return `${wo}<img class="md-ico" src="${escapeHtml(src)}" width="${parseInt(w)}" height="${parseInt(h)}" alt="" loading="lazy" style="width:${parseInt(w)}px;height:${parseInt(h)}px;object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;">${wc}`;
    });
    r = r.replace(/\[\[ico:'([^']+)'\]\]/g, (_, src) => {
        return `<img class="md-ico" src="${escapeHtml(src)}" width="24" height="24" alt="" loading="lazy" style="width:36px;height:36px;object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;">`;
    });
    return r;
}

// Инлайн-синтаксис: [[badge:...]], [[button:...]], [[kbd:...]]
function renderInlineSyntax(html) {
    // Бейдж: [[badge:тип|текст]] или [[badge:текст]]
    html = html.replace(/\[\[badge:([^\]]+)\]\]/g, (_, raw) => {
        const parts = raw.split('|');
        const type = parts.length > 1 ? parts[0].trim() : 'default';
        const text = parts.length > 1 ? parts.slice(1).join('|').trim() : parts[0].trim();
        const safeType = escapeHtml(type).toLowerCase().replace(/[^a-z0-9-]/g, '');
        return `<span class="md-badge md-badge-${safeType || 'default'}">${escapeHtml(text)}</span>`;
    });

    // Кнопка-ссылка: [[button:Текст|url]]
    html = html.replace(/\[\[button:([^\]|]+)\|([^\]]+)\]\]/g, (_, label, url) => {
        return `<a href="${escapeHtml(url.trim())}" class="md-button" target="_blank" rel="noopener">${escapeHtml(label.trim())}</a>`;
    });

    // Клавиши: [[kbd:Ctrl+Shift+S]]
    html = html.replace(/\[\[kbd:([^\]]+)\]\]/g, (_, keys) => {
        const parts = keys.split('+').map(k => k.trim()).filter(Boolean);
        return parts.map((key, i) => {
            const kbd = `<kbd class="md-kbd">${escapeHtml(key)}</kbd>`;
            const sep = i < parts.length - 1 ? '<span class="md-kbd-sep">+</span>' : '';
            return kbd + sep;
        }).join('');
    });

    // Поле ввода: [[tif:'value'-t'0'-p'%'-s150-sc300-d0/100-st0,5-r0]]
    // Ручной поиск закрывающих ]] с учётом вложенных [[
    (function() {
        const TAG = '[[tif:';
        let idx = html.indexOf(TAG);
        while (idx !== -1) {
            let depth = 1;
            let i = idx + 2;
            let end = -1;
            while (i < html.length - 1) {
                if (html[i] === '[' && html[i + 1] === '[') { depth++; i++; }
                else if (html[i] === ']' && html[i + 1] === ']') { depth--; i++; if (depth === 0) { end = i + 1; break; } }
                i++;
            }
            if (end === -1) break;

            const inner = html.substring(idx + 6, end - 2);
            const vm = inner.match(/^'([^']*)'/);
            const value = vm ? vm[1] : '';
            const rest = vm ? inner.slice(vm[0].length) : '';

            function extractP(str) {
                const pi = str.indexOf("-p'");
                if (pi === -1) return undefined;
                const start = pi + 3;
                let d = 0;
                for (let j = start; j < str.length; j++) {
                    if (str.substring(j, j + 7) === "[[ico:'") { d++; j += 6; continue; }
                    if (d > 0 && str[j] === ']' && str[j + 1] === ']') { d--; j++; continue; }
                    if (d === 0 && str[j] === "'" && (str[j + 1] === '-' || str[j + 1] === ']')) return str.substring(start, j);
                }
                return str.substring(start);
            }

            function extractParam(str, name) {
                const m = str.match(new RegExp(`-${name}'([^']*)'`));
                return m ? m[1] : undefined;
            }

            const type = extractParam(rest, 't');
            const suffix = extractP(rest);
            const wM = rest.match(/-s(\d+)/);
            const w = wM ? wM[1] : undefined;
            const scWM = rest.match(/-sc(\d*)/);
            const scW = scWM ? scWM[1] : undefined;
            const dM = rest.match(/-d(-?[\d.,]+\/-?[\d.,]+)/);
            const range = dM ? dM[1] : undefined;
            const stM = rest.match(/-st([\d.,]+)/);
            const step = stM ? stM[1] : undefined;
            const rM = rest.match(/-r([01])/);
            const readOnly = rM ? rM[1] : undefined;

            const id = 'tif-' + Math.random().toString(36).substr(2, 6);
            let inputType = 'text';
            let inputMode = '';
            if (type === '0') { inputType = 'number'; inputMode = 'numeric'; }
            else if (type && /[\d.,]+\/[\d.,]+/.test(type)) { inputType = 'number'; inputMode = 'decimal'; }
            else if (type && /^\d+,\d+$/.test(type)) { inputType = 'number'; inputMode = 'decimal'; }
            else if (type && /^\d+\.\d+$/.test(type)) { inputType = 'number'; inputMode = 'decimal'; }

            const typeAttr = inputType === 'number' ? ` type="number" inputmode="${inputMode}"` : ` type="text"`;
            const disabled = readOnly === '0' ? ' disabled' : '';
            const style = w ? ` style="width:${parseInt(w)}px"` : '';

            let suffixContent = '';
            if (suffix) {
                if (suffix.indexOf('[[ico:') !== -1) {
                    suffixContent = renderIcoInline(suffix);
                } else {
                    suffixContent = escapeHtml(suffix);
                }
            }
            const suffixHtml = suffixContent ? `<span class="md-tif-suffix">${suffixContent}</span>` : '';

            let sliderHtml = '';
            if (scW !== undefined) {
                let min = 0, max = 100, stepVal = 1;
                if (range) {
                    const parts = range.split('/');
                    min = parseFloat(parts[0].replace(',', '.'));
                    max = parseFloat(parts[1].replace(',', '.'));
                }
                if (step) stepVal = parseFloat(step.replace(',', '.'));
                const sliderWidth = scW ? ` width:${parseInt(scW)}px` : '';
                sliderHtml = `<input type="range" class="md-tif-slider" id="${id}-slider" min="${min}" max="${max}" step="${stepVal}" value="${escapeHtml(value)}"${sliderWidth ? ` style="${sliderWidth.trim()}"` : ''}${disabled}>`;
            }

            const suffixPos = suffixContent ? suffixHtml : '';
            const replacement = `<span class="md-tif-wrap"><input${typeAttr} class="md-tif" id="${id}" value="${escapeHtml(value)}"${style}${disabled}>${suffixPos}${sliderHtml}</span>`;
            html = html.substring(0, idx) + replacement + html.substring(end);
            idx = html.indexOf(TAG, idx + replacement.length);
        }
    })();

    // Иконка/изображение: [[ico:'path/to/img.png'|WxH]] или [[ico:'path':WxH]]
    // Примеры: [[ico:'plugins/icon.png'|32x32]]  [[ico:'img/logo.svg':64*64]]  [[ico:'img/pic.jpg'|120x80]]

    // Вариант -x / -H: [[ico:'path'-x]] [[ico:'path'-100]] [[ico:'path'-300-c2]]
    html = html.replace(/\[\[ico:'([^']+)'-(x|\d+)(?:-c([1-3]))?\]\]/g, (_, src, size, align) => {
        const alignCls = align ? ` md-ico-wrap-${['','left','center','right'][align]}` : '';
        const wrapOpen = align ? `<span class="md-ico-wrap${alignCls}">` : '';
        const wrapClose = align ? `</span>` : '';
        if (size === 'x') {
            return `${wrapOpen}<img class="md-ico" src="${escapeHtml(src)}" alt="" loading="lazy" style="object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;">${wrapClose}`;
        }
        const h = parseInt(size);
        return `${wrapOpen}<img class="md-ico" src="${escapeHtml(src)}" height="${h}" alt="" loading="lazy" style="height:${h}px;width:auto;object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;">${wrapClose}`;
    });

    // Вариант с размером: [[ico:'path'|WxH]] [[ico:'path':WxH]] [[ico:'path'|300*200-c2]]
    html = html.replace(/\[\[ico:'([^']+)'\[|:](\d+)[x*](\d+)(?:-c([1-3]))?\]\]/g, (_, src, w, h, align) => {
        const alignCls = align ? ` md-ico-wrap-${['','left','center','right'][align]}` : '';
        const wrapOpen = align ? `<span class="md-ico-wrap${alignCls}">` : '';
        const wrapClose = align ? `</span>` : '';
        return `${wrapOpen}<img class="md-ico" src="${escapeHtml(src)}" width="${parseInt(w)}" height="${parseInt(h)}" alt="" loading="lazy" style="width:${parseInt(w)}px;height:${parseInt(h)}px;object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;">${wrapClose}`;
    });

    // Вариант без размеров: [[ico:'path/to/img.png']] [[ico:'path'-c2]]
    html = html.replace(/\[\[ico:'([^']+)'\]\]/g, (_, src) => {
        return `<img class="md-ico" src="${escapeHtml(src)}" width="24" height="24" alt="" loading="lazy" style="width:36px;height:36px;object-fit:contain;vertical-align:middle;display:inline-block;border-radius:0;">`;
    });

    // Фотоальбом кнопка: [[photo: -n'Name' -p'path1','path2']]
    html = html.replace(/\[\[photo:\s*([\s\S]*?)\]\]/g, (_, args) => {
        const nameMatch = args.match(/-n['"]([^'"]*)['"]/);
        const name = nameMatch ? nameMatch[1] : 'Галерея';
        const pMatch = args.match(/-p([\s\S]*?)$/);
        let photos = [];
        if (pMatch) {
            photos = pMatch[1].match(/'([^']*)'/g)?.map(p => p.replace(/^'|'$/g, '')) || [];
        }
        if (photos.length === 0) return '';
        const photosJson = JSON.stringify(photos).replace(/"/g, '&quot;');
        return `<button class="md-photo-btn" data-photos="${photosJson}" onclick="openPhotoModal(this)">${escapeHtml(name)}</button>`;
    });

    // Кнопка модального окна: [[mdb:'label'-n'id'-sW-bN]] (-s без значения = 100% ширины)
    html = html.replace(/\[\[mdb:'([^']+)'-n'([^']+)'(?:-s(\d*))?(?:-b([1-9]))?\]\]/g, (_, label, id, w, btnStyle) => {
        const safeId = escapeHtml(id);
        const style = w !== undefined ? (w ? ` style="width:${parseInt(w)}px"` : ' style="width:100%"') : '';
        const cls = btnStyle ? `md-modal-btn-b${btnStyle}` : 'md-modal-btn';
        return `<button class="${cls}"${style} onclick="openModal('${safeId}')">${escapeHtml(label)}</button>`;
    });

    // Пробелы: [[ "N" ]] — N пробелов
    html = html.replace(/\[\[\s*"(\d+)"\s*\]\]/g, (_, n) => {
        return '&nbsp;'.repeat(parseInt(n));
    });

    // Галочка: [[biil:-c1-r1]]
    html = html.replace(/\[\[biil:-c([01])-r([01])\]\]/g, (_, checked, clickable) => {
        const id = 'chk-' + Math.random().toString(36).substr(2, 6);
        const cAttr = checked === '1' ? ' checked' : '';
        const dAttr = clickable === '0' ? ' disabled' : '';
        return `<label class="md-biil${clickable === '0' ? ' md-biil-static' : ''}"><input type="checkbox" id="${id}"${cAttr}${dAttr}><span class="md-biil-mark"></span></label>`;
    });

    // Выпадающий список: [[ddl:'a','b','c'-s150-p1]] (-s без значения = 100% ширины)
    html = html.replace(/\[\[ddl:((?:'[^']*'(?:,\s*'[^']*')*))(?:-s(\d*))?(?:-p(\d+))?\]\]/g, (_, itemsStr, w, selected) => {
        const options = itemsStr.match(/'([^']*)'/g)?.map(o => o.replace(/^'|'$/g, '')) || [];
        const id = 'ddl-' + Math.random().toString(36).substr(2, 6);
        const style = w !== undefined ? (w ? ` style="width:${parseInt(w)}px"` : ' style="width:100%"') : '';
        const selIdx = selected ? parseInt(selected) - 1 : 0;
        const optsHtml = options.map((o, i) => `<option value="${i}"${i === selIdx ? ' selected' : ''}>${escapeHtml(o)}</option>`).join('');
        return `<select class="md-ddl" id="${id}"${style}>${optsHtml}</select>`;
    });

    // Цвет: [[color: #0A0A0F -s30*90 -c]]
    html = html.replace(/\[\[color:\s*#([0-9a-fA-F]{6})(?:\s+-s(\d+)[*\/,\-](\d+))?\s*(-c)?\]\]/g, (_, hex, w, h, showCode) => {
        const id = 'clr-' + Math.random().toString(36).substr(2, 6);
        const width = w ? parseInt(w) : 30;
        const height = h ? parseInt(h) : 30;
        const hexHtml = showCode ? `<span class="md-color-hex">#${hex}</span>` : '';
        return `<span class="md-color-wrap"><input type="color" class="md-color" id="${id}" value="#${hex}" style="width:${width}px;height:${height}px">${hexHtml}</span>`;
    });

    return html;
}

// Конвертируем таблицы Markdown
function renderMarkdownTables(html) {
    const renderCell = (c) => {
        const v = c.trim();
        return v === '-' ? '' : v;
    };
    return html.replace(/(\|.+\|\n\|[-| :]+\|\n(?:\|.+\|\n?)+)/g, tableBlock => {
        const rows = tableBlock.trim().split('\n');
        const headerCells = rows[0].split('|').filter(c => c.trim());
        const bodyRows = rows.slice(2); // пропускаем строку с ---

        const thead = `<thead><tr>${headerCells.map(c => `<th>${renderCell(c)}</th>`).join('')}</tr></thead>`;
        const tbody = `<tbody>${bodyRows.map(row => {
            const cells = row.split('|').filter(c => c.trim());
            return `<tr>${cells.map(c => `<td>${renderCell(c)}</td>`).join('')}</tr>`;
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
   Интерактивные MD-компоненты (вкладки и т.д.)
======================================== */

function initMdComponents(root = document) {
    initMdTabs(root);
    initPhotoCarousels(root);
    initLevelingSliders(root);
    initTifSliders(root);
    initColorPickers(root);
    initSyntaxHighlight(root);
    // Инициализируем кнопки копирования внутри динамически загруженного контента
    root.querySelectorAll('.copy-btn').forEach(btn => {
        if (!btn.dataset.initialized) {
            btn.dataset.initialized = 'true';
            btn.addEventListener('click', handleCopyClick);
        }
    });
}

function initMdTabs(root) {
    root.querySelectorAll('.md-tabs').forEach(tabsEl => {
        if (tabsEl.dataset.initialized) return;
        tabsEl.dataset.initialized = 'true';

        const buttons = tabsEl.querySelectorAll('.md-tab-btn');
        const panels = tabsEl.querySelectorAll('.md-tab-panel');
        const scrollWrap = tabsEl.querySelector('.md-tabs-scroll-wrap');
        const nav = tabsEl.querySelector('.md-tabs-nav');
        const scrollbar = tabsEl.querySelector('.md-tabs-scrollbar');
        const thumb = tabsEl.querySelector('.md-tabs-scrollbar-thumb');

        function updateScrollbar() {
            if (!nav || !scrollbar || !thumb) return;
            const overflow = nav.scrollWidth > nav.clientWidth;
            scrollWrap.classList.toggle('has-overflow', overflow);
            if (overflow) {
                const ratio = nav.clientWidth / nav.scrollWidth;
                const thumbW = Math.max(30, nav.clientWidth * ratio);
                thumb.style.width = thumbW + 'px';
                const maxScroll = nav.scrollWidth - nav.clientWidth;
                const thumbPos = maxScroll > 0 ? (nav.scrollLeft / maxScroll) * (nav.clientWidth - thumbW) : 0;
                thumb.style.transform = `translateX(${thumbPos}px)`;
            }
        }

        if (nav) {
            nav.addEventListener('scroll', updateScrollbar);

            nav.addEventListener('wheel', e => {
                if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
                    const maxScroll = nav.scrollWidth - nav.clientWidth;
                    if (maxScroll > 0) {
                        e.preventDefault();
                        nav.scrollLeft += e.deltaY;
                    }
                }
            }, { passive: false });
        }

        if (thumb && nav) {
            let dragging = false, startX = 0, startScroll = 0;

            thumb.addEventListener('mousedown', e => {
                dragging = true;
                startX = e.clientX;
                startScroll = nav.scrollLeft;
                e.preventDefault();
            });

            document.addEventListener('mousemove', e => {
                if (!dragging) return;
                const dx = e.clientX - startX;
                const ratio = nav.scrollWidth / nav.clientWidth;
                nav.scrollLeft = startScroll + dx * ratio;
            });

            document.addEventListener('mouseup', () => { dragging = false; });
        }

        updateScrollbar();

        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabId = btn.dataset.tab;

                buttons.forEach(b => {
                    const isActive = b.dataset.tab === tabId;
                    b.classList.toggle('active', isActive);
                    b.setAttribute('aria-selected', isActive);
                });

                panels.forEach(panel => {
                    panel.classList.toggle('active', panel.dataset.tab === tabId);
                });

                updateScrollbar();
            });
        });
    });
}

function initTifSliders(root = document) {
    root.querySelectorAll('.md-tif-wrap').forEach(wrap => {
        if (wrap.dataset.initialized) return;
        const input = wrap.querySelector('.md-tif');
        const slider = wrap.querySelector('.md-tif-slider');
        if (!input || !slider) return;
        wrap.dataset.initialized = 'true';

        const min = parseFloat(slider.min);
        const max = parseFloat(slider.max);
        const step = parseFloat(slider.step) || 1;

        const syncFromSlider = () => { input.value = slider.value; };
        const syncFromInput = () => {
            let v = parseFloat(input.value);
            if (isNaN(v)) return;
            v = Math.round(v / step) * step;
            v = Math.max(min, Math.min(max, v));
            slider.value = v;
        };

        slider.addEventListener('input', syncFromSlider);
        slider.addEventListener('change', syncFromSlider);
        input.addEventListener('input', syncFromInput);
        input.addEventListener('change', syncFromInput);
    });
}

function initColorPickers(root = document) {
    root.querySelectorAll('.md-color-wrap').forEach(wrap => {
        if (wrap.dataset.initialized) return;
        const picker = wrap.querySelector('.md-color');
        const hex = wrap.querySelector('.md-color-hex');
        if (!picker) return;
        wrap.dataset.initialized = 'true';
        if (hex) {
            picker.addEventListener('input', () => { hex.textContent = picker.value; });
        }
    });
}

/* ========================================
   Подсветка синтаксиса Python
   ======================================== */

const PY_KEYWORDS = new Set([
  'False','None','True','and','as','assert','async','await','break','class','continue',
  'def','del','elif','else','except','finally','for','from','global','if','import',
  'in','is','lambda','nonlocal','not','or','pass','raise','return','try','while','with','yield'
]);
const PY_BUILTINS = new Set([
  'print','len','range','str','int','float','list','dict','set','tuple','bool','type',
  'open','input','enumerate','zip','map','filter','sorted','reversed','sum','min','max',
  'abs','round','isinstance','issubclass','hasattr','getattr','setattr','delattr',
  'super','property','staticmethod','classmethod','Exception','ValueError','TypeError',
  'KeyError','IndexError','RuntimeError','StopIteration','FileNotFoundError','OSError',
  'self','c4d','document','op','base','Vector','Matrix','Color','BaseObject','BaseTag',
  'BaseMaterial','BaseShader','GeListNode','NodeData','SplineObject','PolygonObject',
  'AtomArray','AliasTrans','BaseSelect','Description','SubDialog','GeDialog',
  'GeModalDialog','GeUserArea','CommandData','ToolData','SplineData','MaterialData',
  'BitmapLoaderImage','Misc','c4dutils','RegisterPlugin'
]);

function highlightPython(code) {
  let out = '';
  let i = 0;
  const n = code.length;

  function append(cls, text) {
    out += `<span class="${cls}">${escapeHtml(text)}</span>`;
  }

  while (i < n) {
    const rest = code.slice(i);

    if (rest.startsWith('#')) {
      const end = rest.search(/\n/);
      const chunk = end === -1 ? rest : rest.slice(0, end);
      append('hl-cmt', chunk);
      i += chunk.length;
      continue;
    }

    if (rest.startsWith('"""') || rest.startsWith("'''")) {
      const q = rest.slice(0, 3);
      let j = i + 3;
      while (j < n) {
        if (code.slice(j, j + 3) === q) { j += 3; break; }
        j++;
      }
      append('hl-str', code.slice(i, j));
      i = j;
      continue;
    }

    if (rest[0] === '"' || rest[0] === "'") {
      const q = rest[0];
      let j = i + 1;
      while (j < n) {
        if (code[j] === '\\') { j += 2; continue; }
        if (code[j] === q) { j++; break; }
        if (code[j] === '\n') break;
        j++;
      }
      append('hl-str', code.slice(i, j));
      i = j;
      continue;
    }

    const num = rest.match(/^(0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+|\d+\.?\d*(?:[eE][+-]?\d+)?)/);
    if (num) {
      append('hl-num', num[0]);
      i += num[0].length;
      continue;
    }

    const ident = rest.match(/^[A-Za-z_][A-Za-z0-9_]*/);
    if (ident) {
      const w = ident[0];
      if (PY_KEYWORDS.has(w)) append('hl-kw', w);
      else if (PY_BUILTINS.has(w)) append('hl-bi', w);
      else if (/^[A-Z]/.test(w)) append('hl-cls', w);
      else if (i + w.length < n && code[i + w.length] === '(') append('hl-fn', w);
      else out += escapeHtml(w);
      i += w.length;
      continue;
    }

    const deco = rest.match(/^@[A-Za-z_][A-Za-z0-9_.]*/);
    if (deco) {
      append('hl-dec', deco[0]);
      i += deco[0].length;
      continue;
    }

    if (/^[+\-*/%=<>!&|^~]/.test(rest)) {
      const op = rest.match(/^[+\-*/%=<>!&|^~]+/)[0];
      append('hl-op', op);
      i += op.length;
      continue;
    }

    out += escapeHtml(code[i]);
    i++;
  }
  return out;
}

function initSyntaxHighlight(root = document) {
  root.querySelectorAll('.code-num-content-cell code').forEach(el => {
    const code = el.textContent;
    el.innerHTML = highlightPython(code);
  });
  root.querySelectorAll('.code-num-copy').forEach(btn => {
    if (btn.dataset.initialized) return;
    btn.dataset.initialized = 'true';
    btn.addEventListener('click', async () => {
      const raw = btn.closest('.code-num').dataset.code;
      try {
        await navigator.clipboard.writeText(raw);
        btn.textContent = '✓ Скопировано';
        setTimeout(() => { btn.textContent = 'Копировать'; }, 2000);
      } catch { btn.textContent = 'Ошибка'; }
    });
  });
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

// Проверяем, похожа ли строка на путь к изображению (png/svg/jpg/jpeg/webp/gif)
function isImagePath(value) {
    return typeof value === 'string' && /\.(png|svg|jpe?g|webp|gif)(\?.*)?$/i.test(value.trim());
}

// Заполняем иконку: путь к изображению -> <img>, иначе emoji/символ -> текст
function setPluginIcon(id, value, fallback = '⬡') {
    const el = document.getElementById(id);
    if (!el) return;

    if (isImagePath(value)) {
        el.innerHTML = '';
        const img = document.createElement('img');
        img.src = value.trim();
        img.alt = '';
        img.loading = 'lazy';
        img.className = 'plugin-icon-img';
        el.appendChild(img);
    } else {
        el.textContent = value || fallback;
    }
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

/* ========================================
   Фотоальбом: карусель (блоковый)
   ======================================== */

function renderPhotoCarousel(type, title, w, h, content, align, asc, asp) {
    const photos = [];
    const photoRegex = /\[\[p:'([^']+)'\]\]/g;
    let m;
    while ((m = photoRegex.exec(content)) !== null) {
        photos.push(m[1]);
    }
    if (photos.length === 0) return '';

    const id = 'pc-' + Math.random().toString(36).substr(2, 9);
    const width = parseInt(w) || 400;
    const height = parseInt(h) || 300;
    const photosJson = JSON.stringify(photos).replace(/"/g, '&quot;');

    const alignMap = { '2': 'center', '3': 'right' };
    const alignName = alignMap[align] || '';
    const wrapClass = alignName ? ` md-photo-carousel-wrap-${alignName}` : '';

    const ascAttr = asc ? ` data-asc="${parseInt(asc)}"` : '';
    const aspAttr = asp ? ` data-asp="${parseInt(asp)}"` : '';

    let out = `<div class="md-photo-carousel${wrapClass}" id="${id}" data-photos="${photosJson}"${ascAttr}${aspAttr} style="width:${width}px;max-width:100%">`;
    if (title) {
        out += `<div class="md-photo-carousel-title">${escapeHtml(title)}</div>`;
    }
    out += `<div class="md-photo-carousel-viewport" style="height:${height}px">`;
    out += `<div class="md-photo-carousel-track" data-current="0">`;
    photos.forEach((p, i) => {
        out += `<div class="md-photo-carousel-slide${i === 0 ? ' active' : ''}" data-index="${i}"><img src="${escapeHtml(p)}" alt="" loading="lazy"></div>`;
    });
    out += `</div>`;
    if (photos.length > 1) {
        out += `<button class="md-photo-carousel-prev" onclick="slideCarousel('${id}',-1)">&#8249;</button>`;
        out += `<button class="md-photo-carousel-next" onclick="slideCarousel('${id}',1)">&#8250;</button>`;
        out += `<div class="md-photo-carousel-dots">`;
        photos.forEach((_, i) => {
            out += `<button class="md-photo-carousel-dot${i === 0 ? ' active' : ''}" onclick="goToSlide('${id}',${i})"></button>`;
        });
        out += `</div>`;
    }
    out += `<div class="md-photo-carousel-counter">1 / ${photos.length}</div>`;
    out += `</div></div>`;
    return out;
}

/* ========================================
   Фотоальбом: модальное окно (кнопка)
   ======================================== */

function openPhotoModal(btn, startIndex) {
    const photos = JSON.parse(btn.dataset.photos || '[]');
    if (photos.length === 0) return;
    showPhotoModal(photos, startIndex || 0);
}

function openCarouselPhoto(carouselId, photoIndex) {
    const el = document.getElementById(carouselId);
    if (!el) return;
    const photos = JSON.parse(el.dataset.photos || '[]');
    if (photos.length === 0) return;
    showPhotoModal(photos, photoIndex);
}

function showPhotoModal(photos, startIndex) {
    let modal = document.getElementById('md-photo-modal-global');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'md-photo-modal-global';
        modal.className = 'md-photo-modal';
        modal.innerHTML = `
            <div class="md-photo-modal-overlay"></div>
            <div class="md-photo-modal-content">
                <button class="md-photo-modal-close">&times;</button>
                <img class="md-photo-modal-img" src="" alt="">
                <button class="md-photo-modal-prev">&#8249;</button>
                <button class="md-photo-modal-next">&#8250;</button>
                <div class="md-photo-modal-counter"></div>
            </div>
        `;
        document.body.appendChild(modal);
        modal.querySelector('.md-photo-modal-overlay').addEventListener('click', closePhotoModal);
        modal.querySelector('.md-photo-modal-close').addEventListener('click', closePhotoModal);
        modal.querySelector('.md-photo-modal-prev').addEventListener('click', () => slidePhotoModal(-1));
        modal.querySelector('.md-photo-modal-next').addEventListener('click', () => slidePhotoModal(1));

        let touchStartX = 0;
        modal.addEventListener('touchstart', (e) => { touchStartX = e.touches[0].clientX; }, { passive: true });
        modal.addEventListener('touchend', (e) => {
            const diff = touchStartX - e.changedTouches[0].clientX;
            if (Math.abs(diff) > 50) slidePhotoModal(diff > 0 ? 1 : -1);
        }, { passive: true });
    }

    if (modal._keyHandler) {
        document.removeEventListener('keydown', modal._keyHandler);
    }

    modal._photos = photos;
    modal._current = startIndex;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    updatePhotoModal();

    modal._keyHandler = (e) => {
        if (!modal.classList.contains('active')) {
            document.removeEventListener('keydown', modal._keyHandler);
            return;
        }
        if (e.key === 'Escape') closePhotoModal();
        if (e.key === 'ArrowLeft') slidePhotoModal(-1);
        if (e.key === 'ArrowRight') slidePhotoModal(1);
    };
    document.addEventListener('keydown', modal._keyHandler);
}

function closePhotoModal() {
    const modal = document.getElementById('md-photo-modal-global');
    if (!modal) return;
    modal.classList.remove('active');
    document.body.style.overflow = '';
    if (modal._keyHandler) {
        document.removeEventListener('keydown', modal._keyHandler);
    }
}

function slidePhotoModal(dir) {
    const modal = document.getElementById('md-photo-modal-global');
    if (!modal || !modal._photos) return;
    modal._current = (modal._current + dir + modal._photos.length) % modal._photos.length;
    updatePhotoModal();
}

function updatePhotoModal() {
    const modal = document.getElementById('md-photo-modal-global');
    if (!modal || !modal._photos) return;
    modal.querySelector('.md-photo-modal-img').src = modal._photos[modal._current];
    modal.querySelector('.md-photo-modal-counter').textContent = `${modal._current + 1} / ${modal._photos.length}`;
}

/* ========================================
    Модальные окна (modal blocks)
    ======================================== */

function openModal(id) {
    const data = modalBlocks[id];
    if (!data) return;

    let overlay = document.getElementById('md-modal-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'md-modal-overlay';
        overlay.className = 'md-modal';
        overlay.innerHTML = `
            <div class="md-modal-backdrop"></div>
            <div class="md-modal-dialog">
                <div class="md-modal-titlebar">
                    <div class="md-modal-titlebar-left"></div>
                    <div class="md-modal-titlebar-right">
                        <div class="md-modal-help" style="display:none">
                            <span class="md-modal-help-icon">?</span>
                            <div class="md-modal-help-tooltip"></div>
                        </div>
                        <button class="md-modal-close">&times;</button>
                    </div>
                </div>
                <div class="md-modal-body"></div>
            </div>
        `;
        document.body.appendChild(overlay);
        overlay.querySelector('.md-modal-backdrop').addEventListener('click', closeModal);
        overlay.querySelector('.md-modal-close').addEventListener('click', closeModal);
    }

    if (overlay._keyHandler) {
        document.removeEventListener('keydown', overlay._keyHandler);
    }

    const dialog = overlay.querySelector('.md-modal-dialog');
    dialog.style.width = data.w + 'px';
    dialog.style.maxWidth = '90vw';
    dialog.style.maxHeight = '85vh';

    const raw = data.raw;

    let icon = '', title = '', tagline = '', body = raw;
    const lines = raw.split('\n');
    let bodyStart = 0;
    let lastHeaderIdx = -1;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.trim() === '') continue;
        const iconMatch = line.match(/^icon:\s*(.+)/);
        const titleMatch = line.match(/^title:\s*(.+)/);
        const taglineMatch = line.match(/^tagline:\s*(.+)/);
        if (iconMatch) { icon = iconMatch[1].trim(); lastHeaderIdx = i; }
        else if (titleMatch) { title = titleMatch[1].trim(); lastHeaderIdx = i; }
        else if (taglineMatch) { tagline = taglineMatch[1].trim(); lastHeaderIdx = i; }
        else { bodyStart = i; break; }
    }
    if (lastHeaderIdx >= 0 && bodyStart <= lastHeaderIdx) bodyStart = lastHeaderIdx + 1;

    body = lines.slice(bodyStart).join('\n').trim();

    const titlebarLeft = overlay.querySelector('.md-modal-titlebar-left');
    let iconHtml = '';
    if (icon) {
        if (isImagePath(icon)) {
            iconHtml = `<img class="md-modal-icon" src="${escapeHtml(icon)}" alt="" width="32" height="32">`;
        } else {
            iconHtml = `<span class="md-modal-icon-text">${escapeHtml(icon)}</span>`;
        }
    }
    titlebarLeft.innerHTML = `${iconHtml}${title ? `<span class="md-modal-title">${escapeHtml(title)}</span>` : ''}`;

    const helpEl = overlay.querySelector('.md-modal-help');
    const tooltipEl = overlay.querySelector('.md-modal-help-tooltip');
    if (tagline) {
        helpEl.style.display = '';
        tooltipEl.textContent = tagline;
    } else {
        helpEl.style.display = 'none';
    }

    const bodyEl = overlay.querySelector('.md-modal-body');
    bodyEl.innerHTML = body ? renderMarkdown(body) : '';
    initMdComponents(bodyEl);

    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';

    overlay._keyHandler = (e) => {
        if (!overlay.classList.contains('active')) {
            document.removeEventListener('keydown', overlay._keyHandler);
            return;
        }
        if (e.key === 'Escape') closeModal();
    };
    document.addEventListener('keydown', overlay._keyHandler);
}

function closeModal() {
    const overlay = document.getElementById('md-modal-overlay');
    if (!overlay) return;
    overlay.classList.remove('active');
    document.body.style.overflow = '';
    if (overlay._keyHandler) {
        document.removeEventListener('keydown', overlay._keyHandler);
    }
}

/* ========================================
   Фотокарусель: навигация (3D)
   ======================================== */

function applyCarousel3D(id, index, instant) {
    const el = document.getElementById(id);
    if (!el) return;
    const track = el.querySelector('.md-photo-carousel-track');
    const slides = Array.from(track.children);
    const dots = el.querySelectorAll('.md-photo-carousel-dot');
    const counter = el.querySelector('.md-photo-carousel-counter');
    track.dataset.current = index;
    const total = slides.length;
    const asp = parseInt(el.dataset.asp) || 500;

    slides.forEach((slide, i) => {
        let offset = i - index;
        if (offset > total / 2) offset -= total;
        if (offset < -total / 2) offset += total;
        const absOffset = Math.abs(offset);

        slide.style.transition = instant ? 'none' : `transform ${asp}ms ease, opacity ${asp}ms ease, filter ${asp}ms ease`;

        if (offset === 0) {
            slide.style.transform = 'translateZ(0) rotateY(0deg) scale(1)';
            slide.style.opacity = '1';
            slide.style.zIndex = '5';
            slide.style.filter = 'none';
        } else if (absOffset === 1) {
            const sign = offset > 0 ? 1 : -1;
            slide.style.transform = `translateX(${sign * 62}%) translateZ(-180px) rotateY(${sign * -45}deg) scale(0.65)`;
            slide.style.opacity = '0.7';
            slide.style.zIndex = '4';
            slide.style.filter = 'brightness(0.75)';
        } else if (absOffset === 2) {
            const sign = offset > 0 ? 1 : -1;
            slide.style.transform = `translateX(${sign * 90}%) translateZ(-350px) rotateY(${sign * -60}deg) scale(0.4)`;
            slide.style.opacity = '0.3';
            slide.style.zIndex = '3';
            slide.style.filter = 'brightness(0.5)';
        } else {
            slide.style.transform = `translateZ(-500px) scale(0)`;
            slide.style.opacity = '0';
            slide.style.zIndex = '0';
            slide.style.filter = 'none';
        }
        slide.classList.toggle('active', i === index);
    });

    dots.forEach((d, i) => d.classList.toggle('active', i === index));
    if (counter) counter.textContent = `${index + 1} / ${total}`;
}

function slideCarousel(id, dir, instant) {
    const el = document.getElementById(id);
    if (!el) return;
    const track = el.querySelector('.md-photo-carousel-track');
    const slides = track.children;
    let current = parseInt(track.dataset.current || '0');
    current = (current + dir + slides.length) % slides.length;
    applyCarousel3D(id, current, instant);
}

function startAutoScroll(carousel) {
    const id = carousel.id;
    const asp = parseInt(carousel.dataset.asp) || 500;
    const asc = parseInt(carousel.dataset.asc) || 0;

    if (asc > 0) {
        const interval = asc + asp;
        carousel._ascTimer = setInterval(() => slideCarousel(id, 1), interval);
        carousel.addEventListener('mouseenter', () => clearInterval(carousel._ascTimer));
        carousel.addEventListener('mouseleave', () => {
            carousel._ascTimer = setInterval(() => slideCarousel(id, 1), interval);
        });
    } else {
        const autoNext = () => {
            slideCarousel(id, 1);
            const track = carousel.querySelector('.md-photo-carousel-track');
            const active = track ? track.querySelector('.active') : null;
            if (active) {
                const handler = (e) => {
                    if (e.propertyName !== 'transform') return;
                    active.removeEventListener('transitionend', handler);
                    carousel._autoTimeout = setTimeout(autoNext, 30);
                };
                active.addEventListener('transitionend', handler);
            } else {
                carousel._autoTimeout = setTimeout(autoNext, asp);
            }
        };
        carousel._autoTimeout = setTimeout(autoNext, asp);
        carousel.addEventListener('mouseenter', () => clearTimeout(carousel._autoTimeout));
        carousel.addEventListener('mouseleave', () => {
            carousel._autoTimeout = setTimeout(autoNext, 30);
        });
    }
}

function goToSlide(id, index) {
    applyCarousel3D(id, index);
}

function initPhotoCarousels(root = document) {
    root.querySelectorAll('.md-photo-carousel').forEach(carousel => {
        if (carousel.dataset.initialized) return;
        carousel.dataset.initialized = 'true';

        const id = carousel.id;
        const slides = carousel.querySelectorAll('.md-photo-carousel-slide');

        slides.forEach(slide => {
            slide.addEventListener('click', () => {
                const idx = parseInt(slide.dataset.index || '0');
                openCarouselPhoto(id, idx);
            });
        });

        const viewport = carousel.querySelector('.md-photo-carousel-viewport');
        if (!viewport) return;

        let startX = 0;
        viewport.addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; }, { passive: true });
        viewport.addEventListener('touchend', (e) => {
            const diff = startX - e.changedTouches[0].clientX;
            if (Math.abs(diff) > 50) slideCarousel(id, diff > 0 ? 1 : -1);
        }, { passive: true });

        applyCarousel3D(id, 0);

        const asp = parseInt(carousel.dataset.asp) || 0;
        if (asp > 0 && slides.length > 1) {
            startAutoScroll(carousel);
        }
    });
}

/* ========================================
   Сравнение фото (leveling)
   ======================================== */

function renderLeveling(title, w, h, content, align, asc, asp) {
    const photos = [];
    const photoRegex = /\[\[lv:'([^']+)'\]\]\s*(?:-d\[([^\]]*)\])?/g;
    let m;
    while ((m = photoRegex.exec(content)) !== null) {
        photos.push({ src: m[1], desc: m[2] || '' });
    }
    if (photos.length < 2 || photos.length > 3) return '';

    const id = 'lv-' + Math.random().toString(36).substr(2, 9);
    const count = photos.length;
    const dividerPositions = [];

    if (count === 2) {
        dividerPositions.push(50);
    } else {
        dividerPositions.push(33.33);
        dividerPositions.push(66.67);
    }

    const alignMap = { '2': 'center', '3': 'right' };
    const alignName = alignMap[align] || '';
    const wrapClass = alignName ? ` md-leveling-wrap-${alignName}` : '';

    const ascAttr = asc ? ` data-asc="${parseInt(asc)}"` : '';
    const aspAttr = asp ? ` data-asp="${parseInt(asp)}"` : '';

    let out = `<div class="md-leveling${wrapClass}" id="${id}" data-count="${count}"${ascAttr}${aspAttr} style="width:${w}px;max-width:100%">`;
    out += `<div class="md-leveling-title">${escapeHtml(title)}</div>`;
    out += `<div class="md-leveling-viewport" style="height:${h}px" data-count="${count}">`;

    photos.forEach((photo, i) => {
        let clipStyle = '';
        if (count === 2) {
            if (i === 0) clipStyle = `clip-path:inset(0 ${100 - dividerPositions[0]}% 0 0)`;
            else clipStyle = `clip-path:inset(0 0 0 ${dividerPositions[0]}%)`;
        } else {
            if (i === 0) clipStyle = `clip-path:inset(0 ${100 - dividerPositions[0]}% 0 0)`;
            else if (i === 1) clipStyle = `clip-path:inset(0 ${100 - dividerPositions[1]}% 0 ${dividerPositions[0]}%)`;
            else clipStyle = `clip-path:inset(0 0 0 ${dividerPositions[1]}%)`;
        }

        let capLeft = '';
        if (count === 2) {
            if (i === 0) capLeft = 'left:12px';
            else capLeft = 'right:12px;left:auto';
        } else {
            if (i === 0) capLeft = 'left:12px';
            else if (i === 1) capLeft = 'left:50%;transform:translateX(-50%)';
            else capLeft = 'right:12px;left:auto';
        }

        out += `<div class="md-leveling-img" data-index="${i}" style="${clipStyle}">`;
        out += `<img src="${escapeHtml(photo.src)}" alt="" loading="lazy" draggable="false">`;
        if (photo.desc) {
            out += `<div class="md-leveling-caption" style="${capLeft}">${escapeHtml(photo.desc)}</div>`;
        }
        out += `</div>`;
    });

    dividerPositions.forEach((pos, i) => {
        out += `<div class="md-leveling-divider" data-index="${i}" style="left:${pos}%">`;
        out += `<div class="md-leveling-handle"></div>`;
        out += `</div>`;
    });

    out += `</div></div>`;
    return out;
}

/* ========================================
   Колонки: <column>...</column>
   ======================================== */

function renderColumns(inner, blockParams) {
    const cols = [];
    const colRegex = /<col([^>]*)>([\s\S]*?)<\/col>/g;
    let m;
    while ((m = colRegex.exec(inner)) !== null) {
        const params = m[1] || '';
        const content = m[2].trim();

        const nMatch = params.match(/-n'([^']*)'/);
        const lMatch = params.match(/-l(\d+)/);
        const cMatch = params.match(/-c([1-3])(?!t)/);
        const ctMatch = params.match(/-ct([1-3])/);

        cols.push({
            title: nMatch ? nMatch[1] : '',
            width: lMatch ? parseInt(lMatch[1]) : 0,
            align: cMatch ? parseInt(cMatch[1]) : 1,
            titleAlign: ctMatch ? parseInt(ctMatch[1]) : 1,
            content: content
        });
    }

    if (cols.length === 0) return '';

    const totalMatch = (blockParams || '').match(/-l(\d+)/);
    const totalWidth = totalMatch ? parseInt(totalMatch[1]) : 0;

    const alignMap = { 1: 'left', 2: 'center', 3: 'right' };
    const wrapStyle = totalWidth ? `width:${totalWidth}px;max-width:100%;` : '';
    let out = `<div class="md-columns"${wrapStyle ? ` style="${wrapStyle}"` : ''}>`;
    cols.forEach(col => {
        const widthStyle = col.width ? `width:${col.width}px;flex:none;` : 'flex:1;min-width:0;';
        const titleHtml = col.title
            ? `<div class="md-column-header" style="text-align:${alignMap[col.titleAlign]}">${escapeHtml(col.title)}</div>`
            : '';
        const contentHtml = renderInlineContent(col.content);
        out += `<div class="md-column" style="${widthStyle}text-align:${alignMap[col.align]}">${titleHtml}<div class="md-column-content">${contentHtml}</div></div>`;
    });
    out += '</div>';
    return out;
}

function initLevelingSliders(root = document) {
    root.querySelectorAll('.md-leveling').forEach(el => {
        if (el.dataset.initialized) return;
        el.dataset.initialized = 'true';

        const viewport = el.querySelector('.md-leveling-viewport');
        const count = parseInt(viewport.dataset.count) || 2;
        const dividers = Array.from(el.querySelectorAll('.md-leveling-divider'));
        const imgs = Array.from(el.querySelectorAll('.md-leveling-img'));

        const getPositions = () => dividers.map(d => parseFloat(d.style.left));
        const setPositions = (positions) => {
            const n = dividers.length;
            for (let i = 0; i < n; i++) {
                const pos = positions[i];
                dividers[i].style.left = pos + '%';
            }

            if (count === 2) {
                const p0 = positions[0];
                imgs[0].style.clipPath = `inset(0 ${100 - p0}% 0 0)`;
                imgs[1].style.clipPath = `inset(0 0 0 ${p0}%)`;
            } else {
                const p0 = positions[0];
                const p1 = positions[1];
                imgs[0].style.clipPath = `inset(0 ${100 - p0}% 0 0)`;
                imgs[1].style.clipPath = `inset(0 ${100 - p1}% 0 ${p0}%)`;
                imgs[2].style.clipPath = `inset(0 0 0 ${p1}%)`;
            }
        };

        dividers.forEach((divider, i) => {
            const onMove = (clientX) => {
                const rect = viewport.getBoundingClientRect();
                let pos = ((clientX - rect.left) / rect.width) * 100;
                pos = Math.max(5, Math.min(95, pos));

                const positions = getPositions();
                const minGap = 5;

                if (i > 0) {
                    pos = Math.max(positions[i - 1] + minGap, pos);
                }
                if (i < positions.length - 1) {
                    pos = Math.min(positions[i + 1] - minGap, pos);
                }

                positions[i] = pos;
                setPositions(positions);
            };

            divider.addEventListener('mousedown', (e) => {
                e.preventDefault();
                viewport.classList.add('dragging');

                const mousemove = (e) => onMove(e.clientX);
                const mouseup = () => {
                    viewport.classList.remove('dragging');
                    document.removeEventListener('mousemove', mousemove);
                    document.removeEventListener('mouseup', mouseup);
                };

                document.addEventListener('mousemove', mousemove);
                document.addEventListener('mouseup', mouseup);
            });

            divider.addEventListener('touchstart', (e) => {
                e.preventDefault();
                viewport.classList.add('dragging');

                const touchmove = (e) => onMove(e.touches[0].clientX);
                const touchend = () => {
                    viewport.classList.remove('dragging');
                    document.removeEventListener('touchmove', touchmove);
                    document.removeEventListener('touchend', touchend);
                };

                document.addEventListener('touchmove', touchmove);
                document.addEventListener('touchend', touchend);
            }, { passive: false });
        });

        const asc = parseInt(el.dataset.asc) || 0;
        const asp = parseInt(el.dataset.asp) || 0;
        if (asp > 0) {
            let autoIdx = 0;

            const animate = (from, to, duration, cb) => {
                const start = performance.now();
                const tick = (now) => {
                    const t = Math.min((now - start) / duration, 1);
                    const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
                    const pos = from + (to - from) * ease;
                    cb(pos);
                    if (t < 1) requestAnimationFrame(tick);
                };
                requestAnimationFrame(tick);
            };

            const autoStep = () => {
                if (count === 2) {
                    const target = autoIdx % 2 === 0 ? 5 : 95;
                    animate(getPositions()[0], target, asp, (p) => setPositions([p]));
                    autoIdx++;
                } else {
                    const positions = autoIdx % 3 === 0
                        ? [80, 95]
                        : autoIdx % 3 === 1
                        ? [5, 95]
                        : [5, 20];
                    const from = getPositions();
                    animate(0, 1, asp, (t) => {
                        setPositions([
                            from[0] + (positions[0] - from[0]) * t,
                            from[1] + (positions[1] - from[1]) * t
                        ]);
                    });
                    autoIdx++;
                }
            };

            const interval = asc > 0 ? asc + asp : asp;

            el._ascTimer = setInterval(autoStep, interval);
            el.addEventListener('mouseenter', () => clearInterval(el._ascTimer));
            el.addEventListener('mouseleave', () => {
                el._ascTimer = setInterval(autoStep, interval);
            });
        }
    });
}