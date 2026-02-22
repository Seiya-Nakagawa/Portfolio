# ポートフォリオサイト リニューアル基本設計書

## 1. はじめに

本ドキュメントは、`REQUIREMENTS.md` に基づくポートフォリオサイトリニューアルの基本設計をまとめたものである。

## 2. システムアーキテクチャ

### 2.1 構成概要

GitHub Pages を利用した静的サイトホスティング構成とする。
ビルドプロセスを排し、純粋な HTML/CSS/JavaScript で構成することで、保守性と学習コストの低減を図る。

| 階層 | 技術スタック | 備考 |
|------|--------------|------|
| フロントエンド | HTML5, CSS3, Vanilla JS | フレームワーク依存なし |
| ホスティング | GitHub Pages | リポジトリ連携 |
| ドメイン | github.io サブドメイン | <https://seiyanakagawa2219.github.io/Portfolio/> |

### 2.2 ディレクトリ構成

機能追加に伴い、翻訳データ格納用の `i18n.js` を追加する。

```
Portfolio/
├── index.html          # エントリーポイント
├── css/
│   ├── style.css       # メインスタイルシート
│   ├── variables.css   # CSS変数定義（色、フォント、サイズ）
│   ├── reset.css       # リセットCSS
│   └── components/     # コンポーネント別CSS（必要に応じて分割）
├── js/
│   ├── main.js         # メインロジック（UI操作、イベント）
│   ├── data.js         # コンテンツデータ（スキル、実績など）
│   └── i18n.js         # 翻訳リソースデータ（日/英）
├── assets/
│   ├── images/         # 画像ファイル
│   └── fonts/          # フォントファイル
└── docs/
    ├── REQUIREMENTS.md # 要件定義書
    └── DESIGN.md       # 基本設計書
```

## 3. デザインシステム（UI/UX）

### 3.1 コンセプト: "Dark Mode x Glassmorphism"（Light Mode対応）

要件に基づき、デフォルトはダークモードとし、ユーザー操作によりライトモードへ切り替え可能とする。

- **ダークモード（デフォルト）**:
  - ベース: 深い紺色 (#0f172a)
  - アクセント: シアン、パープルのネオンカラー
- **ライトモード**:
  - ベース: 不透明度の高い白/明るいグレー (#f8fafc)
  - アクセント: 視認性の高い青、紫
  - ガラス効果: 白ベースの曇りガラス

### 3.2 カラーパレット定義 (css/variables.css)

CSSカスタムプロパティ（CSS変数）を使用し、`body.light-mode` クラスの有無で変数を上書きする設計とする。

```css
:root {
  /* Default (Dark) */
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
  --accent-1: #06b6d4;
  --glass-bg: rgba(255, 255, 255, 0.05);
  --glass-border: rgba(255, 255, 255, 0.1);
}

body.light-mode {
  /* Light Mode Overrides */
  --bg-primary: #f8fafc;
  --bg-secondary: #e2e8f0;
  --text-main: #1e293b;
  --text-muted: #475569;
  --accent-1: #0284c7;
  --glass-bg: rgba(255, 255, 255, 0.4);
  --glass-border: rgba(255, 255, 255, 0.6);
}
```

### 3.3 UIコンポーネント

- **モード切替スイッチ**: ヘッダー内に配置。太陽/月のアイコンでトグル。
- **言語切替スイッチ**: ヘッダー内に配置。「JP / EN」テキストまたは国旗アイコン。

## 4. 機能詳細設計

### 4.1 タイピングアニメーション (Hero)

Heroセクションの肩書き部分等をタイプライターのように表示する。

- **ロジック**:
  - 文字列配列: `["Cloud Architect Engineer", "Full Stack Engineer", "Problem Solver"]`
  - 処理: 1文字ずつ `span` に追加 → 一時停止 → 1文字ずつ削除 → 次の単語へ。
  - ループ再生。

### 4.2 スキルバー (Skills)

IntersectionObserver を使用し、スクロールして画面に入ったタイミングでアニメーションを開始する。

- **デザイン**:
  - プログレスバー形式。
  - 幅 0% から指定% までスムーズに伸長（transition / animation）。
- **データ構造 (`js/data.js`)**:

  ```javascript
  { name: "HTML/CSS", percent: 80, category: "frontend" }
  ```

### 4.3 多言語対応 (i18n)

URLパラメータや複雑なルーティングは使わず、DOMのテキスト書き換えのみで対応するシンプル設計とする。

- **データ構造 (`js/i18n.js`)**:

  ```javascript
  const resources = {
    ja: {
      hero: { title: "こんにちは" },
      about: { description: "..." }
    },
    en: {
      hero: { title: "Hello" },
      about: { description: "..." }
    }
  };
  ```

- **切り替えロジック**:
  - `data-i18n="hero.title"` のような属性をHTML要素に付与。
  - JSで現在の言語(`currentLang`)に基づき、該当キーのテキストを流し込む。
  - 言語状態は `localStorage` に保存し、次回訪問時に維持する。

### 4.4 その他のセクション

- **About**: 年齢自動計算ロジックをJSで実装。
- **Works**: `js/data.js` から動的にカードを生成。
- **Contact**: Google Forms へのリンク。

## 5. 実装フェーズ分け

### Phase 1: ベース構築と静的コンテンツ

- ディレクトリセットアップ
- HTML構造 (セマンティックタグ)
- 基本CSS (Variables, Reset, Layout)
- コンテンツ流し込み (日本語のみ)

### Phase 2: デザイン適用 (Glassmorphism & Dark/Light)

- ガラスモーフィズムの実装
- ダークモードのスタイリング
- ライトモード用変数の調整と切替スイッチ実装

### Phase 3: 動的機能とアニメーション

- タイピングアニメーション
- スキルバーアニメーション (IntersectionObserver)
- 多言語対応ロジック実装 (Data binding)

### Phase 4: レスポンシブ調整と最終確認

- モバイルビュー調整
- 各ブラウザ確認
