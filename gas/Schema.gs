/**
 * 実績シート（skills・projects・project_skills）のスキーマが最新であることを保証する。
 * 不足しているシート・列があれば追加のみ行い、既存データは変更・削除しない。
 * ウェブアプリの起動（doGet）ごとに自動実行し、スキーマ変更を手動実行なしで反映する。
 */
function ensureSkillsSchema_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  let projectSkillsSheet = ss.getSheetByName(SHEET_NAMES.PROJECT_SKILLS);
  if (!projectSkillsSheet) {
    projectSkillsSheet = ss.insertSheet(SHEET_NAMES.PROJECT_SKILLS);
    projectSkillsSheet.getRange(1, 1, 1, 3).setValues([['project_id', 'skill_id', 'version']]);
  } else {
    const psHeaders = projectSkillsSheet.getRange(1, 1, 1, projectSkillsSheet.getLastColumn()).getValues()[0];
    if (psHeaders.indexOf('version') === -1) {
      const nextColumn = projectSkillsSheet.getLastColumn() + 1;
      projectSkillsSheet.getRange(1, nextColumn, 1, 1).setValues([['version']]);
    }
  }

  const projectsSheet = ss.getSheetByName(SHEET_NAMES.PROJECTS);
  const headers = projectsSheet.getRange(1, 1, 1, projectsSheet.getLastColumn()).getValues()[0];
  if (headers.indexOf('start_year_month') === -1) {
    const nextColumn = projectsSheet.getLastColumn() + 1;
    projectsSheet.getRange(1, nextColumn, 1, 2).setValues([['start_year_month', 'end_year_month']]);
    const dataRowCount = projectsSheet.getLastRow() - 1;
    if (dataRowCount > 0) {
      projectsSheet.getRange(2, nextColumn, dataRowCount, 2).setNumberFormat('@');
    }
  }
}
