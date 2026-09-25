/**
 * 実績シートのシート名・入力値のバリデーションパターンを定義する。
 */

const SHEET_NAMES = {
  SKILLS: 'skills',
  PROJECTS: 'projects',
  PROJECT_SKILLS: 'project_skills',
  LEVELS: 'levels',
};

const YEAR_MONTH_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/;
const ID_PATTERN = /^[a-z0-9-]+$/;
