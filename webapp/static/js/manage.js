// スキル実績管理（登録画面）。単一ページ上でタブを切り替え、サーバーの JSON API と通信する。
document.addEventListener('DOMContentLoaded', () => {
    const urls = {
        bootstrap: document.body.dataset.apiBootstrap,
        projects: document.body.dataset.apiProjects,
        skills: document.body.dataset.apiSkills,
        categories: document.body.dataset.apiCategories,
        categoryOrder: document.body.dataset.apiCategoryOrder,
        certifications: document.body.dataset.apiCertifications,
        works: document.body.dataset.apiWorks,
        site: document.body.dataset.apiSite,
        upload: document.body.dataset.apiUpload,
        mediaBase: document.body.dataset.mediaBase,
        skillsheet: document.body.dataset.apiSkillsheet,
        skillsheetPdf: document.body.dataset.skillsheetPdf,
        skillsheetMarkdown: document.body.dataset.skillsheetMarkdown,
    };
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

    const toastEl = document.getElementById('toast');
    // エラーは文章が長くなりがちなため、成功・警告より長く表示する。
    const TOAST_DURATION_MS = { ok: 3000, warning: 4000, error: 5000 };
    let toastTimer = null;

    // 完了通知・エラー・警告は、いずれも画面右上のポップアップ（トースト）で表示する。
    function showMessage(text, kind = 'ok') {
        clearTimeout(toastTimer);
        toastEl.hidden = true;
        if (!text) return;
        toastEl.textContent = text;
        toastEl.className = `toast toast-${kind}`;
        toastEl.hidden = false;
        toastTimer = setTimeout(() => { toastEl.hidden = true; }, TOAST_DURATION_MS[kind] ?? TOAST_DURATION_MS.ok);
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

    // 各画面の先頭に置く見出し。補足文と主要操作（追加・新規作成など）を同じ行にまとめる。
    function pageHead(title, { sub = '', actions = '', back = '' } = {}) {
        return `
            <div class="page-head">
                <div>
                    ${back ? `<button type="button" class="link" ${back}>← 一覧に戻る</button>` : ''}
                    <h2>${esc(title)}</h2>
                    ${sub ? `<p class="sub">${esc(sub)}</p>` : ''}
                </div>
                ${actions ? `<div class="head-actions">${actions}</div>` : ''}
            </div>`;
    }

    // --- 画像 ---

    // 画像のパスは MEDIA_ROOT からの相対パスで保持している。外部 URL はそのまま使う。
    function imageUrl(path) {
        return /^(https?:)?\/\//.test(path) ? path : urls.mediaBase + path;
    }

    async function uploadImage(file) {
        const form = new FormData();
        form.append('image', file);
        const response = await fetch(urls.upload, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
            body: form,
        });
        if (response.status === 401) {
            window.location.reload();
            throw new Error('ログインが必要です。');
        }
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error((data.errors || ['画像のアップロードに失敗しました。']).join('\n'));
        }
        return data;
    }

    // --- 案件登録 ---

    const SUB_OTHER = 'その他';
    const SUB_ALL = 'すべて';

    const project = {
        state: null, // { project_id, name, start_year_month, end_year_month, selected: {skill_id: version} }
        skills: [],
        ongoing: [],
        finished: [],
        activeCategory: '', // スキル選択で表示中のカテゴリ
        confirming: false, // true の間は入力画面とは別の確認画面を表示する
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

    // 種類マスタの並び順（スキル項目を持たない種類を含む）。スキル項目の入力候補・絞り込みに使う。
    function masterCategories() {
        return project.categoryNames || categories();
    }

    // カテゴリの順序は、各カテゴリの sort_order 最小値の昇順（サーバーの並び順に従う）。
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

    function infoIsValid() {
        return project.state.name.trim() !== '' && project.state.start_year_month !== '';
    }

    // スキル項目・継続中案件を取得する。失敗時は null を返し、メッセージは表示しない。
    async function refreshMaster() {
        try {
            const data = await api('GET', urls.bootstrap);
            project.skills = data.skills;
            project.categoryNames = data.categories;
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
        }
        renderProject();
    }

    // 入力内容の確認画面。登録か入力への戻りのみを選べる。
    function renderConfirm() {
        const root = document.getElementById('tab-project');
        const s = project.state;
        const chosen = project.skills.filter((sk) => sk.skill_id in s.selected);
        root.innerHTML = `
            ${pageHead('入力内容の確認', { sub: '内容を確認して「登録」を押すと保存します。' })}
            <div class="card">
                <h3>案件情報</h3>
                <table class="kv">
                    <tr><th>案件名</th><td>${esc(s.name)}</td></tr>
                    <tr><th>開始年月</th><td>${esc(s.start_year_month)}</td></tr>
                    <tr><th>終了年月</th><td>${s.end_year_month ? esc(s.end_year_month) : '継続中'}</td></tr>
                </table>
            </div>
            <div class="card">
                <h3>選択したスキル項目（${chosen.length}件）</h3>
                ${chosen.length === 0 ? '<p class="empty">スキル項目は選択されていません。</p>' : `<div class="table-wrap"><table class="data-table">
                    <thead><tr><th>種類</th><th>項目</th><th>バージョン</th></tr></thead>
                    <tbody>${chosen.map((sk) => `<tr><td>${esc(sk.category)}</td><td>${esc(sk.name)}</td><td>${esc(s.selected[sk.skill_id])}</td></tr>`).join('')}</tbody>
                </table></div>`}
                <div class="form-bar">
                    <button type="button" id="back-to-input">入力に戻る</button>
                    <button type="button" class="primary" id="save-project">登録</button>
                </div>
            </div>`;
        root.querySelector('#back-to-input').addEventListener('click', () => {
            project.confirming = false;
            showMessage('');
            renderProject();
        });
        root.querySelector('#save-project').addEventListener('click', saveProject);
    }

    // 案件情報の必須項目を満たさない場合は、案件情報のカードへ戻してエラーを表示する。
    function goToConfirm() {
        showMessage('');
        if (!infoIsValid()) {
            showInfoErrors();
            return;
        }
        project.confirming = true;
        renderProject();
        window.scrollTo({ top: 0 });
    }

    function showInfoErrors() {
        const card = document.getElementById('info-card');
        if (!card) {
            project.confirming = false;
            renderProject();
            showInfoErrors();
            return;
        }
        [['#p-name', project.state.name.trim() === ''], ['#p-start', project.state.start_year_month === '']].forEach(([selector, bad]) => {
            const input = card.querySelector(selector);
            input.classList.toggle('invalid', bad);
            input.setAttribute('aria-invalid', String(bad));
        });
        card.scrollIntoView({ block: 'center' });
        const firstBad = card.querySelector('.invalid');
        if (firstBad) firstBad.focus();
        showMessage('案件名と開始年月を入力してください。', 'error');
    }

    function renderProject() {
        if (project.confirming) {
            renderConfirm();
            return;
        }
        const root = document.getElementById('tab-project');
        const s = project.state;
        const hasId = s.project_id !== '';
        const projectOptions = (list, label) => ['<option value="">（選択してください）</option>']
            .concat(list.map((p) => (
                `<option value="${esc(p.project_id)}"${p.project_id === s.project_id ? ' selected' : ''}>${esc(label(p))}</option>`
            ))).join('');

        root.innerHTML = `
            ${pageHead('案件登録', {
        sub: hasId ? `「${s.name}」を編集しています。` : '新しい案件を登録します。',
        actions: '<button type="button" id="new-project">新規作成</button>',
    })}
            <div class="card picker">
                <div class="row">
                    <label>継続中の案件を編集する
                        <select id="ongoing-select">${projectOptions(project.ongoing, (p) => p.name)}</select>
                    </label>
                </div>
                <details class="finished-projects"${project.finishedOpen ? ' open' : ''}>
                    <summary>終了済みの案件を訂正する</summary>
                    <div class="row">
                        <label>終了済みの案件
                            <select id="finished-select">${projectOptions(project.finished, (p) => `${p.name}（${p.start_year_month}〜${p.end_year_month}）`)}</select>
                        </label>
                    </div>
                </details>
            </div>
            <div class="project-layout">
                <div>
                    <div class="card" id="info-card">
                        <h3>案件情報</h3>
                        <label>案件名<input type="text" id="p-name" value="${esc(s.name)}" maxlength="255" required /></label>
                        <div class="row">
                            <label>開始年月<input type="month" id="p-start" value="${esc(s.start_year_month)}" required /></label>
                            <label>終了年月<input type="month" id="p-end" value="${esc(s.end_year_month)}" /></label>
                        </div>
                        <p><label><input type="checkbox" id="p-ongoing"${s.end_year_month === '' ? ' checked' : ''} />継続中（終了年月を空欄のままにする）</label></p>
                    </div>
                    <div class="card">
                        <h3>使用したスキル</h3>
                        <div id="skill-area"></div>
                    </div>
                </div>
                <aside class="card tray" id="tray" aria-label="選択中のスキル"></aside>
            </div>`;

        bindInfoFields(root);
        renderSkillArea();
        renderTray();

        // 継続中・終了済みのどちらのプルダウンも、選んだ案件を登録フォームへ読み込む。
        [['#ongoing-select', false], ['#finished-select', true]].forEach(([selector, isFinished]) => {
            root.querySelector(selector).addEventListener('change', async (e) => {
                if (!e.target.value) return;
                const data = await guarded(() => api('GET', `${urls.projects}/${encodeURIComponent(e.target.value)}`));
                if (data) {
                    project.state = fromServer(data);
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
            showMessage('');
            renderProject();
        });
    }

    function bindInfoFields(root) {
        const s = project.state;
        const nameInput = root.querySelector('#p-name');
        const startInput = root.querySelector('#p-start');
        const endInput = root.querySelector('#p-end');
        const ongoingCheck = root.querySelector('#p-ongoing');
        endInput.disabled = ongoingCheck.checked;
        // 入力されたらエラー表示を解除する。
        const clearInvalid = (input) => { input.classList.remove('invalid'); input.removeAttribute('aria-invalid'); };
        nameInput.addEventListener('input', (e) => { s.name = e.target.value; clearInvalid(nameInput); });
        startInput.addEventListener('input', (e) => { s.start_year_month = e.target.value; clearInvalid(startInput); });
        endInput.addEventListener('input', (e) => { s.end_year_month = e.target.value; });
        ongoingCheck.addEventListener('change', (e) => {
            endInput.disabled = e.target.checked;
            if (e.target.checked) {
                s.end_year_month = '';
                endInput.value = '';
            }
        });
    }

    // カテゴリのタブとサブタブ、選択中のカテゴリのスキル項目チップを描画する。
    function renderSkillArea() {
        const area = document.getElementById('skill-area');
        const s = project.state;
        const cats = categories();
        if (cats.length === 0) {
            area.innerHTML = '<p class="empty">スキル項目が登録されていません。「スキル項目管理」から追加してください。</p>';
            return;
        }
        if (!cats.includes(project.activeCategory)) project.activeCategory = cats[0];
        const page = project.activeCategory;
        const categoryItems = project.skills.filter((sk) => sk.category === page);
        const subs = subcategoriesOf(categoryItems);
        const chipHtml = (sk) => `<label class="chip"><input type="checkbox" data-skill="${esc(sk.skill_id)}"${sk.skill_id in s.selected ? ' checked' : ''} />${esc(sk.name)}</label>`;
        const chipsHtml = (items) => `<div class="chips">${items.map(chipHtml).join('')}</div>`;

        let subTabsHtml = '';
        let contentHtml = chipsHtml(categoryItems);
        const tabs = subs.length > 0 ? [SUB_ALL, ...subs] : [];
        if (tabs.length > 0) {
            // 既定は「すべて」。「すべて」ではサブカテゴリのセクション単位で表示する。
            const activeSub = tabs.includes(project.subTabs[page]) ? project.subTabs[page] : SUB_ALL;
            project.subTabs[page] = activeSub;
            const inSub = (sub) => categoryItems.filter((sk) => (sk.subcategory || SUB_OTHER) === sub);
            contentHtml = activeSub === SUB_ALL
                ? subs.map((sub) => `<div class="sub-section"><h4>${esc(sub)}</h4>${chipsHtml(inSub(sub))}</div>`).join('')
                : chipsHtml(inSub(activeSub));
            subTabsHtml = `<div class="sub-tabs" role="tablist" aria-label="サブカテゴリ">${tabs.map((sub, i) => `<button type="button" role="tab" data-sub="${i}" aria-selected="${sub === activeSub}">${esc(sub)}</button>`).join('')}</div>`;
        }

        area.innerHTML = `
            <div class="page-tabs" role="tablist" aria-label="種類">
                ${cats.map((c, i) => `<button type="button" role="tab" data-cat="${i}" aria-selected="${c === page}">${esc(c)}<span class="badge" data-badge="${i}"></span></button>`).join('')}
            </div>
            ${subTabsHtml}
            ${contentHtml}`;
        updateBadges();

        area.querySelectorAll('[data-cat]').forEach((button) => {
            button.addEventListener('click', () => {
                project.activeCategory = cats[Number(button.dataset.cat)];
                renderSkillArea();
            });
        });
        area.querySelectorAll('[data-sub]').forEach((button) => {
            button.addEventListener('click', () => {
                project.subTabs[page] = tabs[Number(button.dataset.sub)];
                renderSkillArea();
            });
        });
        area.querySelectorAll('input[data-skill]').forEach((check) => {
            check.addEventListener('change', () => {
                if (check.checked) {
                    s.selected[check.dataset.skill] = s.selected[check.dataset.skill] ?? '';
                } else {
                    delete s.selected[check.dataset.skill];
                }
                updateBadges();
                renderTray();
            });
        });
    }

    // カテゴリのタブに、選択中の項目数を表示する。
    function updateBadges() {
        const s = project.state;
        categories().forEach((category, i) => {
            const badge = document.querySelector(`[data-badge="${i}"]`);
            if (!badge) return;
            const count = project.skills.filter((sk) => sk.category === category && sk.skill_id in s.selected).length;
            badge.textContent = count > 0 ? String(count) : '';
        });
    }

    // 選択中のスキルを常時表示し、バージョンの入力と取り外しを行う。
    function renderTray() {
        const tray = document.getElementById('tray');
        const s = project.state;
        const chosen = project.skills.filter((sk) => sk.skill_id in s.selected);
        const groups = categories()
            .map((category) => [category, chosen.filter((sk) => sk.category === category)])
            .filter(([, items]) => items.length > 0);
        tray.innerHTML = `
            <div class="tray-title"><span>選択中のスキル</span><span><b>${chosen.length}</b>件</span></div>
            ${groups.length === 0 ? '<p class="tray-empty">左の一覧からスキルを選ぶと、ここに表示されます。バージョンはここで入力できます。</p>' : groups.map(([category, items]) => `
                <h4>${esc(category)}</h4>
                ${items.map((sk) => `<div class="tray-row">
                    <span>${esc(sk.name)}</span>
                    <input type="text" data-version="${esc(sk.skill_id)}" placeholder="バージョン" aria-label="${esc(sk.name)}のバージョン" maxlength="64" value="${esc(s.selected[sk.skill_id])}" />
                    <button type="button" data-remove="${esc(sk.skill_id)}" aria-label="${esc(sk.name)}を外す">×</button>
                </div>`).join('')}`).join('')}
            <div class="tray-actions">
                <button type="button" class="primary" id="confirm-project">確認へ</button>
                ${s.project_id !== '' ? '<button type="button" class="danger" id="delete-project">この案件を削除</button>' : ''}
            </div>`;
        tray.querySelectorAll('input[data-version]').forEach((input) => {
            input.addEventListener('input', () => { s.selected[input.dataset.version] = input.value; });
        });
        tray.querySelectorAll('[data-remove]').forEach((button) => {
            button.addEventListener('click', () => {
                delete s.selected[button.dataset.remove];
                renderSkillArea();
                renderTray();
            });
        });
        tray.querySelector('#confirm-project').addEventListener('click', goToConfirm);
        const deleteButton = tray.querySelector('#delete-project');
        if (deleteButton) deleteButton.addEventListener('click', deleteProject);
    }

    async function saveProject() {
        const s = project.state;
        // 保存時は必ず案件情報の必須項目を確認し、未入力なら入力画面へ戻す。
        if (!infoIsValid()) {
            project.confirming = false;
            renderProject();
            showInfoErrors();
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

    // 年月（YYYY-MM）を表示用の YYYY年MM月に整形する。未設定は空欄とする。
    function formatYearMonth(value) {
        const match = /^(\d{4})-(\d{2})$/.exec(value || '');
        return match ? `${match[1]}年${match[2]}月` : '';
    }

    // --- 追加・更新前の確認画面（スキル項目・資格・実績・サイト情報で共通） ---

    // 入力欄のラベルから、確認画面に表示する項目名（括弧書きの補足を除いたもの）を取り出す。
    function confirmLabel(label) {
        return label.split('（')[0];
    }

    function confirmValue(value) {
        return Array.isArray(value) ? value.join(', ') : String(value ?? '');
    }

    // before を渡した場合は、変更のあった項目のみを修正前・修正後の 2 列で表示する。
    function renderConfirmScreen(root, { title, rows, before, saveLabel, onBack, onSave }) {
        let body;
        if (before) {
            const changed = rows
                .map(([label, value], i) => ({ label, after: value, before: before[i] }))
                .filter((r) => confirmValue(r.after) !== confirmValue(r.before));
            body = changed.length === 0
                ? '<p class="empty">変更された項目はありません。</p>'
                : `<div class="table-wrap"><table class="data-table">
                    <thead><tr><th>項目</th><th>修正前</th><th>修正後</th></tr></thead>
                    <tbody>${changed.map((r) => `<tr><th scope="row">${esc(r.label)}</th><td class="pre-line">${esc(confirmValue(r.before))}</td><td class="pre-line">${esc(confirmValue(r.after))}</td></tr>`).join('')}</tbody>
                </table></div>`;
        } else {
            body = `<div class="table-wrap"><table class="kv">
                ${rows.map(([label, value]) => `<tr><th scope="row">${esc(label)}</th><td class="pre-line">${esc(confirmValue(value))}</td></tr>`).join('')}
            </table></div>`;
        }
        root.innerHTML = `
            ${pageHead(`${title}の確認`, { sub: `内容を確認して「${saveLabel}」を押すと保存します。` })}
            <div class="card">
                ${body}
                <div class="form-bar">
                    <button type="button" data-confirm-back>入力に戻る</button>
                    <button type="button" class="primary" data-confirm-save>${esc(saveLabel)}</button>
                </div>
            </div>`;
        root.querySelector('[data-confirm-back]').addEventListener('click', onBack);
        root.querySelector('[data-confirm-save]').addEventListener('click', onSave);
        window.scrollTo({ top: 0 });
    }

    // --- 一覧・追加・変更・削除の共通画面（スキル項目・資格・実績） ---

    function crudPanel(root, config) {
        let rows = [];
        let editing = null; // 編集中の行。追加時は null
        let inEditScreen = false; // separateEdit 指定時に、一覧ではなく編集画面を表示中か
        let filterValue = ''; // filter 指定時に、絞り込み中の値（空は絞り込みなし）
        let searchValue = ''; // キーワード検索の入力値
        let draft = null; // 入力済みで確認待ちの内容。入力に戻る場合はフォームへ再表示する
        let confirming = false; // true の間は保存前の確認画面を表示する

        function fieldValue(row, field) {
            const value = row ? row[field.name] : '';
            return Array.isArray(value) ? value.join(', ') : (value ?? '');
        }

        function formatField(field, source) {
            const value = source[field.name];
            return field.format ? field.format(value) : (Array.isArray(value) ? value.join(', ') : value);
        }

        // フォームの初期値は、確認画面から戻った場合は入力途中の内容、それ以外は編集対象の行とする。
        function formSource() {
            return draft || editing;
        }

        function renderField(field, row) {
            const value = esc(fieldValue(row, field));
            const readonly = editing && field.readonlyOnEdit ? ' disabled' : '';
            if (field.type === 'select') {
                const options = field.options().map((o) => `<option value="${esc(o.value)}"${String(o.value) === String(fieldValue(row, field)) ? ' selected' : ''}>${esc(o.label)}</option>`).join('');
                return `<label>${esc(field.label)}<select name="${field.name}">${options}</select></label>`;
            }
            if (field.type === 'textarea') {
                return `<label class="wide">${esc(field.label)}<textarea name="${field.name}" rows="4">${value}</textarea></label>`;
            }
            if (field.type === 'image') {
                const current = fieldValue(row, field);
                return `<div class="image-field wide" data-image-field>
                    <span>${esc(field.label)}</span>
                    <input type="hidden" name="${field.name}" value="${value}" />
                    <img class="image-preview" alt="サムネイルのプレビュー" src="${current ? esc(imageUrl(current)) : ''}"${current ? '' : ' hidden'} />
                    <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" data-image-input />
                </div>`;
            }
            const list = field.datalist ? ` list="${config.key}-${field.name}-list"` : '';
            const dl = field.datalist
                ? `<datalist id="${config.key}-${field.name}-list">${field.datalist().map((v) => `<option value="${esc(v)}"></option>`).join('')}</datalist>`
                : '';
            return `<label>${esc(field.label)}<input type="${field.type || 'text'}" name="${field.name}" value="${value}"${list}${readonly} />${dl}</label>`;
        }

        function renderForm() {
            const heading = `${config.title}を${editing ? '変更' : '追加'}`;
            return `
                ${pageHead(heading, { back: 'data-cancel' })}
                <form class="card">
                    <div class="form-grid">
                        ${config.fields.map((f) => renderField(f, formSource())).join('')}
                    </div>
                    <div class="form-bar">
                        <button type="submit" class="primary">確認へ</button>
                        <button type="button" data-cancel>キャンセル</button>
                    </div>
                </form>`;
        }

        function renderFilter() {
            if (!config.filter) return '';
            const options = ['', ...config.filter.values()]
                .map((v) => `<option value="${esc(v)}"${v === filterValue ? ' selected' : ''}>${esc(v || 'すべて')}</option>`).join('');
            return `<label>${esc(config.filter.label)}<select data-filter>${options}</select></label>`;
        }

        // 絞り込み（フィルタ・キーワード検索）後の行。キーワードは一覧に表示する列の値を対象とする。
        function visibleRows() {
            const keyword = searchValue.trim().toLowerCase();
            return rows.filter((r) => (
                (!config.filter || !filterValue || config.filter.value(r) === filterValue)
                && (keyword === '' || config.columns.some((c) => String(c.value(r)).toLowerCase().includes(keyword)))
            ));
        }

        function bodyHtml(visible) {
            if (visible.length === 0) {
                const hint = rows.length === 0 ? '「追加」から最初の1件を登録できます。' : '検索条件を変えてください。';
                return `<tr><td colspan="${config.columns.length + 1}" class="empty">該当するデータがありません。${hint}</td></tr>`;
            }
            return visible.map((row) => `<tr>${config.columns.map((c) => `<td${c.numeric ? ' class="num"' : ''}>${esc(c.value(row))}</td>`).join('')}
                <td class="row-actions"><button type="button" class="sm" data-edit="${rows.indexOf(row)}">編集</button><button type="button" class="sm danger" data-delete="${rows.indexOf(row)}">削除</button></td></tr>`).join('');
        }

        function countText(visible) {
            return visible.length === rows.length ? `${rows.length}件` : `${visible.length}件 / 全${rows.length}件`;
        }

        // 一覧の本文と件数のみを更新する（検索入力中にフォーカスを失わないため）。
        function refreshList() {
            const visible = visibleRows();
            root.querySelector('[data-body]').innerHTML = bodyHtml(visible);
            root.querySelector('[data-count]').textContent = countText(visible);
            bindRowActions();
        }

        function bindRowActions() {
            root.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () => {
                editing = rows[Number(b.dataset.edit)];
                draft = null;
                inEditScreen = true;
                render();
                window.scrollTo({ top: 0 });
            }));
            root.querySelectorAll('[data-delete]').forEach((b) => b.addEventListener('click', () => remove(rows[Number(b.dataset.delete)])));
        }

        function render() {
            const showEditScreen = config.separateEdit && inEditScreen;
            if (confirming) {
                renderConfirmScreen(root, {
                    title: config.title,
                    saveLabel: editing ? '更新' : '追加',
                    rows: config.fields.map((f) => [confirmLabel(f.label), formatField(f, draft)]),
                    before: editing ? config.fields.map((f) => formatField(f, editing)) : undefined,
                    onBack: () => { confirming = false; render(); },
                    onSave: save,
                });
                return;
            }
            if (showEditScreen) {
                root.innerHTML = renderForm();
                const cancel = root.querySelectorAll('[data-cancel]');
                cancel.forEach((b) => b.addEventListener('click', () => { editing = null; draft = null; inEditScreen = false; render(); }));
                root.querySelector('form').addEventListener('submit', submit);
                root.querySelectorAll('[data-image-field]').forEach(bindImageField);
                return;
            }
            const visible = visibleRows();
            root.innerHTML = `
                ${pageHead(config.title, { actions: '<button type="button" class="primary" data-add>＋ 追加</button>' })}
                <div class="card">
                    <div class="toolbar">
                        ${renderFilter()}
                        <label class="search">キーワード検索<input type="search" data-search value="${esc(searchValue)}" placeholder="表示中の項目から探す" /></label>
                        <span class="count" data-count aria-live="polite">${countText(visible)}</span>
                    </div>
                    <div class="table-wrap"><table class="data-table">
                        <thead><tr>${config.columns.map((c) => `<th>${esc(c.label)}</th>`).join('')}<th></th></tr></thead>
                        <tbody data-body>${bodyHtml(visible)}</tbody>
                    </table></div>
                </div>`;
            bindRowActions();
            root.querySelector('[data-add]').addEventListener('click', () => {
                editing = null;
                draft = null;
                inEditScreen = true;
                render();
                window.scrollTo({ top: 0 });
            });
            const filter = root.querySelector('[data-filter]');
            if (filter) filter.addEventListener('change', () => { filterValue = filter.value; refreshList(); });
            root.querySelector('[data-search]').addEventListener('input', (e) => { searchValue = e.target.value; refreshList(); });
        }

        // 画像を選択した時点でアップロードし、保存先のパスを hidden の入力欄へ保持する。
        function bindImageField(wrapper) {
            const input = wrapper.querySelector('[data-image-input]');
            const hidden = wrapper.querySelector('input[type="hidden"]');
            const preview = wrapper.querySelector('.image-preview');
            input.addEventListener('change', async () => {
                if (!input.files.length) return;
                const result = await guarded(() => uploadImage(input.files[0]));
                if (!result) { input.value = ''; return; }
                hidden.value = result.path;
                preview.src = imageUrl(result.path);
                preview.hidden = false;
            });
        }

        // 入力内容を確認画面へ渡す。保存は確認画面で承認した場合のみ行う。
        function submit(event) {
            event.preventDefault();
            const payload = {};
            config.fields.forEach((f) => {
                const value = event.target.elements[f.name].value;
                payload[f.name] = f.type === 'tags' ? value.split(',').map((t) => t.trim()).filter(Boolean) : value;
            });
            showMessage('');
            draft = payload;
            confirming = true;
            render();
        }

        async function save() {
            const method = editing ? 'PUT' : 'POST';
            const url = editing ? `${config.url}/${encodeURIComponent(editing[config.idKey])}` : config.url;
            const result = await guarded(() => api(method, url, draft));
            if (result) {
                rows = result;
                editing = null;
                draft = null;
                confirming = false;
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
        filter: { label: '種類', values: () => masterCategories(), value: (r) => r.category },
        url: urls.skills,
        idKey: 'skill_id',
        label: (row) => row.name,
        columns: [
            { label: '種類', value: (r) => r.category },
            { label: 'サブカテゴリ', value: (r) => r.subcategory },
            { label: '項目', value: (r) => r.name },
            { label: '経験年数', value: (r) => r.years, numeric: true },
        ],
        fields: [
            { name: 'skill_id', label: 'skill_id（半角英小文字・数字・ハイフン。登録後は変更不可）', readonlyOnEdit: true },
            { name: 'category', label: '種類', datalist: () => masterCategories() },
            { name: 'subcategory', label: 'サブカテゴリ（任意。案件登録でサブタブに分ける）', datalist: () => subcategories() },
            { name: 'name', label: '表示名' },
        ],
        afterSave: () => {
            // 案件登録画面のカテゴリ・スキル項目にも反映する。
            refreshMaster().then(() => { if (project.state) renderProject(); });
            return '保存しました。';
        },
    });

    // 種類管理。サイト管理者のみの作業として、追加・名称変更・削除・並び替えをこのタブに集約する。
    const categoriesRoot = document.getElementById('tab-categories');
    let categoryRows = [];
    let editingCategory = null; // 名称変更中の種類名

    function renderCategories() {
        const last = categoryRows.length - 1;
        categoriesRoot.innerHTML = `
            ${pageHead('種類管理', { sub: 'スキルの種類の追加・名称変更・並び替え・削除を行います。並び順は案件登録のタブ順に反映されます。' })}
            <div class="card">
                <form data-add class="toolbar">
                    <label class="search">新しい種類名<input type="text" name="name" required /></label>
                    <button type="submit" class="primary">＋ 追加</button>
                </form>
                <div class="table-wrap"><table class="data-table">
                    <thead><tr><th>種類</th><th>項目数</th><th></th></tr></thead>
                    <tbody>${categoryRows.length === 0 ? '<tr><td colspan="3" class="empty">種類が登録されていません。上の入力欄から追加できます。</td></tr>' : categoryRows.map((c, i) => `<tr>
                        <td>${editingCategory === c.name
        ? `<form data-rename class="row"><input type="text" name="name" value="${esc(c.name)}" aria-label="新しい種類名" /> <button type="submit" class="primary sm">保存</button> <button type="button" class="sm" data-rename-cancel>キャンセル</button></form>`
        : esc(c.name)}</td>
                        <td class="num">${c.skill_count}</td>
                        <td class="row-actions">
                            <button type="button" class="sm" data-move="${i}" data-dir="-1" aria-label="${esc(c.name)}を上へ"${i === 0 ? ' disabled' : ''}>↑</button>
                            <button type="button" class="sm" data-move="${i}" data-dir="1" aria-label="${esc(c.name)}を下へ"${i === last ? ' disabled' : ''}>↓</button>
                            <button type="button" class="sm" data-rename-start="${i}">名称変更</button>
                            <button type="button" class="sm danger" data-delete="${i}">削除</button>
                        </td></tr>`).join('')}</tbody>
                </table></div>
            </div>`;

        categoriesRoot.querySelectorAll('[data-move]').forEach((b) => b.addEventListener('click', () => moveCategory(Number(b.dataset.move), Number(b.dataset.dir))));
        categoriesRoot.querySelectorAll('[data-rename-start]').forEach((b) => b.addEventListener('click', () => {
            editingCategory = categoryRows[Number(b.dataset.renameStart)].name;
            renderCategories();
        }));
        categoriesRoot.querySelectorAll('[data-delete]').forEach((b) => b.addEventListener('click', () => deleteCategory(categoryRows[Number(b.dataset.delete)])));
        const cancel = categoriesRoot.querySelector('[data-rename-cancel]');
        if (cancel) cancel.addEventListener('click', () => { editingCategory = null; renderCategories(); });
        const rename = categoriesRoot.querySelector('form[data-rename]');
        if (rename) rename.addEventListener('submit', (e) => {
            e.preventDefault();
            confirmCategory({ method: 'PUT', url: `${urls.categories}/${encodeURIComponent(editingCategory)}`, before: editingCategory, name: e.target.elements.name.value, message: '名称を変更しました。' });
        });
        categoriesRoot.querySelector('form[data-add]').addEventListener('submit', (e) => {
            e.preventDefault();
            confirmCategory({ method: 'POST', url: urls.categories, name: e.target.elements.name.value, message: '追加しました。' });
        });
    }

    // 種類の変更結果を、スキル項目管理・案件登録の表示にも反映する。
    async function applyCategories(result, message) {
        if (!result) return;
        categoryRows = result;
        editingCategory = null;
        await refreshMaster();
        renderCategories();
        showMessage(message);
    }

    // 追加・名称変更は、確認画面で承認した場合のみ保存する。
    function confirmCategory({ method, url, before, name, message }) {
        showMessage('');
        renderConfirmScreen(categoriesRoot, {
            title: before === undefined ? '種類の追加' : '種類の名称変更',
            saveLabel: before === undefined ? '追加' : '更新',
            rows: [['種類名', name]],
            before: before === undefined ? undefined : [before],
            onBack: renderCategories,
            onSave: async () => {
                await applyCategories(await guarded(() => api(method, url, { name })), message);
            },
        });
    }

    async function moveCategory(index, direction) {
        const order = categoryRows.map((c) => c.name);
        const target = index + direction;
        [order[index], order[target]] = [order[target], order[index]];
        await applyCategories(await guarded(() => api('POST', urls.categoryOrder, { categories: order })), '並び順を保存しました。');
    }

    async function deleteCategory(category) {
        if (!window.confirm(`「${category.name}」を削除します。よろしいですか？`)) return;
        await applyCategories(await guarded(() => api('DELETE', `${urls.categories}/${encodeURIComponent(category.name)}`)), '削除しました。');
    }

    async function loadCategories() {
        const data = await guarded(() => api('GET', urls.categories));
        if (data) {
            categoryRows = data;
            editingCategory = null;
            renderCategories();
        }
    }

    // 資格・実績・サイト情報は、それぞれ別のタブで管理する。表示順は入力せず、サーバー側で自動的に並べる。
    const certificationsRoot = document.getElementById('tab-certifications');
    const worksRoot = document.getElementById('tab-works');
    const siteRoot = document.getElementById('tab-site');

    const certificationsPanel = crudPanel(certificationsRoot, {
        key: 'cert',
        title: '資格',
        separateEdit: true,
        url: urls.certifications,
        idKey: 'certification_id',
        label: (row) => row.name,
        columns: [
            { label: '資格名', value: (r) => r.name },
            { label: '取得年月', value: (r) => formatYearMonth(r.acquired_on) },
            { label: '発行団体', value: (r) => r.org },
        ],
        fields: [
            { name: 'name', label: '資格名' },
            { name: 'acquired_on', label: '取得年月', type: 'month', format: formatYearMonth },
            { name: 'org', label: '発行団体' },
        ],
    });
    const worksPanel = crudPanel(worksRoot, {
        key: 'work',
        title: '実績',
        separateEdit: true,
        url: urls.works,
        idKey: 'work_id',
        label: (row) => row.title,
        columns: [
            { label: 'タイトル', value: (r) => r.title },
            { label: '実績年月', value: (r) => formatYearMonth(r.achieved_on) },
            { label: '使用技術', value: (r) => r.tags.join(', ') },
        ],
        fields: [
            { name: 'title', label: 'タイトル' },
            { name: 'achieved_on', label: '実績年月', type: 'month', format: formatYearMonth },
            { name: 'desc_ja', label: '説明文（日本語）', type: 'textarea' },
            { name: 'desc_en', label: '説明文（英語）', type: 'textarea' },
            { name: 'tags', label: '使用技術タグ（カンマ区切り）', type: 'tags' },
            { name: 'thumbnail', label: 'サムネイル画像', type: 'image', format: (v) => (v ? v.split('/').pop() : '') },
            { name: 'github_url', label: 'GitHub URL', type: 'url' },
            { name: 'live_url', label: '公開 URL', type: 'url' },
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
            return `<label class="wide">${esc(field.label)}<textarea name="${field.name}" rows="4">${esc(value)}</textarea></label>`;
        }
        if (field.type === 'lines') {
            return `<label class="wide">${esc(field.label)}<textarea name="${field.name}" rows="4">${esc((value || []).join('\n'))}</textarea></label>`;
        }
        return `<label>${esc(field.label)}<input type="${field.type || 'text'}" name="${field.name}" value="${esc(value)}" /></label>`;
    }

    // 表示 → 編集 → 確認の順に画面を遷移する。確認画面では変更のあった項目のみ修正前後を表示する。
    let siteCurrent = null; // サーバーに保存されている現在の内容

    function siteRows(values) {
        return SITE_FIELDS.map((f) => [f.label, values[f.name]]);
    }

    function renderSiteView() {
        siteRoot.innerHTML = `
            ${pageHead('サイト情報', { sub: 'ポートフォリオサイトに表示する氏名・自己紹介・リンクなどです。', actions: '<button type="button" class="primary" data-site-edit>編集</button>' })}
            <div class="card">
                <div class="table-wrap"><table class="kv">
                    ${siteRows(siteCurrent).map(([label, value]) => `<tr><th scope="row">${esc(label)}</th><td class="pre-line">${esc(confirmValue(value))}</td></tr>`).join('')}
                </table></div>
            </div>`;
        siteRoot.querySelector('[data-site-edit]').addEventListener('click', () => renderSiteForm(siteCurrent));
    }

    // 入力に戻る場合は入力途中の内容をフォームへ再表示する。
    function renderSiteForm(values) {
        siteRoot.innerHTML = `
            ${pageHead('サイト情報を編集', { back: 'data-site-cancel' })}
            <form class="card">
                <div class="form-grid">
                    ${SITE_FIELDS.map((f) => renderSiteField(f, values[f.name])).join('')}
                </div>
                <div class="form-bar">
                    <button type="submit" class="primary">確認へ</button>
                    <button type="button" data-site-cancel>キャンセル</button>
                </div>
            </form>`;
        siteRoot.querySelectorAll('[data-site-cancel]').forEach((b) => b.addEventListener('click', renderSiteView));
        siteRoot.querySelector('form').addEventListener('submit', (event) => {
            event.preventDefault();
            const payload = {};
            SITE_FIELDS.forEach((f) => {
                const value = event.target.elements[f.name].value;
                payload[f.name] = f.type === 'lines' ? value.split('\n').map((t) => t.trim()).filter(Boolean) : value;
            });
            showMessage('');
            renderSiteConfirm(payload);
        });
        window.scrollTo({ top: 0 });
    }

    function renderSiteConfirm(payload) {
        renderConfirmScreen(siteRoot, {
            title: 'サイト情報',
            saveLabel: '更新',
            rows: siteRows(payload),
            before: siteRows(siteCurrent).map(([, value]) => value),
            onBack: () => renderSiteForm(payload),
            onSave: async () => {
                const saved = await guarded(() => api('PUT', urls.site, payload));
                if (!saved) return;
                siteCurrent = saved;
                renderSiteView();
                showMessage('保存しました。');
            },
        });
    }

    async function loadSiteInfo() {
        const data = await guarded(() => api('GET', urls.site));
        if (data) {
            siteCurrent = data;
            renderSiteView();
        }
    }

    // --- 職務経歴書 ---

    // 行単位の差分（最長共通部分列）。修正前・修正後の各行に追加・削除の印を付けて返す。
    function lineDiff(before, after) {
        const a = before.split('\n');
        const b = after.split('\n');
        const lcs = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
        for (let i = a.length - 1; i >= 0; i--) {
            for (let j = b.length - 1; j >= 0; j--) {
                lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
            }
        }
        const result = [];
        let i = 0;
        let j = 0;
        while (i < a.length && j < b.length) {
            if (a[i] === b[j]) {
                result.push({ kind: 'same', text: a[i] });
                i++; j++;
            } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
                result.push({ kind: 'del', text: a[i++] });
            } else {
                result.push({ kind: 'add', text: b[j++] });
            }
        }
        while (i < a.length) result.push({ kind: 'del', text: a[i++] });
        while (j < b.length) result.push({ kind: 'add', text: b[j++] });
        return result;
    }

    function renderDiff(before, after) {
        const lines = lineDiff(before, after);
        if (lines.every((l) => l.kind === 'same')) return '<p class="empty">変更された箇所はありません。</p>';
        const mark = { same: ' ', add: '+', del: '-' };
        return `<pre class="diff">${lines.map((l) => `<span class="diff-${l.kind}">${mark[l.kind]} ${esc(l.text)}</span>`).join('\n')}</pre>`;
    }

    async function loadSkillsheet() {
        const root = document.getElementById('tab-skillsheet');
        const data = await guarded(() => api('GET', urls.skillsheet));
        if (!data) return;
        renderSkillsheetView(root, data);
    }

    function renderSkillsheetView(root, data) {
        const warnings = [];
        if (data.warnings) {
            if (data.warnings.unmatched_projects.length > 0) {
                warnings.push(`本文に案件見出しが見つからない案件があります: ${data.warnings.unmatched_projects.join('、')}`);
            }
            if (data.warnings.unused_skill_count > 0) {
                warnings.push(`使用実績がなく出力対象外のスキル項目: ${data.warnings.unused_skill_count}件`);
            }
        }
        const updated = data.updated_at ? new Date(data.updated_at).toLocaleString('ja-JP') : '未登録';
        const canDownload = data.preview_html !== null;
        root.innerHTML = `
            ${pageHead('職務経歴書', {
        sub: `本文の最終更新日時: ${updated}`,
        actions: `<button type="button" id="edit-skillsheet">編集</button>
                  ${data.updated_at ? `<a href="${esc(urls.skillsheetMarkdown)}" download><button type="button">本文をダウンロード</button></a>` : ''}
                  ${canDownload ? `<a href="${esc(urls.skillsheetPdf)}" download><button type="button" class="primary">PDF をダウンロード</button></a>` : ''}`,
    })}
            ${data.error ? `<p class="message warning skillsheet-error pre-line">${esc(data.error)}</p>` : ''}
            ${warnings.map((w) => `<p class="message warning">${esc(w)}</p>`).join('')}
            ${canDownload ? `<div class="card"><h3>プレビュー</h3><iframe id="skillsheet-preview" class="skillsheet-preview" title="職務経歴書のプレビュー"></iframe></div>` : ''}`;
        if (canDownload) root.querySelector('#skillsheet-preview').srcdoc = data.preview_html;
        root.querySelector('#edit-skillsheet').addEventListener('click', () => renderSkillsheetEdit(root, data, data.body));
    }

    function renderSkillsheetEdit(root, data, draft) {
        root.innerHTML = `
            ${pageHead('職務経歴書の編集', { sub: '本文を Markdown で編集します。「確認へ」で変更内容を確認してから保存します。' })}
            <div class="card">
                <textarea id="skillsheet-body" class="skillsheet-body" spellcheck="false"></textarea>
                <div class="form-bar">
                    <button type="button" data-cancel>キャンセル</button>
                    <button type="button" class="primary" data-confirm>確認へ</button>
                </div>
            </div>`;
        const textarea = root.querySelector('#skillsheet-body');
        textarea.value = draft;
        root.querySelector('[data-cancel]').addEventListener('click', () => renderSkillsheetView(root, data));
        root.querySelector('[data-confirm]').addEventListener('click', () => {
            if (!textarea.value.trim()) {
                showMessage('本文を入力してください。', 'error');
                return;
            }
            renderSkillsheetConfirm(root, data, textarea.value);
        });
        window.scrollTo({ top: 0 });
    }

    function renderSkillsheetConfirm(root, data, draft) {
        root.innerHTML = `
            ${pageHead('職務経歴書の確認', { sub: '変更内容（行単位の差分）を確認して「保存」を押すと保存します。' })}
            <div class="card">
                ${renderDiff(data.body, draft)}
                <div class="form-bar">
                    <button type="button" data-back>入力に戻る</button>
                    <button type="button" class="primary" data-save>保存</button>
                </div>
            </div>`;
        root.querySelector('[data-back]').addEventListener('click', () => renderSkillsheetEdit(root, data, draft));
        root.querySelector('[data-save]').addEventListener('click', async () => {
            const saved = await guarded(() => api('PUT', urls.skillsheet, { body: draft, expected_updated_at: data.updated_at }));
            if (!saved) return;
            renderSkillsheetView(root, saved);
            showMessage('保存しました。');
        });
        window.scrollTo({ top: 0 });
    }

    // --- タブ切り替え ---

    const tabLoaders = {
        project: () => loadProjectTab(project.state === null),
        skills: async () => {
            if (project.skills.length === 0) await refreshMaster();
            await skillsPanel.load();
        },
        certifications: () => certificationsPanel.load(),
        works: () => worksPanel.load(),
        site: loadSiteInfo,
        skillsheet: loadSkillsheet,
        categories: loadCategories,
    };

    // 狭い画面でのサイドバー開閉。画面を選択したら閉じる。
    const navToggle = document.getElementById('nav-toggle');
    function setNavOpen(open) {
        document.body.classList.toggle('nav-open', open);
        navToggle.setAttribute('aria-expanded', String(open));
    }
    navToggle.addEventListener('click', () => setNavOpen(!document.body.classList.contains('nav-open')));

    async function showTab(name) {
        document.querySelectorAll('#main-tabs button').forEach((b) => {
            const selected = b.dataset.tab === name;
            b.setAttribute('aria-selected', String(selected));
            if (selected) {
                document.getElementById('current-page').textContent = b.textContent;
            }
        });
        setNavOpen(false);
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
