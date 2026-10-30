"""検索の入口となる解説記事の一覧。本文は templates/articles/{slug}.html に置く。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    description: str


ARTICLES = (
    Article(
        slug="engineer-experience-years",
        title="エンジニアの経験年数の数え方",
        description="並行案件や複数の技術をどう数えるか。スキルごとの経験年数を重複なく算出する考え方を解説します。",
    ),
    Article(
        slug="ses-resume-guide",
        title="SES エンジニアの職務経歴書の書き方",
        description="案件が多い SES エンジニア向けに、職務経歴書の構成・案件の書き方・スキルの整理方法を解説します。",
    ),
)


def get_article(slug: str) -> Article | None:
    return next((a for a in ARTICLES if a.slug == slug), None)
