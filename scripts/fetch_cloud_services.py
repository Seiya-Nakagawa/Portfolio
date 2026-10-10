"""各クラウドの公式サイトからサービス一覧を取得し、スキル項目マスタの種データを更新する。

取得元（いずれも公式サイト）:
  - AWS: aws.amazon.com の製品ディレクトリ（種別が Service のもの）
  - Azure: azure.microsoft.com の製品一覧（カテゴリ別）
  - Google Cloud: docs.cloud.google.com の AWS・Azure・Google Cloud サービス比較表
  - OCI: docs.oracle.com の OCI ドキュメントのサービス一覧（カテゴリ別）

`webapp/portfolio/seed/skills_master.json` のうち、上記 4 つのクラウドの種類だけを置き換え、
その他の種類（言語・DB 等）は変更しない。

使い方: python3 scripts/fetch_cloud_services.py
"""

import html
import json
import re
import urllib.request
from pathlib import Path

SEED_FILE = (
    Path(__file__).resolve().parent.parent
    / "webapp"
    / "portfolio"
    / "seed"
    / "skills_master.json"
)
USER_AGENT = "Mozilla/5.0"
TIMEOUT_SECONDS = 60

AWS_URL = (
    "https://aws.amazon.com/api/dirs/items/search"
    "?item.directoryId=aws-products&item.locale=en_US&size=500"
)
AZURE_URL = "https://azure.microsoft.com/en-us/products/"
GCP_URL = (
    "https://docs.cloud.google.com/docs/get-started/aws-azure-gcp-service-comparison"
)
OCI_URL = "https://docs.oracle.com/en-us/iaas/Content/home.htm"

# 公式サイト上で表記が揺れているカテゴリ名の統一。
AWS_CATEGORY_ALIASES = {
    "Databases": "Database",
    "Business Application": "Business Applications",
    "Security, Identity & Compliance": "Security, Identity, & Compliance",
}
# 名称末尾の状態表記（例: "(Preview)"）と旧称の補足。
STATUS_SUFFIX = re.compile(
    r"\s*\((?:preview|coming soon|formerly [^)]*|now [^)]*)\)\s*$", re.IGNORECASE
)
UNCATEGORIZED = "Other"
# スキル項目の表示名の最大文字数、subcategory の最大文字数（モデルの定義に合わせる）。
MAX_NAME_LENGTH = 128
MAX_SUBCATEGORY_LENGTH = 64


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def clean_name(name: str) -> str:
    return STATUS_SUFFIX.sub("", name.strip())


def fetch_aws() -> list[tuple[str, str]]:
    items = json.loads(fetch(AWS_URL))["items"]
    services = []
    for entry in items:
        tag_ids = {tag["id"] for tag in entry["tags"]}
        if "aws-products#type#service" not in tag_ids:
            continue
        fields = entry["item"]["additionalFields"]
        category = fields.get("productCategory") or UNCATEGORIZED
        services.append(
            (
                AWS_CATEGORY_ALIASES.get(category, category),
                clean_name(fields["productName"]),
            )
        )
    return services


def fetch_azure() -> list[tuple[str, str]]:
    page = fetch(AZURE_URL)
    # カテゴリ見出し（h2）の位置で区切り、各区間のカード見出し（h3）をサービス名とする。
    headings = [
        (m.start(), strip_tags(m.group(1)))
        for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", page, re.DOTALL)
    ]
    services = []
    for index, (start, category) in enumerate(headings):
        if category == "Select a category:":
            continue
        end = headings[index + 1][0] if index + 1 < len(headings) else len(page)
        for m in re.finditer(
            r'<h3 class="h5">\s*(.*?)\s*</h3>', page[start:end], re.DOTALL
        ):
            services.append((category, clean_name(strip_tags(m.group(1)))))
    return services


def fetch_gcp() -> list[tuple[str, str]]:
    page = fetch(GCP_URL)
    services = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.DOTALL)[1:]:
        cells = [
            strip_tags(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        ]
        if len(cells) >= 3 and cells[2]:
            services.append((cells[0], clean_name(cells[2])))
    return services


def fetch_oci() -> list[tuple[str, str]]:
    page = fetch(OCI_URL)
    page = page[page.index(">Services<") :]
    services = []
    for m in re.finditer(r"<h4>(.*?)</h4>\s*<ul[^>]*>(.*?)</ul>", page, re.DOTALL):
        category = strip_tags(m.group(1))
        for link in re.findall(r"<a [^>]*>(.*?)</a>", m.group(2), re.DOTALL):
            services.append((category, clean_name(strip_tags(link))))
    return services


def build_category(name: str, prefix: str, services: list[tuple[str, str]]) -> dict:
    """サービス名の重複（大文字小文字を区別しない）を除き、最初に現れたカテゴリを採用する。"""
    seen: set[str] = set()
    # 大文字小文字だけが異なるカテゴリ名は、最初に現れた表記に統一する。
    spellings: dict[str, str] = {}
    skills = []
    for subcategory, service in services:
        subcategory = spellings.setdefault(subcategory.casefold(), subcategory)
        key = service.casefold()
        if not service or key in seen:
            continue
        if len(service) > MAX_NAME_LENGTH:
            raise ValueError(f"名称が長すぎます: {service}")
        seen.add(key)
        skills.append(
            {"name": service, "subcategory": subcategory[:MAX_SUBCATEGORY_LENGTH]}
        )
    return {"name": name, "skill_id_prefix": prefix, "skills": skills}


def write_seed(categories: list[dict]) -> None:
    """1 スキル項目を 1 行にして書き出す（差分を読みやすくするため）。"""
    blocks = []
    for category in categories:
        lines = ",\n".join(
            "      " + json.dumps(s, ensure_ascii=False) for s in category["skills"]
        )
        blocks.append(
            "    {\n"
            f'      "name": {json.dumps(category["name"], ensure_ascii=False)},\n'
            f'      "skill_id_prefix": {json.dumps(category["skill_id_prefix"])},\n'
            f'      "skills": [\n{lines}\n      ]\n    }}'
        )
    SEED_FILE.write_text(
        '{\n  "categories": [\n' + ",\n".join(blocks) + "\n  ]\n}\n", encoding="utf-8"
    )


def main() -> None:
    clouds = {
        "AWS": ("aws-", fetch_aws),
        "Azure": ("azure-", fetch_azure),
        "Google Cloud": ("gcp-", fetch_gcp),
        "OCI": ("oci-", fetch_oci),
    }
    current = json.loads(SEED_FILE.read_text(encoding="utf-8"))["categories"]
    others = [c for c in current if c["name"] not in clouds]
    fetched = [
        build_category(name, prefix, fn()) for name, (prefix, fn) in clouds.items()
    ]
    for category in fetched:
        print(f"{category['name']}: {len(category['skills'])} 件")
    write_seed(fetched + others)


if __name__ == "__main__":
    main()
