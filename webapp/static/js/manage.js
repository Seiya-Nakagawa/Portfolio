// スキル実績管理（登録画面）。単一ページ上でタブを切り替え、サーバーの JSON API と通信する。
document.addEventListener('DOMContentLoaded', () => {
    const urls = {
        bootstrap: document.body.dataset.apiBootstrap,
        projects: document.body.dataset.apiProjects,
        skills: document.body.dataset.apiSkills,
        certifications: document.body.dataset.apiCertifications,
        works: document.body.dataset.apiWorks,
        site: document.body.dataset.apiSite,
        export: document.body.dataset.apiExport,
        exportDownload: document.body.dataset.exportDownload,
    };
    const messageEl = document.getElementById('message');

    // --- 共通処理 ---

    function esc(value) {
        return String(value ?? '').replace(/[&<>"']/g, (c) => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
        ));
    }

    function getCookie(name) {
        const match = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`));
        return match ? decodeURIComponent(match.split('=')[1]) : '';
    }

    function showMessage(text, kind = 'ok') {
        messageEl.textContent = text;
        messageEl.className = kind === 'ok' ? 'message' : `message ${kind}`;
        messageEl.hidden = !text;
    }

    async function api(method, url, body) {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        };
        if (body !== undefined) options.body = JSON.stringify(body);
        const response = await fetch(url, options);
        if (response.status === 401) {
            window.location.reload();
            throw new Error('ログインが必要です。');
        }
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error((data.errors || ['エラーが発生しました。']).join('\n'));
        }
        return data;
    }

    // 失敗時はメッセージを表示して例外を握りつぶす（呼び出し側は undefined を受け取る）。
    async function guarded(task) {
        try {
            showMessage('');
            return await task();
        } catch (error) {
            showMessage(error.message, 'error');
            return undefined;
        }
    }

    // --- 案件登録 ---

    const PAGE_INFO = 'info';
    const SUB_OTHER = 'その他';

    const project = {
        state: null, // { project_id, name, start_year_month, end_year_month, selected: {skill_id: version} }
        skills: [],
        ongoing: [],
        finished: [],
        pageIndex: 0,
        confirming: false, // true の間は入力ページとは別の確認画面を表示する
        finishedOpen: false,
        subTabs: {}, // カテゴリごとに選択中のサブカテゴリ { category: subcategory }
    };

    function emptyProject() {
        return { project_id: '', name: '', start_year_month: '', end_year_month: '', selected: {} };
    }

    function fromServer(data) {
        if (!data) return emptyProject();
        const selected = {};
        data.skills.forEach((s) => { selected[s.skill_id] = s.version; });
        return { ...data, selected };
    }

    // カテゴリページの順序は、各カテゴリの sort_order 最小値の昇順（サーバーの並び順に従う）。
    function categories() {
        return [...new Set(project.skills.map((s) => s.category))];
    }

    // サブカテゴリの候補（種類フィルタと同様、既存の値から選べるようにする）。
    function subcategories() {
        return [...new Set(project.skills.map((s) => s.subcategory).filter((v) => v !== ''))];
    }

    // カテゴリ内のサブカテゴリを sort_order 最小値の昇順で返す。未設定の項目は末尾の「その他」にまとめる。
    function subcategoriesOf(items) {
        const named = [...new Set(items.map((s) => s.subcategory).filter((v) => v !== ''))];
        if (named.length === 0) return [];
        return items.some((s) => s.subcategory === '') ? [...named, SUB_OTHER] : named;
    }

    function pages() {
        return [PAGE_INFO, ...categories()];
    }

    function pageLabel(page) {
        if (page === PAGE_INFO) return '案件情報';
        return page;
    }

    function infoIsValid() {
        return project.state.name.trim() !== '' && project.state.start_year_month !== '';
    }

    // スキル項目・継続中案件を取得する。失敗時は null を返し、メッセージは表示しない。
    async function refreshMaster() {
        try {
            const data = await api('GET', urls.bootstrap);
            project.skills = data.skills;
            project.ongoing = data.ongoing_projects;
            project.finished = data.finished_projects;
            return data;
        } catch (error) {
            return null;
        }
    }

    async function loadProjectTab(reloadInitial) {
        showMessage('');
        const data = await refreshMaster();
        if (!data) {
            showMessage('初期表示データの取得に失敗しました。', 'error');
            return;
        }
        if (reloadInitial) {
            project.state = fromServer(data.initial_project);
            project.pageIndex = 0;
        }
        renderProject();
    }

    // 入力内容の確認画面。入力ページのタブ・案件選択は表示せず、登録か入力への戻りのみを選べる。
    function renderConfirm() {
        const root = document.getElementById('tab-project');
        const s = project.state;
        const chosen = project.skills.filter((sk) => sk.skill_id in s.selected);
        root.innerHTML = `
            <h2>入力内容の確認</h2>
            <table>
                <tr><th>案件名</th><td>${esc(s.name)}</td></tr>
                <tr><th>開始年月</th><td>${esc(s.start_year_month)}</td></tr>
                <tr><th>終了年月</th><td>${s.end_year_month ? esc(s.end_year_month) : '継続中'}</td></tr>
            </table>
            <h2>選択したスキル項目（${chosen.length}件）</h2>
            <div class="table-wrap"><table>
                <tr><th>種類</th><th>項目</th><th>バージョン</th></tr>
                ${chosen.map((sk) => `<tr><td>${esc(sk.category)}</td><td>${esc(sk.name)}</td><td>${esc(s.selected[sk.skill_id])}</td></tr>`).join('')}
            </table></div>
            <div class="actions">
                <button type="button" id="back-to-input">入力に戻る</button>
                <span class="spacer"></span>
                <button type="button" class="primary" id="save-project">登録</button>
            </div>`;
        root.querySelector('#back-to-input').addEventListener('click', () => {
            project.confirming = false;
            showMessage('');
            renderProject();
        });
        root.querySelector('#save-project').addEventListener('click', saveProject);
    }

    function goToConfirm() {
        showMessage('');
        if (!infoIsValid()) {
            project.pageIndex = 0;
            renderProject();
            showMessage('案件名と開始年月を入力してください。', 'error');
            return;
        }
        project.confirming = true;
        renderProject();
    }

    function renderProject() {
        if (project.confirming) {
            renderConfirm();
            return;
        }
        const root = document.getElementById('tab-project');
        const list = pages();
        const current = list[project.pageIndex];
        const isLastPage = project.pageIndex === list.length - 1;
        const hasId = project.state.project_id !== '';
        const options = ['<option value="">（選択してください）</option>']
            .concat(project.ongoing.map((p) => (
                `<option value="${esc(p.project_id)}"${p.project_id === project.state.project_id ? ' selected' : ''}>${esc(p.name)}</option>`
            ))).join('');

        const finishedOptions = ['<option value="">（選択してください）</option>']
            .concat(project.finished.map((p) => (
                `<option value="${esc(p.project_id)}"${p.project_id === project.state.project_id ? ' selected' : ''}>${esc(p.name)}（${esc(p.start_year_month)}〜${esc(p.end_year_month)}）</option>`
            ))).join('');

        root.innerHTML = `
            <div class="row">
                <label>継続中の案件
                    <select id="ongoing-select">${options}</select>
                </label>
                <button type="button" id="new-project">新規作成</button>
            </div>
            <details class="finished-projects"${project.finishedOpen ? ' open' : ''}>
                <summary>終了済みの案件を訂正する</summary>
                <div class="row">
                    <label>終了済みの案件
                        <select id="finished-select">${finishedOptions}</select>
                    </label>
                </div>
            </details>
            <div class="page-tabs" role="tablist">
                ${list.map((p, i) => `<button type="button" role="tab" data-page="${i}" aria-selected="${i === project.pageIndex}">${esc(pageLabel(p))}</button>`).join('')}
            </div>
            <div id="project-page"></div>
            <div class="actions">
                <button type="button" id="prev-page"${project.pageIndex === 0 ? ' disabled' : ''}>戻る</button>
                ${isLastPage
        ? '<button type="button" class="primary" id="next-page">確認へ</button>'
        : '<button type="button" id="next-page">次へ</button><button type="button" class="primary" id="confirm-page">確認へ</button>'}
                <span class="spacer"></span>
                ${hasId ? '<button type="button" class="danger" id="delete-project">削除</button>' : ''}
            </div>`;

        renderProjectPage(current);

        // 継続中・終了済みのどちらのプルダウンも、選んだ案件を登録フォームへ読み込む。
        [['#ongoing-select', false], ['#finished-select', true]].forEach(([selector, isFinished]) => {
            root.querySelector(selector).addEventListener('change', async (e) => {
                if (!e.target.value) return;
                const data = await guarded(() => api('GET', `${urls.projects}/${encodeURIComponent(e.target.value)}`));
                if (data) {
                    project.state = fromServer(data);
                    project.pageIndex = 0;
                    project.finishedOpen = isFinished;
                    renderProject();
                }
            });
        });
        root.querySelector('.finished-projects').addEventListener('toggle', (e) => {
            project.finishedOpen = e.target.open;
        });
        root.querySelector('#new-project').addEventListener('click', () => {
            project.state = emptyProject();
            project.pageIndex = 0;
            showMessage('');
            renderProject();
        });
        root.querySelectorAll('.page-tabs button').forEach((button) => {
            button.addEventListener('click', () => {
                project.pageIndex = Number(button.dataset.page);
                renderProject();
            });
        });
        root.querySelector('#prev-page').addEventListener('click', () => {
            project.pageIndex = Math.max(0, project.pageIndex - 1);
            renderProject();
        });
        root.querySelector('#next-page').addEventListener('click', () => {
            // 案件情報ページの必須項目を満たさない場合は先へ進めない。
            if (current === PAGE_INFO && !infoIsValid()) {
                showMessage('案件名と開始年月を入力してください。', 'error');
                return;
            }
            showMessage('');
            if (isLastPage) {
                goToConfirm();
                return;
            }
            project.pageIndex += 1;
            renderProject();
        });
        // 最後以外のページからも、案件情報を検証したうえで確認画面へ遷移する。
        const confirmButton = root.querySelector('#confirm-page');
        if (confirmButton) confirmButton.addEventListener('click', goToConfirm);
        const deleteButton = root.querySelector('#delete-project');
        if (deleteButton) deleteButton.addEventListener('click', deleteProject);
    }

    function renderProjectPage(page) {
        const body = document.getElementById('project-page');
        const s = project.state;

        if (page === PAGE_INFO) {
            body.innerHTML = `
                <label>案件名<input type="text" id="p-name" value="${esc(s.name)}" maxlength="255" /></label>
                <div class="row">
                    <label>開始年月<input type="month" id="p-start" value="${esc(s.start_year_month)}" /></label>
                    <label>終了年月<input type="month" id="p-end" value="${esc(s.end_year_month)}" /></label>
                </div>
                <p><label><input type="checkbox" id="p-ongoing"${s.end_year_month === '' ? ' checked' : ''} />継続中（終了年月を空欄のままにする）</label></p>`;
            const endInput = body.querySelector('#p-end');
            const ongoingCheck = body.querySelector('#p-ongoing');
            endInput.disabled = ongoingCheck.checked;
            body.querySelector('#p-name').addEventListener('input', (e) => { s.name = e.target.value; });
            body.querySelector('#p-start').addEventListener('input', (e) => { s.start_year_month = e.target.value; });
            endInput.addEventListener('input', (e) => { s.end_year_month = e.target.value; });
            ongoingCheck.addEventListener('change', (e) => {
                endInput.disabled = e.target.checked;
                if (e.target.checked) {
                    s.end_year_month = '';
                    endInput.value = '';
                }
            });
            return;
        }

        const categoryItems = project.skills.filter((sk) => sk.category === page);
        const subs = subcategoriesOf(categoryItems);
        let items = categoryItems;
        let subTabsHtml = '';
        if (subs.length > 0) {
            const activeSub = subs.includes(project.subTabs[page]) ? project.subTabs[page] : subs[0];
            project.subTabs[page] = activeSub;
            items = categoryItems.filter((sk) => (sk.subcategory || SUB_OTHER) === activeSub);
            subTabsHtml = `<div class="sub-tabs" role="tablist">${subs.map((sub, i) => `<button type="button" role="tab" data-sub="${i}" aria-selected="${sub === activeSub}">${esc(sub)}</button>`).join('')}</div>`;
        }
        body.innerHTML = subTabsHtml + items.map((sk) => {
            const checked = sk.skill_id in s.selected;
            return `
                <div class="skill-check">
                    <label><input type="checkbox" data-skill="${esc(sk.skill_id)}"${checked ? ' checked' : ''} />${esc(sk.name)}</label>
                    <input type="text" data-version="${esc(sk.skill_id)}" placeholder="バージョン（任意）" maxlength="64" value="${esc(s.selected[sk.skill_id] ?? '')}"${checked ? '' : ' hidden'} />
                </div>`;
        }).join('');
        body.querySelectorAll('.sub-tabs button').forEach((button) => {
            button.addEventListener('click', () => {
                project.subTabs[page] = subs[Number(button.dataset.sub)];
                renderProjectPage(page);
            });
        });
        body.querySelectorAll('input[data-skill]').forEach((check) => {
            const versionInput = body.querySelector(`input[data-version="${CSS.escape(check.dataset.skill)}"]`);
            check.addEventListener('change', () => {
                if (check.checked) {
                    s.selected[check.dataset.skill] = versionInput.value;
                } else {
                    delete s.selected[check.dataset.skill];
                }
                versionInput.hidden = !check.checked;
            });
            versionInput.addEventListener('input', () => {
                if (check.checked) s.selected[check.dataset.skill] = versionInput.value;
            });
        });
    }

    async function saveProject() {
        const s = project.state;
        // 保存時は必ず案件情報の必須項目を確認し、未入力なら案件情報ページへ戻す。
        if (!infoIsValid()) {
            project.confirming = false;
            project.pageIndex = 0;
            renderProject();
            showMessage('案件名と開始年月を入力してください。', 'error');
            return;
        }
        const saved = await guarded(() => api('POST', urls.projects, {
            project_id: s.project_id || undefined,
            name: s.name,
            start_year_month: s.start_year_month,
            end_year_month: s.end_year_month,
            skills: Object.entries(s.selected).map(([skill_id, version]) => ({ skill_id, version })),
        }));
        if (!saved) return;
        project.state = fromServer(saved);
        project.confirming = false;
        project.pageIndex = 0;
        await loadProjectTab(false);
        showMessage('保存しました。');
    }

    async function deleteProject() {
        const message = '案件を削除します。紐づくスキル使用実績も同時に削除され、経験年数に影響します。よろしいですか？';
        if (!window.confirm(message)) return;
        const result = await guarded(() => api('DELETE', `${urls.projects}/${encodeURIComponent(project.state.project_id)}`));
        if (!result) return;
        await loadProjectTab(true);
        showMessage('削除しました。');
    }

    // --- 一覧・追加・変更・削除の共通画面（スキル項目・資格・実績） ---

    function crudPanel(root, config) {
        let rows = [];
        let editing = null; // 編集中の行。追加時は null
        let inEditScreen = false; // separateEdit 指定時に、一覧ではなく編集画面を表示中か
        let filterValue = ''; // filter 指定時に、絞り込み中の値（空は絞り込みなし）

        function fieldValue(row, field) {
            const value = row ? row[field.name] : '';
            return Array.isArray(value) ? value.join(', ') : (value ?? '');
        }

        function renderField(field, row) {
            const value = esc(fieldValue(row, field));
            const readonly = row && field.readonlyOnEdit ? ' disabled' : '';
            if (field.type === 'select') {
                const options = field.options().map((o) => `<option value="${esc(o.value)}"${String(o.value) === String(fieldValue(row, field)) ? ' selected' : ''}>${esc(o.label)}</option>`).join('');
                return `<label>${esc(field.label)}<select name="${field.name}">${options}</select></label>`;
            }
            if (field.type === 'textarea') {
                return `<label>${esc(field.label)}<textarea name="${field.name}" rows="3">${value}</textarea></label>`;
            }
            const list = field.datalist ? ` list="${config.key}-${field.name}-list"` : '';
            const dl = field.datalist
                ? `<datalist id="${config.key}-${field.name}-list">${field.datalist().map((v) => `<option value="${esc(v)}"></option>`).join('')}</datalist>`
                : '';
            return `<label>${esc(field.label)}<input type="${field.type || 'text'}" name="${field.name}" value="${value}"${list}${readonly} />${dl}</label>`;
        }

        function renderForm() {
            return `
                <h2>${editing ? '変更' : '追加'}</h2>
                <form>
                    ${config.fields.map((f) => renderField(f, editing)).join('')}
                    <div class="actions">
                        <button type="submit" class="primary">${editing ? '更新' : '追加'}</button>
                        ${editing || config.separateEdit ? '<button type="button" data-cancel>キャンセル</button>' : ''}
                    </div>
                </form>`;
        }

        function renderFilter() {
            if (!config.filter) return '';
            const options = ['', ...config.filter.values()]
                .map((v) => `<option value="${esc(v)}"${v === filterValue ? ' selected' : ''}>${esc(v || 'すべて')}</option>`).join('');
            return `<label class="list-filter">${esc(config.filter.label)}<select data-filter>${options}</select></label>`;
        }

        function render() {
            const showEditScreen = config.separateEdit && inEditScreen;
            if (showEditScreen) {
                root.innerHTML = renderForm();
            } else {
                const visible = config.filter && filterValue
                    ? rows.filter((r) => config.filter.value(r) === filterValue)
                    : rows;
                root.innerHTML = `
                    <h2>${esc(config.title)}</h2>
                    ${renderFilter()}
                    ${config.separateEdit ? '<div class="actions"><button type="button" class="primary" data-add>追加</button></div>' : ''}
                    <div class="table-wrap"><table>
                        <tr>${config.columns.map((c) => `<th>${esc(c.label)}</th>`).join('')}<th></th></tr>
                        ${visible.map((row) => `<tr>${config.columns.map((c) => `<td>${esc(c.value(row))}</td>`).join('')}
                            <td><button type="button" data-edit="${rows.indexOf(row)}">編集</button> <button type="button" class="danger" data-delete="${rows.indexOf(row)}">削除</button></td></tr>`).join('')}
                    </table></div>
                    ${config.separateEdit ? '' : renderForm()}`;
            }

            root.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () => {
                editing = rows[Number(b.dataset.edit)];
                inEditScreen = true;
                render();
            }));
            root.querySelectorAll('[data-delete]').forEach((b) => b.addEventListener('click', () => remove(rows[Number(b.dataset.delete)])));
            const add = root.querySelector('[data-add]');
            if (add) add.addEventListener('click', () => { editing = null; inEditScreen = true; render(); });
            const filter = root.querySelector('[data-filter]');
            if (filter) filter.addEventListener('change', () => { filterValue = filter.value; render(); });
            const cancel = root.querySelector('[data-cancel]');
            if (cancel) cancel.addEventListener('click', () => { editing = null; inEditScreen = false; render(); });
            const form = root.querySelector('form');
            if (form) form.addEventListener('submit', submit);
        }

        async function submit(event) {
            event.preventDefault();
            const payload = {};
            config.fields.forEach((f) => {
                const value = event.target.elements[f.name].value;
                payload[f.name] = f.type === 'tags' ? value.split(',').map((t) => t.trim()).filter(Boolean) : value;
            });
            const method = editing ? 'PUT' : 'POST';
            const url = editing ? `${config.url}/${encodeURIComponent(editing[config.idKey])}` : config.url;
            const result = await guarded(() => api(method, url, payload));
            if (result) {
                rows = result;
                editing = null;
                inEditScreen = false;
                render();
                showMessage(config.afterSave ? config.afterSave() : '保存しました。');
            }
        }

        async function remove(row) {
            if (!window.confirm(`「${config.label(row)}」を削除します。よろしいですか？`)) return;
            const result = await guarded(() => api('DELETE', `${config.url}/${encodeURIComponent(row[config.idKey])}`));
            if (result) {
                rows = result;
                editing = null;
                render();
                showMessage('削除しました。');
            }
        }

        return {
            async load() {
                const data = await guarded(() => api('GET', config.url));
                if (data) {
                    rows = data;
                    render();
                }
            },
        };
    }

    // スキル項目管理
    const skillsPanel = crudPanel(document.getElementById('tab-skills'), {
        key: 'skill',
        title: 'スキル項目',
        separateEdit: true,
        filter: { label: '種類', values: () => categories(), value: (r) => r.category },
        url: urls.skills,
        idKey: 'skill_id',
        label: (row) => row.name,
        columns: [
            { label: '種類', value: (r) => r.category },
            { label: 'サブカテゴリ', value: (r) => r.subcategory },
            { label: '項目', value: (r) => r.name },
            { label: '経験年数', value: (r) => r.years },
            { label: '表示順', value: (r) => r.sort_order },
        ],
        fields: [
            { name: 'skill_id', label: 'skill_id（半角英小文字・数字・ハイフン。登録後は変更不可）', readonlyOnEdit: true },
            { name: 'category', label: '種類', datalist: () => categories() },
            { name: 'subcategory', label: 'サブカテゴリ（任意。案件登録でサブタブに分ける）', datalist: () => subcategories() },
            { name: 'name', label: '表示名' },
            { name: 'sort_order', label: '表示順', type: 'number' },
        ],
        afterSave: () => {
            // 案件登録画面のカテゴリ・スキル項目にも反映する。
            refreshMaster().then(() => { if (project.state) renderProject(); });
            return '保存しました。';
        },
    });

    // 資格・実績・サイト情報管理。1 つのタブに 2 つの一覧とサイト情報のフォームを並べる。
    const certworksRoot = document.getElementById('tab-certworks');
    const certificationsRoot = document.createElement('div');
    const worksRoot = document.createElement('div');
    const siteRoot = document.createElement('div');
    certworksRoot.append(certificationsRoot, worksRoot, siteRoot);

    const certificationsPanel = crudPanel(certificationsRoot, {
        key: 'cert',
        title: '資格',
        url: urls.certifications,
        idKey: 'certification_id',
        label: (row) => row.name,
        columns: [
            { label: '資格名', value: (r) => r.name },
            { label: '取得日', value: (r) => r.acquired_on },
            { label: '発行団体', value: (r) => r.org },
            { label: '表示順', value: (r) => r.sort_order },
        ],
        fields: [
            { name: 'name', label: '資格名' },
            { name: 'acquired_on', label: '取得日（例: Jul 2024）' },
            { name: 'org', label: '発行団体' },
            { name: 'sort_order', label: '表示順', type: 'number' },
        ],
    });
    const worksPanel = crudPanel(worksRoot, {
        key: 'work',
        title: '実績',
        url: urls.works,
        idKey: 'work_id',
        label: (row) => row.title,
        columns: [
            { label: 'タイトル', value: (r) => r.title },
            { label: '使用技術', value: (r) => r.tags.join(', ') },
            { label: '表示順', value: (r) => r.sort_order },
        ],
        fields: [
            { name: 'title', label: 'タイトル' },
            { name: 'desc_ja', label: '説明文（日本語）', type: 'textarea' },
            { name: 'desc_en', label: '説明文（英語）', type: 'textarea' },
            { name: 'tags', label: '使用技術タグ（カンマ区切り）', type: 'tags' },
            { name: 'thumbnail', label: 'サムネイル（例: img/portfolio.png）' },
            { name: 'github_url', label: 'GitHub URL', type: 'url' },
            { name: 'live_url', label: '公開 URL', type: 'url' },
            { name: 'sort_order', label: '表示順', type: 'number' },
        ],
    });

    // サイト情報（1 行のみ）。一覧・追加・削除は持たず、現在の内容を変更する。
    const SITE_FIELDS = [
        { name: 'name', label: '氏名' },
        { name: 'typing_titles', label: 'Hero の肩書き（1 行に 1 件）', type: 'lines' },
        { name: 'catchphrase', label: 'Hero のキャッチコピー' },
        { name: 'intro', label: 'About の自己紹介文', type: 'textarea' },
        { name: 'birth_date', label: '生年月日', type: 'date' },
        { name: 'job', label: '職業' },
        { name: 'education', label: '学歴' },
        { name: 'location', label: '居住地' },
        { name: 'hobby', label: '趣味' },
        { name: 'github_url', label: 'GitHub URL', type: 'url' },
        { name: 'contact_message', label: 'Contact の案内文', type: 'textarea' },
        { name: 'contact_form_url', label: '問い合わせフォーム URL', type: 'url' },
        { name: 'copyright_start_year', label: 'フッターの著作権の開始年', type: 'number' },
    ];

    function renderSiteField(field, value) {
        if (field.type === 'textarea') {
            return `<label>${esc(field.label)}<textarea name="${field.name}" rows="4">${esc(value)}</textarea></label>`;
        }
        if (field.type === 'lines') {
            return `<label>${esc(field.label)}<textarea name="${field.name}" rows="4">${esc((value || []).join('\n'))}</textarea></label>`;
        }
        return `<label>${esc(field.label)}<input type="${field.type || 'text'}" name="${field.name}" value="${esc(value)}" /></label>`;
    }

    async function loadSiteInfo() {
        const data = await guarded(() => api('GET', urls.site));
        if (!data) return;
        siteRoot.innerHTML = `
            <h2>サイト情報</h2>
            <form>
                ${SITE_FIELDS.map((f) => renderSiteField(f, data[f.name])).join('')}
                <div class="actions"><button type="submit" class="primary">更新</button></div>
            </form>`;
        siteRoot.querySelector('form').addEventListener('submit', async (event) => {
            event.preventDefault();
            const payload = {};
            SITE_FIELDS.forEach((f) => {
                const value = event.target.elements[f.name].value;
                payload[f.name] = f.type === 'lines' ? value.split('\n').map((t) => t.trim()).filter(Boolean) : value;
            });
            const saved = await guarded(() => api('PUT', urls.site, payload));
            if (saved) showMessage('保存しました。');
        });
    }

    // --- エクスポート ---

    async function loadExport() {
        const root = document.getElementById('tab-export');
        const data = await guarded(() => api('GET', urls.export));
        if (!data) return;
        const warnings = [];
        if (data.warnings.unused_skill_count > 0) {
            warnings.push(`使用実績がなく出力対象外のスキル項目: ${data.warnings.unused_skill_count}件`);
        }
        root.innerHTML = `
            ${warnings.map((w) => `<p class="message warning">${esc(w)}</p>`).join('')}
            <div class="actions">
                <a href="${esc(urls.exportDownload)}" download><button type="button" class="primary">ダウンロード</button></a>
                <button type="button" id="copy-export">クリップボードへコピー</button>
            </div>
            <h2>プレビュー</h2>
            <pre id="export-preview"></pre>`;
        root.querySelector('#export-preview').textContent = data.markdown;
        root.querySelector('#copy-export').addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(data.markdown);
                showMessage('コピーしました。');
            } catch (error) {
                showMessage('コピーに失敗しました。', 'error');
            }
        });
    }

    // --- タブ切り替え ---

    const tabLoaders = {
        project: () => loadProjectTab(project.state === null),
        skills: async () => {
            if (project.skills.length === 0) await refreshMaster();
            await skillsPanel.load();
        },
        certworks: async () => {
            await certificationsPanel.load();
            await worksPanel.load();
            await loadSiteInfo();
        },
        export: loadExport,
    };

    async function showTab(name) {
        document.querySelectorAll('#main-tabs button').forEach((b) => {
            b.setAttribute('aria-selected', String(b.dataset.tab === name));
        });
        Object.keys(tabLoaders).forEach((key) => {
            document.getElementById(`tab-${key}`).hidden = key !== name;
        });
        showMessage('');
        await tabLoaders[name]();
    }

    document.querySelectorAll('#main-tabs button').forEach((button) => {
        button.addEventListener('click', () => showTab(button.dataset.tab));
    });

    showTab('project');
});
