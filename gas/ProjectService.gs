/**
 * 案件登録画面（基本設計書 5.3.2 案件登録）のサーバー側処理。
 * 更新対象は継続中の案件または新規の案件のいずれかであるため、終了済みの過去案件を選び直す機能は持たない。
 * 継続中の案件は、本業・副業の並行を想定し複数存在しうる。
 */

/**
 * 継続中の案件（終了年月が未設定の案件）を、start_year_month の降順で返す。
 */
function listOngoingProjects_() {
  return readRows_(SHEET_NAMES.PROJECTS)
    .filter((project) => !project.end_year_month)
    .sort((a, b) => (a.start_year_month < b.start_year_month ? 1 : -1));
}

function buildProjectDetail_(project) {
  const selectedSkills = readRows_(SHEET_NAMES.PROJECT_SKILLS)
    .filter((row) => row.project_id === project.project_id)
    .map((row) => ({ skill_id: row.skill_id, version: row.version || '' }));
  return {
    project_id: project.project_id,
    name: project.name,
    start_year_month: project.start_year_month,
    end_year_month: project.end_year_month,
    selectedSkills,
  };
}

/**
 * 案件登録画面の初期表示データを取得する。
 * スキル項目のカテゴリ別グループ（ページ送りの各ページに対応）、継続中の案件一覧
 * （プルダウン用）、初期選択される案件（start_year_month が最も新しい継続中案件）の
 * 登録内容を返す。
 */
function getProjectRegistrationInitialData() {
  const skills = sortByCategoryAndOrder_(readRows_(SHEET_NAMES.SKILLS));
  const skillCategories = groupSkillsByCategory_(skills);
  const ongoingProjects = listOngoingProjects_();
  const initial = ongoingProjects.length > 0 ? ongoingProjects[0] : null;

  return {
    skillCategories,
    ongoingProjects: ongoingProjects.map((project) => ({ project_id: project.project_id, name: project.name })),
    initialProject: initial ? buildProjectDetail_(initial) : null,
  };
}

/**
 * 継続中の案件選択プルダウンで切り替えたときに、対象案件の登録内容を取得する。
 */
function getProjectDetail(projectId) {
  const project = readRows_(SHEET_NAMES.PROJECTS).find((row) => row.project_id === projectId);
  if (!project) {
    throw new Error(`存在しない案件です: ${projectId}`);
  }
  return buildProjectDetail_(project);
}

function generateProjectId_() {
  const projects = readRows_(SHEET_NAMES.PROJECTS);
  let max = 0;
  projects.forEach((project) => {
    const match = /^project-(\d+)$/.exec(project.project_id);
    if (match) {
      max = Math.max(max, Number(match[1]));
    }
  });
  return `project-${max + 1}`;
}

/**
 * 案件を新規登録または更新する。project_id が未指定の場合は新規登録として自動採番する。
 * project_skills は既存レコードを削除したうえでチェックされたスキル項目（バージョンを含む）を
 * 追加する置き換え方式とする。
 */
function saveProject(project) {
  validateRequired_(project.name, '案件名');
  validateYearMonth_(project.start_year_month);
  validateYearMonthOptional_(project.end_year_month);
  validateYearMonthRange_(project.start_year_month, project.end_year_month);

  const validSkillIds = new Set(readRows_(SHEET_NAMES.SKILLS).map((row) => row.skill_id));
  const skills = project.skills || [];
  skills.forEach((skill) => {
    if (!validSkillIds.has(skill.skill_id)) {
      throw new Error(`存在しないスキル項目です: ${skill.skill_id}`);
    }
  });

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    let projectId = project.project_id;
    const record = {
      name: project.name,
      start_year_month: project.start_year_month,
      end_year_month: project.end_year_month || '',
    };

    if (projectId) {
      const updated = updateRowWhere_(
        SHEET_NAMES.PROJECTS,
        (row) => row.project_id === projectId,
        (row) => Object.assign({}, row, record),
      );
      if (!updated) {
        throw new Error(`存在しない案件です: ${projectId}`);
      }
    } else {
      projectId = generateProjectId_();
      appendRow_(SHEET_NAMES.PROJECTS, Object.assign({ project_id: projectId }, record));
    }

    deleteRowsWhere_(SHEET_NAMES.PROJECT_SKILLS, (row) => row.project_id === projectId);
    appendRows_(
      SHEET_NAMES.PROJECT_SKILLS,
      skills.map((skill) => ({ project_id: projectId, skill_id: skill.skill_id, version: skill.version || '' })),
    );

    return { success: true, project_id: projectId };
  } finally {
    lock.releaseLock();
  }
}

/**
 * 案件を削除する。紐づく project_skills の実績も同時に削除する。
 * 経験年数の算出結果に影響するため、削除確認は画面側のダイアログで行う。
 */
function deleteProject(projectId) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    deleteRowsWhere_(SHEET_NAMES.PROJECT_SKILLS, (row) => row.project_id === projectId);
    deleteRowsWhere_(SHEET_NAMES.PROJECTS, (row) => row.project_id === projectId);
  } finally {
    lock.releaseLock();
  }
  return { success: true };
}
