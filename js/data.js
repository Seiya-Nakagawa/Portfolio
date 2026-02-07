const skillsData = [
    // OS
    { name: "Windows", years: "1年", level: 2, category: "OS" },
    { name: "Linux", years: "11年", level: 3, category: "OS" },

    // 言語
    { name: "HTML＆CSS", years: "2年", level: 3, category: "言語" },
    { name: "JavaScript", years: "1年", level: 2, category: "言語" },
    { name: "Java", years: "1年", level: 2, category: "言語" },
    { name: "SQL", years: "1年", level: 3, category: "言語" },
    { name: "B_Shell", years: "8年", level: 3, category: "言語" },
    { name: "PHP", years: "1年", level: 2, category: "言語" },
    { name: "Python", years: "-", level: 3, category: "言語" },

    // フレームワーク
    { name: "Laravel", years: "10か月", level: 2, category: "フレームワーク" },
    { name: "Spring Boot", years: "2年", level: 2, category: "フレームワーク" },
    { name: "Next.js", years: "1か月", level: 1, category: "フレームワーク" },

    // DB
    { name: "Oracle DB", years: "1年", level: 2, category: "DB" },
    { name: "MySQL", years: "3年", level: 2, category: "DB" },

    // パブリッククラウド
    { name: "AWS", years: "5年", level: 5, category: "パブリッククラウド" },
    { name: "Google Cloud", years: "5ヶ月", level: 3, category: "パブリッククラウド" },
    { name: "Oracle Cloud Infrastructure", years: "6ヶ月", level: 2, category: "パブリッククラウド" },

    // ジョブ管理
    { name: "JP1/Base", years: "3年", level: 3, category: "ジョブ管理" },
    { name: "JP1/AJS", years: "3年", level: 2, category: "ジョブ管理" },
    { name: "LoadStar Scheduler", years: "8ヶ月", level: 2, category: "ジョブ管理" },

    // 監視
    { name: "Zabbix", years: "1年", level: 2, category: "監視" },
    { name: "JP1 Integrated Management", years: "1年", level: 3, category: "監視" },
    { name: "ESB File Transfer", years: "8ヶ月", level: 2, category: "監視" },
    { name: "CloudWatch", years: "-", level: 2, category: "監視" },

    // ログ分析
    { name: "ELK Stack", years: "2ヶ月", level: 2, category: "ログ分析" },

    // IaC
    { name: "Terraform", years: "3年", level: 4, category: "IaC" },
    { name: "CloudFormation (Sceptre)", years: "5ヶ月", level: 4, category: "IaC" },
    { name: "Ansible", years: "1ヶ月", level: 2, category: "IaC" },

    // コンテナ
    { name: "Docker", years: "1年", level: 2, category: "コンテナ" },
    { name: "ECS (Fargate)", years: "1年", level: 3, category: "コンテナ" },
    { name: "Kubernetes", years: "1か月", level: 1, category: "コンテナ" },

    // CI/CD
    { name: "GitHub Actions", years: "3年", level: 4, category: "CI/CD" },
    { name: "GitLab Runner", years: "1年", level: 3, category: "CI/CD" },
    { name: "CodeBuild", years: "1年", level: 2, category: "CI/CD" },
    { name: "CodeDeploy", years: "2年", level: 3, category: "CI/CD" }
];

const worksData = [
    {
        title: "Portfolio",
        desc_ja: "このポートフォリオサイトのリニューアルプロジェクト。",
        desc_en: "Renewal project of this portfolio website.",
        tags: ["HTML", "CSS", "JS"],
        thumbnail: "img/portfolio.png",
        github_url: "https://github.com/Seiya-Nakagawa/Portfolio"
    },
    {
        title: "News Check App",
        desc_ja: "ニュース収集・要約アプリケーション。",
        desc_en: "News collection and summarization application.",
        tags: ["Python", "AWS", "Terraform"],
        thumbnail: "img/news_check.png",
        live_url: "https://technohonesty.com/news",
        github_url: "https://github.com/Seiya-Nakagawa/news_check"
    }
];
