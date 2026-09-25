/**
 * 実績シートの各シートに対する汎用的な読み書き処理。
 * 列位置ではなくヘッダー名（1行目）で列を解決する。
 */

function getSheet_(sheetName) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  if (!sheet) {
    throw new Error(`シート "${sheetName}" が見つかりません。`);
  }
  return sheet;
}

function getHeaders_(sheet) {
  const lastColumn = sheet.getLastColumn();
  return sheet.getRange(1, 1, 1, lastColumn).getValues()[0];
}

/**
 * シートの全レコードをヘッダー名をキーとしたオブジェクトの配列で返す。
 * 全列が空の行はスキップする。
 */
function readRows_(sheetName) {
  const sheet = getSheet_(sheetName);
  const values = sheet.getDataRange().getValues();
  if (values.length === 0) {
    return [];
  }
  const headers = values[0];
  const rows = [];
  for (let i = 1; i < values.length; i += 1) {
    const row = values[i];
    if (row.every((cell) => cell === '')) {
      continue;
    }
    const record = {};
    headers.forEach((header, index) => {
      record[header] = row[index];
    });
    rows.push(record);
  }
  return rows;
}

function appendRow_(sheetName, record) {
  const sheet = getSheet_(sheetName);
  const headers = getHeaders_(sheet);
  const row = headers.map((header) => (record[header] !== undefined ? record[header] : ''));
  sheet.appendRow(row);
}

function appendRows_(sheetName, records) {
  if (records.length === 0) {
    return;
  }
  const sheet = getSheet_(sheetName);
  const headers = getHeaders_(sheet);
  const rows = records.map((record) => headers.map((header) => (record[header] !== undefined ? record[header] : '')));
  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, headers.length).setValues(rows);
}

/**
 * 条件に一致する行を削除する（末尾から走査し、削除による行番号のズレを避ける）。
 */
function deleteRowsWhere_(sheetName, predicate) {
  const sheet = getSheet_(sheetName);
  const values = sheet.getDataRange().getValues();
  if (values.length <= 1) {
    return;
  }
  const headers = values[0];
  for (let i = values.length - 1; i >= 1; i -= 1) {
    const record = {};
    headers.forEach((header, index) => {
      record[header] = values[i][index];
    });
    if (predicate(record)) {
      sheet.deleteRow(i + 1);
    }
  }
}

/**
 * 条件に一致する最初の行を updater の戻り値で置き換える。
 * 一致する行があった場合は true、なければ false を返す。
 */
function updateRowWhere_(sheetName, predicate, updater) {
  const sheet = getSheet_(sheetName);
  const values = sheet.getDataRange().getValues();
  if (values.length <= 1) {
    return false;
  }
  const headers = values[0];
  for (let i = 1; i < values.length; i += 1) {
    const record = {};
    headers.forEach((header, index) => {
      record[header] = values[i][index];
    });
    if (predicate(record)) {
      const updated = updater(record);
      const row = headers.map((header) => (updated[header] !== undefined ? updated[header] : ''));
      sheet.getRange(i + 1, 1, 1, headers.length).setValues([row]);
      return true;
    }
  }
  return false;
}
