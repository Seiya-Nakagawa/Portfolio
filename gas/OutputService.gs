/**
 * 出力画面（基本設計書 5.3.2 出力、6.2〜6.3）のサーバー側処理。
 * ポートフォリオ用 JSON、職務経歴書用 Markdown を生成する。
 */

function generateOutputs() {
  const skills = sortByCategoryAndOrder_(readRows_(SHEET_NAMES.SKILLS));
  const levels = readRows_(SHEET_NAMES.LEVELS);
  const levelMap = {};
  levels.forEach((level) => { levelMap[level.level] = level; });

  const projects = readRows_(SHEET_NAMES.PROJECTS);
  const projectSkills = readRows_(SHEET_NAMES.PROJECT_SKILLS);
  const experience = calculateExperience_(projects, projectSkills, currentYearMonth_());

  const usedSkills = skills.filter((skill) => experience[skill.skill_id] && experience[skill.skill_id].uniqueMonths > 0);
  const unusedSkillCount = skills.length - usedSkills.length;

  const invalidLevelSkills = [];
  const outputSkills = [];
  const skillTableRows = [];

  usedSkills.forEach((skill) => {
    const exp = experience[skill.skill_id];
    outputSkills.push({
      category: skill.category,
      name: skill.name,
      months: exp.uniqueMonths,
      years: exp.years,
      level: skill.level,
    });

    const level = levelMap[skill.level];
    if (!level) {
      invalidLevelSkills.push(skill.name);
      return;
    }
    const resumeLevel = skill.remarks ? `${level.resume_label}（${skill.remarks}）` : level.resume_label;
    skillTableRows.push(`| ${skill.category} | ${skill.name} | ${exp.startYear}年 | ${exp.years} | ${resumeLevel} |`);
  });

  const warnings = [];
  if (unusedSkillCount > 0) {
    warnings.push(`使用実績が1件もないスキル項目が ${unusedSkillCount} 件あります（出力対象外）。`);
  }
  if (invalidLevelSkills.length > 0) {
    warnings.push(`levels シートに存在しない習熟度レベルを持つスキル項目があります: ${invalidLevelSkills.join('、')}`);
  }

  const json = JSON.stringify({
    generated_at: formatDate_(new Date()),
    skills: outputSkills,
  }, null, 2);

  const skillTableMarkdown = [
    '| 種類 | 項目 | 開始年 | 使用期間 | レベル |',
    '| --- | --- | --- | --- | --- |',
  ].concat(skillTableRows).join('\n');

  const projectPeriodMarkdown = projects
    .slice()
    .sort((a, b) => (a.start_year_month < b.start_year_month ? -1 : 1))
    .map((project) => `**${formatProjectPeriod_(project)}｜${project.name}**`)
    .join('\n');

  return {
    json,
    markdown: `${skillTableMarkdown}\n\n${projectPeriodMarkdown}`,
    warnings,
  };
}
