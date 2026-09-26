import re

from django.db import migrations

AWS_CATEGORY = "AWS"

# AWS 公式のサービスカテゴリごとのサービス名（正規化前の表記で列挙する）。
AWS_SERVICE_CATEGORIES = {
    "Compute": [
        "EC2", "Lambda", "ECS", "EKS", "Fargate", "Lightsail", "Batch",
        "Elastic Beanstalk", "App Runner", "Auto Scaling", "EC2 Auto Scaling",
        "Outposts", "Image Builder", "Serverless Application Repository",
    ],
    "Containers": ["ECR", "ECS", "EKS", "Fargate", "App Runner", "Copilot"],
    "Storage": [
        "S3", "EBS", "EFS", "FSx", "Glacier", "S3 Glacier", "Storage Gateway",
        "AWS Backup", "Backup", "Snow Family", "DataSync", "Elastic Disaster Recovery",
    ],
    "Database": [
        "RDS", "Aurora", "DynamoDB", "ElastiCache", "MemoryDB", "DocumentDB",
        "Neptune", "Redshift", "Keyspaces", "Timestream", "QLDB", "DMS",
        "Database Migration Service",
    ],
    "Networking & Content Delivery": [
        "VPC", "CloudFront", "Route 53", "Route53", "ELB", "ALB", "NLB",
        "Elastic Load Balancing", "API Gateway", "Direct Connect", "Transit Gateway",
        "PrivateLink", "Global Accelerator", "Site-to-Site VPN", "VPN",
        "Client VPN", "Cloud Map", "App Mesh", "Network Firewall",
    ],
    "Security, Identity, & Compliance": [
        "IAM", "IAM Identity Center", "SSO", "Cognito", "KMS", "Secrets Manager",
        "WAF", "Shield", "GuardDuty", "Inspector", "Macie", "Security Hub",
        "Certificate Manager", "ACM", "Directory Service", "Firewall Manager",
        "Detective", "Artifact", "Audit Manager", "Security Lake",
        "Verified Access", "Private CA",
    ],
    "Management & Governance": [
        "CloudWatch", "CloudTrail", "CloudFormation", "Config", "Systems Manager",
        "SSM", "Organizations", "Control Tower", "Trusted Advisor", "Service Catalog",
        "Auto Scaling", "Health Dashboard", "Personal Health Dashboard",
        "Cost Explorer", "Budgets", "License Manager", "Resource Groups",
        "Service Quotas", "Well-Architected Tool", "Managed Grafana",
        "Managed Service for Prometheus", "Chatbot", "Compute Optimizer",
    ],
    "Application Integration": [
        "SQS", "SNS", "EventBridge", "Step Functions", "MQ", "AppSync",
        "MWAA", "Managed Workflows for Apache Airflow", "AppFlow",
    ],
    "Analytics": [
        "Athena", "Glue", "EMR", "Kinesis", "Kinesis Data Streams",
        "Kinesis Data Firehose", "Firehose", "OpenSearch Service", "OpenSearch",
        "Elasticsearch Service", "QuickSight", "Lake Formation", "MSK",
        "Data Pipeline", "CloudSearch",
    ],
    "Developer Tools": [
        "CodeBuild", "CodeCommit", "CodeDeploy", "CodePipeline", "CodeArtifact",
        "CodeStar", "Cloud9", "CloudShell", "X-Ray", "CDK", "Amplify",
    ],
    "Migration & Transfer": [
        "Migration Hub", "Application Migration Service", "MGN", "Transfer Family",
        "Application Discovery Service",
    ],
    "Machine Learning": [
        "SageMaker", "Bedrock", "Rekognition", "Comprehend", "Textract",
        "Translate", "Polly", "Transcribe", "Lex", "Kendra", "Forecast",
    ],
    "End User Computing": ["WorkSpaces", "AppStream 2.0", "WorkSpaces Web"],
    "Business Applications": ["SES", "Connect", "Pinpoint", "WorkMail", "Chime"],
}

# 複数カテゴリに列挙したサービス（ECS・EKS・Fargate 等）は、AWS 公式の分類に合わせて
# Containers を Compute より優先する。
PRIORITY = ["Containers"]


def normalize(name: str) -> str:
    """「Amazon EC2」「AWS Lambda」等の接頭辞・空白・記号を除いて比較用に整える。"""
    lowered = re.sub(r"^(amazon|aws)\s+", "", name.strip().lower())
    return re.sub(r"[\s\-_]+", "", lowered)


def build_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    ordered = PRIORITY + [c for c in AWS_SERVICE_CATEGORIES if c not in PRIORITY]
    for category in reversed(ordered):
        for service in AWS_SERVICE_CATEGORIES[category]:
            lookup[normalize(service)] = category
    return lookup


def set_subcategories(apps, schema_editor):
    Skill = apps.get_model("portfolio", "Skill")
    lookup = build_lookup()
    for skill in Skill.objects.filter(category=AWS_CATEGORY, subcategory=""):
        subcategory = lookup.get(normalize(skill.name))
        if subcategory:
            skill.subcategory = subcategory
            skill.save(update_fields=["subcategory"])


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0005_skill_subcategory"),
    ]

    operations = [
        migrations.RunPython(set_subcategories, migrations.RunPython.noop),
    ]
