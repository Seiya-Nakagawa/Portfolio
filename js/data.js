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
    { name: "Python", years: "1年", level: 3, category: "言語" },

    // フレームワーク
    { name: "Laravel", years: "1年未満", level: 2, category: "フレームワーク" },
    { name: "Spring Boot", years: "2年", level: 2, category: "フレームワーク" },
    { name: "Next.js", years: "1年未満", level: 1, category: "フレームワーク" },

    // DB
    { name: "Oracle DB", years: "1年", level: 2, category: "DB" },
    { name: "MySQL", years: "3年", level: 2, category: "DB" },

    // パブリッククラウド
    { name: "AWS", years: "5年", level: 5, category: "パブリッククラウド" },
    { name: "Google Cloud", years: "1年未満", level: 3, category: "パブリッククラウド" },
    { name: "Oracle Cloud Infrastructure", years: "1年未満", level: 2, category: "パブリッククラウド" },

    // ジョブ管理
    { name: "JP1/Base", years: "3年", level: 3, category: "ジョブ管理" },
    { name: "JP1/AJS", years: "3年", level: 2, category: "ジョブ管理" },
    { name: "LoadStar Scheduler", years: "1年未満", level: 2, category: "ジョブ管理" },

    // 監視
    { name: "Zabbix", years: "1年", level: 2, category: "監視" },
    { name: "JP1 Integrated Management", years: "1年", level: 3, category: "監視" },
    { name: "ESB File Transfer", years: "1年未満", level: 2, category: "監視" },
    { name: "CloudWatch", years: "4年", level: 2, category: "監視" },

    // ログ分析
    { name: "ELK Stack", years: "1年未満", level: 2, category: "ログ分析" },

    // IaC
    { name: "Terraform", years: "3年", level: 4, category: "IaC" },
    { name: "CloudFormation (Sceptre)", years: "1年未満", level: 4, category: "IaC" },
    { name: "Ansible", years: "1年未満", level: 2, category: "IaC" },

    // コンテナ
    { name: "Docker", years: "1年", level: 2, category: "コンテナ" },
    { name: "ECS (Fargate)", years: "1年", level: 3, category: "コンテナ" },
    { name: "EKS(Kubernetes)", years: "1年未満", level: 1, category: "コンテナ" },

    // CI/CD
    { name: "GitHub Actions", years: "3年", level: 4, category: "CI/CD" },
    { name: "GitLab Runner", years: "1年", level: 3, category: "CI/CD" },
    { name: "CodeBuild", years: "1年", level: 2, category: "CI/CD" },
    { name: "CodeDeploy", years: "2年", level: 3, category: "CI/CD" },

    // クラスタリング
    { name: "CLUSTERPRO", years: "1年未満", level: 2, category: "クラスタリング" }
];

const worksData = [
    {
        title: "Portfolio",
        desc_ja: "当ポートフォリオサイト",
        desc_en: "Renewal project of this portfolio website.",
        tags: ["HTML", "CSS", "JS"],
        thumbnail: "img/portfolio.png",
        github_url: "https://github.com/Seiya-Nakagawa/Portfolio"
    },
    {
        title: "Blog Link Checker",
        desc_ja: "ブログ記事内のリンク切れを自動でチェック。GASとAWS（Lambda, S3）を連携。",
        desc_en: "Automated broken link checker for blogs. Integrates GAS with AWS Lambda and S3.",
        tags: ["GAS", "AWS", "Terraform"],
        thumbnail: "img/blog_link_checker.jpg",
        github_url: "https://github.com/Seiya-Nakagawa/blog_link_checker"
    },
    {
        title: "Train Delay Alert",
        desc_ja: "登録した路線の情報をLINEで受け取れる遅延通知システム。",
        desc_en: "Train delay notification system using LINE Messaging API and AWS.",
        tags: ["Python", "AWS", "Line API", "Terraform"],
        thumbnail: "img/train_delay_alert.jpg",
        github_url: "https://github.com/Seiya-Nakagawa/train_delay_alert"
    }
];
const certificationsData = [
    {
        name: "Google Cloud Certified - Associate Cloud Engineer",
        date: "Jul 2025",
        org: "Google Cloud"
    },
    {
        name: "AWS Certified Solutions Architect – Professional",
        date: "Jul 2024",
        org: "Amazon Web Services (AWS)"
    },
    {
        name: "LinuC LEVEL2",
        date: "Sep 2020",
        org: "LPI-Japan"
    },
    {
        name: "AWS Certified Solutions Architect – Associate",
        date: "Sep 2020",
        org: "Amazon Web Services (AWS)"
    },
    {
        name: "Oracle Master Bronze 12c",
        date: "Jul 2018",
        org: "Oracle"
    },
    {
        name: "LinuC LEVEL1",
        date: "Feb 2018",
        org: "LPI-Japan"
    }
];
