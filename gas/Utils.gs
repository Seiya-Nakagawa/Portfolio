/**
 * スキル項目のカテゴリ順・年月展開等、複数サービスで共通して使う補助関数。
 */

/**
 * skills シートの行を category・sort_order の昇順に並べ替える。
 * カテゴリの表示順は、各カテゴリに属するスキル項目の sort_order の最小値から導出する
 * （基本設計書 5.3.2）。カテゴリ順のためだけの列は持たない。
 */
function sortByCategoryAndOrder_(skills) {
  const minOrderByCategory = {};
  skills.forEach((skill) => {
    const current = minOrderByCategory[skill.category];
    if (current === undefined || skill.sort_order < current) {
      minOrderByCategory[skill.category] = skill.sort_order;
    }
  });
  return skills.slice().sort((a, b) => {
    if (a.category !== b.category) {
      return minOrderByCategory[a.category] - minOrderByCategory[b.category];
    }
    return a.sort_order - b.sort_order;
  });
}

/**
 * category・sort_order 順に並べたスキル項目を、カテゴリ単位のグループ配列に変換する。
 * 配列の順序がそのままカテゴリの表示順（案件登録画面のページ順）になる。
 * @param {Array<Object>} sortedSkills sortByCategoryAndOrder_ 済みのスキル項目
 * @return {Array<{category: string, skills: Array<Object>}>}
 */
function groupSkillsByCategory_(sortedSkills) {
  const order = [];
  const groups = {};
  sortedSkills.forEach((skill) => {
    if (!groups[skill.category]) {
      groups[skill.category] = [];
      order.push(skill.category);
    }
    groups[skill.category].push(skill);
  });
  return order.map((category) => ({ category, skills: groups[category] }));
}

/**
 * 開始年月から終了年月までの年月文字列（YYYY-MM）を、両端を含めて昇順に列挙する。
 */
function expandYearMonths_(startYearMonth, endYearMonth) {
  const months = [];
  let year = Number(startYearMonth.slice(0, 4));
  let month = Number(startYearMonth.slice(5, 7));
  const endYear = Number(endYearMonth.slice(0, 4));
  const endMonth = Number(endYearMonth.slice(5, 7));
  while (year < endYear || (year === endYear && month <= endMonth)) {
    months.push(`${year}-${String(month).padStart(2, '0')}`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return months;
}

function currentYearMonth_() {
  return Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM');
}

function formatDate_(date) {
  return Utilities.formatDate(date, 'Asia/Tokyo', 'yyyy-MM-dd');
}
