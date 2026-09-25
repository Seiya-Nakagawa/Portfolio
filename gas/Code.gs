/**
 * ウェブアプリのエントリーポイント。
 */

function doGet() {
  ensureSkillsSchema_();
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('スキル実績管理')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
