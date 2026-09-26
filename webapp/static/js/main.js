document.addEventListener('DOMContentLoaded', () => {

    // --- State ---
    const currentLang = 'ja';

    // --- DOM Elements ---
    const typingText = document.getElementById('typing-text');
    const header = document.querySelector('header');

    // 静的ファイルの配信パスと API の URL は、テンプレートが body の data 属性で渡す。
    const staticBase = document.body.dataset.staticBase;
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
    initScrollEffects();

    // --- Event Listeners ---
    // --- Event Listeners ---

    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
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

    // サムネイルのパスは静的ファイルの相対パスで保持しているため、配信パスを前置する。
    function resolveThumbnail(path) {
        const thumbnail = path || 'img/placeholder.png';
        return /^(https?:)?\/\//.test(thumbnail) ? thumbnail : staticBase + thumbnail;
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

    function renderSkills(skillsData) {
        const container = document.getElementById('skills-container');
        container.innerHTML = '';
        container.className = 'skills-grid-container'; // Use a class for easier styling if needed, or just inline for now
        container.style.display = 'grid';
        container.style.gridTemplateColumns = 'repeat(auto-fit, minmax(450px, 1fr))';
        container.style.gap = '2rem';
        container.style.alignItems = 'start';

        // 0. Render Legend
        const r = resources[currentLang || 'ja'].nav;
        const legend = document.createElement('div');
        legend.className = 'glass-panel';
        legend.style.padding = '1rem';
        legend.style.marginBottom = '2rem';
        legend.style.fontSize = '0.9rem';
        legend.style.color = 'var(--text-muted)';
        legend.style.gridColumn = '1 / -1'; // Ensure legend takes full row space
        legend.style.width = 'fit-content'; // But don't make the box wider than content
        legend.style.justifySelf = 'center'; // Center the block

        let legendHTML = `<div style="margin-bottom:0.5rem; font-weight:bold;">${r.skill_level_label || 'Skill Level'}</div>`;
        legendHTML += `<div style="display: flex; flex-direction: column; gap: 0.3rem;">`;
        if (r.skill_legend) {
            Object.values(r.skill_legend).forEach(text => {
                legendHTML += `<span>${text}</span>`;
            });
        }
        legendHTML += `</div>`;
        legend.innerHTML = legendHTML;
        container.appendChild(legend);

        // 1. Group by category
        const groups = {};
        skillsData.forEach(skill => {
            if (!groups[skill.category]) groups[skill.category] = [];
            groups[skill.category].push(skill);
        });

        // 2. Render each group
        Object.keys(groups).forEach(category => {
            const groupSection = document.createElement('div');
            groupSection.className = 'skill-category-section glass-panel';
            groupSection.style.marginBottom = '2rem';
            groupSection.style.padding = '2rem';

            // Category Title
            const title = document.createElement('h3');
            title.textContent = category;
            title.style.color = 'var(--primary)';
            title.style.marginBottom = '1.5rem';
            title.style.borderLeft = '4px solid var(--primary)';
            title.style.paddingLeft = '1rem';
            groupSection.appendChild(title);

            // Table Header
            const headerRow = document.createElement('div');
            headerRow.style.display = 'grid';
            headerRow.style.gridTemplateColumns = '2fr 1fr 2fr';
            headerRow.style.paddingBottom = '1rem';
            headerRow.style.borderBottom = '1px solid rgba(255,255,255,0.1)';
            headerRow.style.marginBottom = '1rem';
            headerRow.style.fontWeight = 'bold';
            headerRow.style.color = 'var(--text-muted)';

            // Get current headers from i18n resources directly for simplicity (or pass them in)
            // Ideally we use a data-i18n, but for dynamic content updates, let's grab from resources global
            const r = resources[currentLang || 'ja'].nav;

            headerRow.innerHTML = `
                <div>${r.skill_tech || 'Technology'}</div>
                <div style="text-align: center;">${r.skill_years || 'Years'}</div>
                <div style="text-align: center;">${r.skill_level || 'Skill'}</div>
            `;
            groupSection.appendChild(headerRow);

            // Skill Items
            groups[category].forEach(skill => {
                const row = document.createElement('div');
                row.style.display = 'grid';
                row.style.gridTemplateColumns = '2fr 1fr 2fr';
                row.style.padding = '1rem 0';
                row.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                row.style.alignItems = 'center';

                // Stars generation
                let stars = '';
                for (let i = 1; i <= 5; i++) {
                    const color = i <= skill.stars ? 'gold' : 'var(--text-muted)';
                    const iconClass = i <= skill.stars ? 'fas' : 'far';
                    stars += `<i class="${iconClass} fa-star" style="color: ${color}; margin-right: 2px;"></i>`;
                }

                row.innerHTML = `
                    <div style="font-weight: bold;">${skill.name}</div>
                    <div style="text-align: center;">${skill.years}</div>
                    <div style="text-align: center; white-space: nowrap;">
                        ${stars}
                    </div>
                `;
                groupSection.appendChild(row);
            });

            container.appendChild(groupSection);
        });

        // Simple fade in
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = 1;
                    entry.target.style.transform = 'translateY(0)';
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        document.querySelectorAll('.skill-category-section').forEach(item => {
            item.style.opacity = 0;
            item.style.transform = 'translateY(20px)';
            item.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
            observer.observe(item);
        });
    }

    function renderCertifications(certificationsData) {
        const container = document.getElementById('certifications-container');
        if (!container) return;
        container.innerHTML = '';

        const listWrapper = document.createElement('div');
        listWrapper.className = 'glass-panel';
        listWrapper.style.padding = '2rem';
        listWrapper.style.maxWidth = '800px';
        listWrapper.style.margin = '0 auto';

        certificationsData.forEach((cert, index) => {
            const item = document.createElement('div');
            item.className = 'cert-item';
            item.style.display = 'flex';
            item.style.justifyContent = 'space-between';
            item.style.alignItems = 'center';
            item.style.padding = '1.2rem 0';
            if (index !== certificationsData.length - 1) {
                item.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
            }

            item.innerHTML = `
                <div style="display: flex; align-items: center; gap: 1.5rem;">
                    <div class="cert-icon" style="color: var(--primary); font-size: 1.5rem;">
                        <i class="fas fa-certificate"></i>
                    </div>
                    <div>
                        <div style="font-weight: 700; color: var(--text-main); font-size: 1.1rem; margin-bottom: 0.2rem;">${cert.name}</div>
                        <div style="font-size: 0.85rem; color: var(--text-muted); opacity: 0.8;">${cert.org}</div>
                    </div>
                </div>
                <div style="background: rgba(6, 182, 212, 0.1); color: var(--primary); padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.9rem; font-weight: 600;">
                    ${cert.date}
                </div>
            `;
            listWrapper.appendChild(item);
        });

        container.appendChild(listWrapper);

        // Simple fade in
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = 1;
                    entry.target.style.transform = 'translateY(0)';
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        listWrapper.style.opacity = 0;
        listWrapper.style.transform = 'translateY(20px)';
        listWrapper.style.transition = 'opacity 0.8s ease, transform 0.8s ease';
        observer.observe(listWrapper);
    }


    function renderWorks(worksData) {
        const container = document.getElementById('works-container');
        container.innerHTML = '';

        worksData.forEach(work => {
            const desc = currentLang === 'ja' ? work.desc_ja : work.desc_en;
            const el = document.createElement('div');
            el.className = 'work-card glass-panel';
            const r = resources[currentLang || 'ja'].nav;
            const liveLink = work.live_url ? `<a href="${work.live_url}" target="_blank" style="font-size: 0.9rem; text-decoration: underline; margin-right: 1.5rem;">${r.view_live} <i class="fas fa-external-link-alt"></i></a>` : '';
            const githubLink = work.github_url ? `<a href="${work.github_url}" target="_blank" style="font-size: 0.9rem; text-decoration: underline;">${r.view_github} <i class="fab fa-github"></i></a>` : '';

            el.innerHTML = `
                <div class="work-img">
                    <img src="${resolveThumbnail(work.thumbnail)}" alt="${work.title}" style="width: 100%; height: 100%; object-fit: cover;">
                </div>
                <div class="work-content">
                    <h3>${work.title}</h3>
                    <p style="font-size: 0.9rem; color: var(--text-muted); margin: 0.5rem 0;">${desc}</p>
                    <div class="work-tags">
                        ${work.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                    </div>
                    <div class="work-links">
                        ${liveLink}
                        ${githubLink}
                    </div>
                </div>
            `;
            container.appendChild(el);
        });
    }

    function startTyping(texts) {
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

    function initScrollEffects() {
        // Optional: Reveal animations on scroll
        const obs = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = 1;
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        });
    }

    // --- Contact Form Event ---
    // Removed: Contact is now handled via Google Forms link in index.html
});
