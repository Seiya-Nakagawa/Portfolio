// スキル実績管理（登録画面）。単一ページ上でタブを切り替え、サーバーの JSON API と通信する。
document.addEventListener('DOMContentLoaded', () => {
    const urls = {
        bootstrap: document.body.dataset.apiBootstrap,
        projects: document.body.dataset.apiProjects,
        skills: document.body.dataset.apiSkills,
        certifications: document.body.dataset.apiCertifications,
        works: document.body.dataset.apiWorks,
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
    const PAGE_CONFIRM = 'confirm';

    const project = {
        state: null, // { project_id, name, start_year_month, end_year_month, selected: {skill_id: version} }
        skills: [],
        levels: [],
        ongoing: [],
        pageIndex: 0,
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

    function pages() {
        return [PAGE_INFO, ...categories(), PAGE_CONFIRM];
    }

    function pageLabel(page) {
        if (page === PAGE_INFO) return '案件情報';
        if (page === PAGE_CONFIRM) return '確認';
        return page;
    }

    function infoIsValid() {
        return project.state.name.trim() !== '' && project.state.start_year_month !== '';
    }

    // スキル項目・レベル・継続中案件を取得する。失敗時は null を返し、メッセージは表示しない。
    async function refreshMaster() {
        try {
            const data = await api('GET', urls.bootstrap);
            project.skills = data.skills;
            project.levels = data.levels;
            project.ongoing = data.ongoing_projects;
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

    function renderProject() {
        const root = document.getElementById('tab-project');
        const list = pages();
        const current = list[project.pageIndex];
        const hasId = project.state.project_id !== '';
        const options = ['<option value="">（選択してください）</option>']
            .concat(project.ongoing.map((p) => (
                `<option value="${esc(p.project_id)}"${p.project_id === project.state.project_id ? ' selected' : ''}>${esc(p.name)}</option>`
            ))).join('');

        root.innerHTML = `
            <div class="row">
                <label>継続中の案件
                    <select id="ongoing-select">${options}</select>
                </label>
                <button type="button" id="new-project">新規作成</button>
            </div>
            <div class="page-tabs" role="tablist">
                ${list.map((p, i) => `<button type="button" role="tab" data-page="${i}" aria-selected="${i === project.pageIndex}">${esc(pageLabel(p))}</button>`).join('')}
            </div>
            <div id="project-page"></div>
            <div class="actions">
                <button type="button" id="prev-page"${project.pageIndex === 0 ? ' disabled' : ''}>戻る</button>
                <button type="button" id="next-page"${current === PAGE_CONFIRM ? ' disabled' : ''}>次へ</button>
                <span class="spacer"></span>
                ${current === PAGE_CONFIRM ? '<button type="button" class="primary" id="save-project">保存</button>' : ''}
                ${hasId ? '<button type="button" class="danger" id="delete-project">削除</button>' : ''}
            </div>`;

        renderProjectPage(current);

        root.querySelector('#ongoing-select').addEventListener('change', async (e) => {
            if (!e.target.value) return;
            const data = await guarded(() => api('GET', `${urls.projects}/${encodeURIComponent(e.target.value)}`));
            if (data) {
                project.state = fromServer(data);
                project.pageIndex = 0;
                renderProject();
            }
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
            project.pageIndex = Math.min(list.length - 1, project.pageIndex + 1);
            renderProject();
        });
        const saveButton = root.querySelector('#save-project');
        if (saveButton) saveButton.addEventListener('click', saveProject);
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

        if (page === PAGE_CONFIRM) {
            const chosen = project.skills.filter((sk) => sk.skill_id in s.selected);
            body.innerHTML = `
                <table>
                    <tr><th>案件名</th><td>${esc(s.name)}</td></tr>
                    <tr><th>開始年月</th><td>${esc(s.start_year_month)}</td></tr>
                    <tr><th>終了年月</th><td>${s.end_year_month ? esc(s.end_year_month) : '継続中'}</td></tr>
                </table>
                <h2>選択したスキル項目（${chosen.length}件）</h2>
                <div class="table-wrap"><table>
                    <tr><th>種類</th><th>項目</th><th>バージョン</th></tr>
                    ${chosen.map((sk) => `<tr><td>${esc(sk.category)}</td><td>${esc(sk.name)}</td><td>${esc(s.selected[sk.skill_id])}</td></tr>`).join('')}
                </table></div>`;
            return;
        }

        const items = project.skills.filter((sk) => sk.category === page);
        body.innerHTML = items.map((sk) => {
            const checked = sk.skill_id in s.selected;
            return `
                <div class="skill-check">
                    <label><input type="checkbox" data-skill="${esc(sk.skill_id)}"${checked ? ' checked' : ''} />${esc(sk.name)}</label>
                    <input type="text" data-version="${esc(sk.skill_id)}" placeholder="バージョン（任意）" maxlength="64" value="${esc(s.selected[sk.skill_id] ?? '')}"${checked ? '' : ' hidden'} />
                </div>`;
        }).join('');
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

        function render() {
            root.innerHTML = `
                <h2>${esc(config.title)}</h2>
                <div class="table-wrap"><table>
                    <tr>${config.columns.map((c) => `<th>${esc(c.label)}</th>`).join('')}<th></th></tr>
                    ${rows.map((row, i) => `<tr>${config.columns.map((c) => `<td>${esc(c.value(row))}</td>`).join('')}
                        <td><button type="button" data-edit="${i}">編集</button> <button type="button" class="danger" data-delete="${i}">削除</button></td></tr>`).join('')}
                </table></div>
                <h2>${editing ? '変更' : '追加'}</h2>
                <form>
                    ${config.fields.map((f) => renderField(f, editing)).join('')}
                    <div class="actions">
                        <button type="submit" class="primary">${editing ? '更新' : '追加'}</button>
                        ${editing ? '<button type="button" data-cancel>キャンセル</button>' : ''}
                    </div>
                </form>`;

            root.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () => {
                editing = rows[Number(b.dataset.edit)];
                render();
            }));
            root.querySelectorAll('[data-delete]').forEach((b) => b.addEventListener('click', () => remove(rows[Number(b.dataset.delete)])));
            const cancel = root.querySelector('[data-cancel]');
            if (cancel) cancel.addEventListener('click', () => { editing = null; render(); });
            root.querySelector('form').addEventListener('submit', submit);
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
        url: urls.skills,
        idKey: 'skill_id',
        label: (row) => row.name,
        columns: [
            { label: '種類', value: (r) => r.category },
            { label: '項目', value: (r) => r.name },
            { label: 'レベル', value: (r) => r.level },
            { label: '補足', value: (r) => r.remarks },
            { label: '経験年数', value: (r) => r.years },
            { label: '表示順', value: (r) => r.sort_order },
        ],
        fields: [
            { name: 'skill_id', label: 'skill_id（半角英小文字・数字・ハイフン。登録後は変更不可）', readonlyOnEdit: true },
            { name: 'category', label: '種類', datalist: () => categories() },
            { name: 'name', label: '表示名' },
            { name: 'level', label: 'レベル', type: 'select', options: () => project.levels.map((l) => ({ value: l.level, label: `${l.level}: ${l.label}` })) },
            { name: 'remarks', label: '補足（職務経歴書のレベル列に付記）' },
            { name: 'sort_order', label: '表示順', type: 'number' },
        ],
        afterSave: () => {
            // 案件登録画面のカテゴリ・スキル項目にも反映する。
            refreshMaster().then(() => { if (project.state) renderProject(); });
            return '保存しました。';
        },
    });

    // 資格・実績管理。1 つのタブに 2 つの一覧を並べる。
    const certworksRoot = document.getElementById('tab-certworks');
    const certificationsRoot = document.createElement('div');
    const worksRoot = document.createElement('div');
    certworksRoot.append(certificationsRoot, worksRoot);

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

    // --- エクスポート ---

    async function loadExport() {
        const root = document.getElementById('tab-export');
        const data = await guarded(() => api('GET', urls.export));
        if (!data) return;
        const warnings = [];
        if (data.warnings.unused_skill_count > 0) {
            warnings.push(`使用実績がなく出力対象外のスキル項目: ${data.warnings.unused_skill_count}件`);
        }
        if (data.warnings.invalid_level_skills.length > 0) {
            warnings.push(`レベルが未定義のスキル項目: ${data.warnings.invalid_level_skills.join('、')}`);
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
            if (project.levels.length === 0) await refreshMaster();
            await skillsPanel.load();
        },
        certworks: async () => {
            await certificationsPanel.load();
            await worksPanel.load();
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
