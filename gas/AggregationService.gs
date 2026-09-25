/**
 * 経験年数の算出（基本設計書 4.7）と案件期間の表記（基本設計書 4.8）。
 * 集計値はシートに保持せず、出力時に都度算出する。
 */

/**
 * projects・project_skills から、skill_id ごとのユニーク月数・経験年数・開始年を算出する。
 * 案件の開始年月〜終了年月（継続中の場合は baseYearMonth）を年月に展開し、
 * その案件で使用したスキル項目それぞれへ展開年月を割り当てて、スキル単位で和集合を取る。
 * @param {Array<{project_id: string, start_year_month: string, end_year_month: string}>} projects
 * @param {Array<{project_id: string, skill_id: string}>} projectSkills
 * @param {string} baseYearMonth 出力時点の年月（継続中案件の終了年月とみなす基準）
 * @return {Object<string, {uniqueMonths: number, years: string, startYear: (number|null)}>}
 */
function calculateExperience_(projects, projectSkills, baseYearMonth) {
  const monthsByProject = {};
  projects.forEach((project) => {
    const end = project.end_year_month || baseYearMonth;
    monthsByProject[project.project_id] = expandYearMonths_(project.start_year_month, end);
  });

  const monthsBySkill = {};
  projectSkills.forEach((record) => {
    const months = monthsByProject[record.project_id] || [];
    if (!monthsBySkill[record.skill_id]) {
      monthsBySkill[record.skill_id] = new Set();
    }
    months.forEach((month) => monthsBySkill[record.skill_id].add(month));
  });

  const result = {};
  Object.keys(monthsBySkill).forEach((skillId) => {
    const months = Array.from(monthsBySkill[skillId]).sort();
    const uniqueMonths = months.length;
    result[skillId] = {
      uniqueMonths,
      years: formatExperienceYears_(uniqueMonths),
      startYear: uniqueMonths > 0 ? Number(months[0].split('-')[0]) : null,
    };
  });
  return result;
}

/**
 * ユニーク月数を「N年Mヶ月」表記へ変換する（基本設計書 4.7 の変換規則）。
 */
function formatExperienceYears_(uniqueMonths) {
  if (uniqueMonths <= 0) {
    return '';
  }
  if (uniqueMonths < 12) {
    return `${uniqueMonths}ヶ月`;
  }
  const years = Math.floor(uniqueMonths / 12);
  const months = uniqueMonths % 12;
  return months === 0 ? `${years}年` : `${years}年${months}ヶ月`;
}

/**
 * 案件の開始年月・終了年月を「YYYY年MM月〜YYYY年MM月」表記へ変換する（基本設計書 4.8）。
 * 終了年月が空文字列の場合は継続中とみなし「〜現在」と表記する。
 */
function formatProjectPeriod_(project) {
  const toLabel = (yearMonth) => {
    const year = yearMonth.slice(0, 4);
    const month = yearMonth.slice(5, 7);
    return `${year}年${month}月`;
  };
  return project.end_year_month
    ? `${toLabel(project.start_year_month)}〜${toLabel(project.end_year_month)}`
    : `${toLabel(project.start_year_month)}〜現在`;
}
