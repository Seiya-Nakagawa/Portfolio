document.addEventListener('DOMContentLoaded', () => {

    // --- State ---
    let currentLang = localStorage.getItem('lang') || 'ja';
    let isLightMode = localStorage.getItem('theme') === 'light';

    // --- DOM Elements ---
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = themeToggle.querySelector('i');
    const langToggle = document.getElementById('lang-toggle');
    const langText = langToggle.querySelector('span');
    const typingText = document.getElementById('typing-text');
    const ageDisplay = document.getElementById('age-display');
    const header = document.querySelector('header');

    // --- Initialization ---
    applyTheme();
    applyLang();
    calculateAge();
    renderSkills();
    renderWorks();
    startTyping();
    initScrollEffects();

    // --- Event Listeners ---
    themeToggle.addEventListener('click', () => {
        isLightMode = !isLightMode;
        localStorage.setItem('theme', isLightMode ? 'light' : 'dark');
        applyTheme();
    });

    langToggle.addEventListener('click', () => {
        currentLang = currentLang === 'ja' ? 'en' : 'ja';
        localStorage.setItem('lang', currentLang);
        applyLang();
        renderWorks(); // Re-render works to update language
    });

    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });

    // --- Functions ---

    function applyTheme() {
        if (isLightMode) {
            document.body.classList.add('light-mode');
            themeIcon.className = 'fas fa-sun';
        } else {
            document.body.classList.remove('light-mode');
            themeIcon.className = 'fas fa-moon';
        }
    }

    function applyLang() {
        langText.textContent = currentLang === 'ja' ? 'JP' : 'EN';
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.dataset.i18n;
            const keys = key.split('.');
            let val = resources[currentLang];
            keys.forEach(k => { if(val) val = val[k]; });
            if (val) el.textContent = val;
        });
    }

    function calculateAge() {
        const birthday = new Date('1988-09-01'); // User birthday: 1988/09 (37yo in Feb 2026)
        // If birthday is not provided in requirements, use a default or ask user.
        // Based on "Age: Auto-calc" requirement, I need a birthdate.
        // I will use a placeholder or 1998 if not known (26-27yo).
        // Let's use 1998-04-18 for now as example or leave it generic if date unknown.
        // Actually, I should check requirements. It says "Auto calculation" but no date.
        // I'll stick to 1998 as a placeholder logic.
        const today = new Date();
        let age = today.getFullYear() - birthday.getFullYear();
        const m = today.getMonth() - birthday.getMonth();
        if (m < 0 || (m === 0 && today.getDate() < birthday.getDate())) {
            age--;
        }
        ageDisplay.textContent = age;
    }

    function renderSkills() {
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
                    const color = i <= skill.level ? 'gold' : 'var(--text-muted)';
                    const iconClass = i <= skill.level ? 'fas' : 'far';
                    stars += `<i class="${iconClass} fa-star" style="color: ${color}; margin-right: 2px;"></i>`;
                }

                const yearsDisplay = typeof skill.years === 'number'
                    ? (currentLang === 'ja' ? `${skill.years}年` : `${skill.years} Years`)
                    : skill.years;

                row.innerHTML = `
                    <div style="font-weight: bold;">${skill.name}</div>
                    <div style="text-align: center;">${yearsDisplay}</div>
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

    function renderWorks() {
        const container = document.getElementById('works-container');
        container.innerHTML = '';

        worksData.forEach(work => {
            const desc = currentLang === 'ja' ? work.desc_ja : work.desc_en;
            const el = document.createElement('div');
            el.className = 'work-card glass-panel';
            el.innerHTML = `
                <div class="work-img">
                    <!-- Image placeholder -->
                </div>
                <div class="work-content">
                    <h3>${work.title}</h3>
                    <p style="font-size: 0.9rem; color: var(--text-muted); margin: 0.5rem 0;">${desc}</p>
                    <div class="work-tags">
                        ${work.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                    </div>
                    <a href="${work.link}" target="_blank" style="font-size: 0.9rem; text-decoration: underline;">View Project <i class="fas fa-external-link-alt"></i></a>
                </div>
            `;
            container.appendChild(el);
        });
    }

    function startTyping() {
        const texts = ["Cloud Architect Engineer", "Full Stack Engineer", "Problem Solver"];
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

        // We can add .reveal class to sections later if wanted
    }
});
