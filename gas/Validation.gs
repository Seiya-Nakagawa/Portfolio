/**
 * サーバー側の入力値検証。画面側の入力制限のみに依存しない。
 */

function validateYearMonth_(yearMonth) {
  if (typeof yearMonth !== 'string' || !YEAR_MONTH_PATTERN.test(yearMonth)) {
    throw new Error(`年月の形式が不正です（YYYY-MM で指定してください）: ${yearMonth}`);
  }
}

/**
 * 空文字列（継続中）を許容したうえで、値がある場合のみ形式を検証する。
 */
function validateYearMonthOptional_(yearMonth) {
  if (yearMonth === '' || yearMonth === undefined || yearMonth === null) {
    return;
  }
  validateYearMonth_(yearMonth);
}

/**
 * 終了年月が設定されている場合、開始年月以降であることを検証する。
 */
function validateYearMonthRange_(startYearMonth, endYearMonth) {
  if (endYearMonth && endYearMonth < startYearMonth) {
    throw new Error('終了年月は開始年月以降にしてください。');
  }
}

function validateId_(id, label) {
  if (typeof id !== 'string' || !ID_PATTERN.test(id)) {
    throw new Error(`${label}の形式が不正です（半角英小文字・数字・ハイフンのみ使用できます）: ${id}`);
  }
}

function validateRequired_(value, label) {
  if (value === undefined || value === null || String(value).trim() === '') {
    throw new Error(`${label}は必須です。`);
  }
}

function validateLevel_(level) {
  const levels = readRows_(SHEET_NAMES.LEVELS).map((row) => row.level);
  if (levels.indexOf(Number(level)) === -1) {
    throw new Error(`存在しない習熟度レベルです: ${level}`);
  }
}
