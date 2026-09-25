/**
 * スキル項目管理画面（基本設計書 5.3.2 スキル項目管理）のサーバー側処理。
 */

function listLevels() {
  return readRows_(SHEET_NAMES.LEVELS).sort((a, b) => b.level - a.level);
}

function listSkills() {
  const skills = sortByCategoryAndOrder_(readRows_(SHEET_NAMES.SKILLS));
  const experience = calculateExperience_(
    readRows_(SHEET_NAMES.PROJECTS),
    readRows_(SHEET_NAMES.PROJECT_SKILLS),
    currentYearMonth_(),
  );
  return skills.map((skill) => Object.assign({}, skill, {
    uniqueMonths: experience[skill.skill_id] ? experience[skill.skill_id].uniqueMonths : 0,
    years: experience[skill.skill_id] ? experience[skill.skill_id].years : '',
  }));
}

/**
 * スキル項目を新規登録する。skill_id は登録後変更しないため、追加時のみ入力を受け付ける。
 */
function createSkill(skill) {
  validateId_(skill.skill_id, 'スキルID');
  validateRequired_(skill.category, '種類');
  validateRequired_(skill.name, '項目名');
  validateLevel_(skill.level);
  validateRequired_(skill.sort_order, '表示順');

  const existing = readRows_(SHEET_NAMES.SKILLS);
  if (existing.some((row) => row.skill_id === skill.skill_id)) {
    throw new Error(`既に存在するスキルIDです: ${skill.skill_id}`);
  }

  appendRow_(SHEET_NAMES.SKILLS, {
    skill_id: skill.skill_id,
    category: skill.category,
    name: skill.name,
    level: Number(skill.level),
    remarks: skill.remarks || '',
    sort_order: Number(skill.sort_order),
  });

  return listSkills();
}

function updateSkill(skill) {
  validateRequired_(skill.category, '種類');
  validateRequired_(skill.name, '項目名');
  validateLevel_(skill.level);
  validateRequired_(skill.sort_order, '表示順');

  const updated = updateRowWhere_(
    SHEET_NAMES.SKILLS,
    (row) => row.skill_id === skill.skill_id,
    (row) => Object.assign({}, row, {
      category: skill.category,
      name: skill.name,
      level: Number(skill.level),
      remarks: skill.remarks || '',
      sort_order: Number(skill.sort_order),
    }),
  );
  if (!updated) {
    throw new Error(`存在しないスキルIDです: ${skill.skill_id}`);
  }

  return listSkills();
}

/**
 * 使用実績が1件も紐づかないスキル項目のみ削除できる。
 */
function deleteSkill(skillId) {
  const inUse = readRows_(SHEET_NAMES.PROJECT_SKILLS).some((row) => row.skill_id === skillId);
  if (inUse) {
    throw new Error('使用実績が紐づくスキル項目は削除できません。');
  }
  deleteRowsWhere_(SHEET_NAMES.SKILLS, (row) => row.skill_id === skillId);
  return listSkills();
}
