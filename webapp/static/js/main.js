document.addEventListener('DOMContentLoaded', () => {

    // --- State ---
    const currentLang = 'ja';

    // --- DOM Elements ---
    const typingText = document.getElementById('typing-text');
    const header = document.querySelector('header');

    // 静的ファイルの配信パスと API の URL は、テンプレートが body の data 属性で渡す。
    const staticBase = document.body.dataset.staticBase;
    const mediaBase = document.body.dataset.mediaBase;
    const api = {
        skills: document.body.dataset.apiSkills,
        certifications: document.body.dataset.apiCertifications,
        works: document.body.dataset.apiWorks,
        site: document.body.dataset.apiSite,
    };

    // --- Initialization ---
    applyLang();
    loadAndRender(api.site, 'site-error', renderSite);
    loadAndRender(api.skills, 'skills-container', (data) => renderSkills(data.skills));
    loadAndRender(api.certifications, 'certifications-container', renderCertifications);
    loadAndRender(api.works, 'works-container', renderWorks);

    // --- Event Listeners ---

    window.addEventListener('scroll', () => {
        header.classList.toggle('scrolled', window.scrollY > 50);
    });

    // モバイル用メニューの開閉。リンク選択時は閉じる。
    const menuButton = document.getElementById('mobile-menu-btn');
    const navLinks = document.getElementById('nav-links');

    function setMenuOpen(open) {
        header.classList.toggle('menu-open', open);
        menuButton.setAttribute('aria-expanded', String(open));
        menuButton.setAttribute('aria-label', open ? 'メニューを閉じる' : 'メニューを開く');
    }

    menuButton.addEventListener('click', () => {
        setMenuOpen(menuButton.getAttribute('aria-expanded') !== 'true');
    });
    navLinks.addEventListener('click', (event) => {
        if (event.target.closest('a')) setMenuOpen(false);
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') setMenuOpen(false);
    });

    // --- Functions ---

    function loadAndRender(url, containerId, onLoaded) {
        fetch(url)
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(onLoaded)
            .catch((error) => {
                console.error(`表示データの読み込みに失敗しました: ${url}`, error);
                const container = document.getElementById(containerId);
                if (container) {
                    container.innerHTML = '<p class="data-load-error">表示データの読み込みに失敗しました。</p>';
                }
            });
    }

    // サムネイルはアップロード画像の相対パスで保持しているため、画像の配信パスを前置する。
    // 未設定の場合は既定のプレースホルダー（静的ファイル）を表示する。
    function resolveThumbnail(path) {
        if (!path) return staticBase + 'img/placeholder.png';
        return /^(https?:)?\/\//.test(path) ? path : mediaBase + path;
    }

    function applyLang() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.dataset.i18n;
            const keys = key.split('.');
            let val = resources[currentLang];
            keys.forEach(k => { if(val) val = val[k]; });
            if (val) el.innerHTML = val.replace(/\n/g, '<br>');
        });
    }

    // 改行を含む文言を、HTML として解釈させずに <br> 区切りで描画する。
    function setMultiline(el, text) {
        el.replaceChildren();
        text.split('\n').forEach((line, index) => {
            if (index > 0) el.appendChild(document.createElement('br'));
            el.appendChild(document.createTextNode(line));
        });
    }

    function renderSite(site) {
        document.getElementById('site-name').textContent = site.name;
        document.getElementById('site-catchphrase').textContent = site.catchphrase;
        setMultiline(document.getElementById('about-intro'), site.intro);
        document.getElementById('age-display').textContent = site.age;
        document.getElementById('about-job').textContent = site.job;
        document.getElementById('about-education').textContent = site.education;
        document.getElementById('about-location').textContent = site.location;
        document.getElementById('about-hobby').textContent = site.hobby;
        const aboutGithub = document.getElementById('about-github');
        aboutGithub.href = site.github_url;
        aboutGithub.textContent = site.github_url;
        setMultiline(document.getElementById('contact-message'), site.contact_message);
        document.getElementById('contact-button').href = site.contact_form_url;
        document.getElementById('contact-github').href = site.github_url;
        document.getElementById('footer-copyright').textContent = site.copyright;
        document.getElementById('footer-name').textContent = site.name;
        startTyping(site.typing_titles);
    }

    // 表示データを HTML 文字列へ埋め込む際のエスケープ。
    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[ch]));
    }

    // 星の数（1〜5）を、5 段階のレベルメーターとして描画する。
    function levelMeter(stars) {
        const pips = [1, 2, 3, 4, 5]
            .map((i) => `<i class="${i <= stars ? 'on' : ''}"></i>`)
            .join('');
        return `<span class="skill-level" role="img" aria-label="レベル ${stars} / 5">${pips}</span>`;
    }

    function renderSkills(skillsData) {
        const container = document.getElementById('skills-container');
        const r = resources[currentLang].nav;

        // 凡例（経験年数の目安）。i18n の凡例文言「★★★☆☆: 1年以上3年未満」を、メーターと目安に分けて表示する。
        const legendItems = Object.values(r.skill_legend).map((text) => {
            const [starsPart, label] = text.split(': ');
            const stars = (starsPart.match(/★/g) || []).length;
            return `<span class="skill-legend-item">${levelMeter(stars)}${escapeHtml(label)}</span>`;
        }).join('');

        // カテゴリ単位にグルーピングする。
        const groups = {};
        skillsData.forEach((skill) => {
            if (!groups[skill.category]) groups[skill.category] = [];
            groups[skill.category].push(skill);
        });

        const categoriesHtml = Object.keys(groups).map((category) => {
            const rows = groups[category].map((skill) => `
                <div class="skill-row">
                    <span class="skill-name">${escapeHtml(skill.name)}</span>
                    <span class="skill-years">${escapeHtml(skill.years)}</span>
                    ${levelMeter(skill.stars)}
                </div>`).join('');
            return `
                <section class="skill-category">
                    <h3 class="skill-category-title">${escapeHtml(category)}</h3>
                    <div class="skill-row skill-row-head">
                        <span>${r.skill_tech}</span>
                        <span>${r.skill_years}</span>
                        <span>${r.skill_level}</span>
                    </div>
                    ${rows}
                </section>`;
        }).join('');

        container.innerHTML = `<div class="skill-legend">${legendItems}</div>${categoriesHtml}`;
    }

    function renderCertifications(certificationsData) {
        const container = document.getElementById('certifications-container');
        container.innerHTML = certificationsData.map((cert) => `
            <div class="cert-item">
                <div>
                    <div class="cert-name">${escapeHtml(cert.name)}</div>
                    <div class="cert-org">${escapeHtml(cert.org)}</div>
                </div>
                <div class="cert-date">${escapeHtml(cert.date)}</div>
            </div>`).join('');
    }

    function renderWorks(worksData) {
        const container = document.getElementById('works-container');
        const r = resources[currentLang].nav;
        container.innerHTML = '';

        worksData.forEach((work) => {
            const desc = currentLang === 'ja' ? work.desc_ja : work.desc_en;
            const thumb = escapeHtml(resolveThumbnail(work.thumbnail));
            const liveLink = work.live_url
                ? `<a href="${escapeHtml(work.live_url)}" target="_blank" rel="noopener">${r.view_live}</a>` : '';
            const githubLink = work.github_url
                ? `<a href="${escapeHtml(work.github_url)}" target="_blank" rel="noopener">${r.view_github}</a>` : '';

            const el = document.createElement('article');
            el.className = 'work-card';
            el.innerHTML = `
                <div class="work-img" style="--thumb-url: url('${thumb}');">
                    <img src="${thumb}" alt="${escapeHtml(work.title)}" loading="lazy">
                </div>
                <div class="work-content">
                    <h3 class="work-title">${escapeHtml(work.title)}</h3>
                    ${work.date ? `<div class="work-date">${escapeHtml(work.date)}</div>` : ''}
                    <p class="work-desc">${escapeHtml(desc)}</p>
                    <div class="work-tags">
                        ${work.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                    </div>
                    <div class="work-links">${liveLink}${githubLink}</div>
                </div>`;
            container.appendChild(el);
        });
    }

    function startTyping(texts) {
        // 動きを減らす設定の場合は、最初の肩書きを固定表示する。
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            typingText.textContent = texts[0];
            return;
        }

        let textIndex = 0;
        let charIndex = 0;
        let isDeleting = false;

        const type = () => {
            const currentText = texts[textIndex];

            if (isDeleting) {
                typingText.textContent = currentText.substring(0, charIndex - 1);
                charIndex--;
            } else {
                typingText.textContent = currentText.substring(0, charIndex + 1);
                charIndex++;
            }

            let typeSpeed = 100;
            if (isDeleting) typeSpeed /= 2;

            if (!isDeleting && charIndex === currentText.length) {
                isDeleting = true;
                typeSpeed = 2000; // Pause at end
            } else if (isDeleting && charIndex === 0) {
                isDeleting = false;
                textIndex = (textIndex + 1) % texts.length;
                typeSpeed = 500;
            }

            setTimeout(type, typeSpeed);
        };

        type();
    }
});
