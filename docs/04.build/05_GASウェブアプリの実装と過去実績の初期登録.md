# 05 構築手順書 - GASウェブアプリの実装と過去実績の初期登録

## 目次

- [1. 概要](#1-概要)
- [2. 前提条件](#2-前提条件)
- [3. 手順](#3-手順)
  - [3.1. アプリケーションコードの配置](#31-アプリケーションコードの配置)
  - [3.2. デプロイ](#32-デプロイ)
  - [3.3. スキーマの自動補完の確認](#33-スキーマの自動補完の確認)
  - [3.4. スキル項目マスタの拡充](#34-スキル項目マスタの拡充)
  - [3.5. 過去のスキル使用実績の初期登録](#35-過去のスキル使用実績の初期登録)
  - [3.6. カテゴリ表示順の調整](#36-カテゴリ表示順の調整)

## 1. 概要

Issue #25・#28。基本設計に沿ってスキル実績管理の GAS ウェブアプリを実装し、過去のスキル使用実績を
実績シートへ初期登録する。

## 2. 前提条件

- [基本設計書 4章](../02.design/DESIGN.md#4-データ設計)・[5章](../02.design/DESIGN.md#5-画面設計)で
  データ構成・画面構成が確定していること
- [04_実績シートの作成とスキル項目初期登録](04_実績シートの作成とスキル項目初期登録.md)により、
  実績シートおよびスキル項目・案件（名称のみ）が登録済みであること
- clasp がインストール済みで、`.clasp.json`（`scriptId`・固定 `deploymentId`）が設定済みであること

## 3. 手順

### 3.1. アプリケーションコードの配置

1. `gas/` 配下にアプリケーションコードを配置する。

   | ファイル | 役割 |
   | --- | --- |
   | `Code.gs` | ウェブアプリのエントリーポイント（`doGet`）。起動時にスキーマの自動補完を実行する |
   | `Schema.gs` | 実績シートのスキーマ（不足シート・列）を補完する |
   | `Constants.gs` | シート名・バリデーション用定数 |
   | `Repository.gs` | ヘッダー名ベースのシート読み書き共通処理 |
   | `Utils.gs` | カテゴリ順ソート・年月展開等の共通処理 |
   | `Validation.gs` | 入力値のバリデーション |
   | `SkillService.gs` | スキル項目の一覧取得・登録・変更・削除 |
   | `ProjectService.gs` | 案件登録画面のサーバー側処理 |
   | `AggregationService.gs` | 経験年数の算出 |
   | `OutputService.gs` | ポートフォリオ用 JSON・職務経歴書用 Markdown の出力 |
   | `Index.html` | 画面のマークアップ |
   | `JavaScript.html` | 画面の操作ロジック |
   | `Stylesheet.html` | 画面のスタイル |
   | `appsscript.json` | マニフェスト（ウェブアプリ公開設定） |

### 3.2. デプロイ

1. リポジトリルートから `clasp push` を実行し、コードをスクリプトエディタへ反映する。
2. `clasp deploy -i {固定デプロイメントID} -d "{変更内容}"` を実行し、既存デプロイを更新する。

### 3.3. スキーマの自動補完の確認

1. ウェブアプリの URL を開く。`Code.gs` の `doGet` が `ensureSkillsSchema_`（`Schema.gs`）を実行し、
   以下が自動的に補完されることを確認する。

   - `project_skills` シートの作成（`project_id`, `skill_id`, `version` 列）
   - `projects` シートへの `start_year_month`・`end_year_month` 列の追加

### 3.4. スキル項目マスタの拡充

1. `skills` シートで、パブリッククラウドの単一項目（`aws` / `google-cloud` / `oci`）を削除する。
2. クラウド提供元ごとのサービス単位の項目を追加する（level は削除した元項目の値を引き継ぐ）。

   | カテゴリ | level | 追加する項目（`name`） |
   | --- | --- | --- |
   | AWS | 5 | Athena, CloudFormation, Kinesis, Config, SQS, Step Functions, Budgets, CloudFront, Auto Scaling, Direct Connect, VPN, Transit Gateway, PrivateLink, ECR, ECS, Fargate, Aurora, WAF, DynamoDB, IAM, EFS, Security Hub, Shield, API Gateway, Cloud9, CodeBuild, CodeCommit, CodeDeploy, CodePipeline, Systems Manager, SES, Lambda, GuardDuty, KMS, ElastiCache, Backup, Secrets Manager, CloudWatch, CloudTrail, CLI, EventBridge, SNS, Cost Explorer, Cost and Usage Report, Route 53, EC2, VPC, ELB, RDS, Certificate Manager, S3（51件、`skill_id` は `aws-` 接頭辞） |
   | Google Cloud | 3 | Compute Engine, Cloud Storage, Cloud Logging, Cloud Monitoring, IAM, BigQuery（6件、`skill_id` は `gcp-` 接頭辞） |

3. OCI・Azure の主要サービス項目を新規に追加する（level 1）。

   | カテゴリ | 追加する項目（`name`） |
   | --- | --- |
   | OCI | Compute, VCN, Object Storage, Autonomous Database, IAM, Load Balancer, Block Volume（`skill_id` は `oci-` 接頭辞） |
   | Azure | Virtual Machines, Virtual Network, Blob Storage, Functions, Entra ID, DevOps, App Service（`skill_id` は `azure-` 接頭辞） |

4. 既存カテゴリへ、各分野でメジャーな製品・ツールを追加する（level 1）。

   | カテゴリ | 追加する項目 |
   | --- | --- |
   | OS | macOS |
   | 言語 | TypeScript, Go, C#, Ruby |
   | フレームワーク | React, Vue.js, Django, Flask, Express, .NET |
   | DB | PostgreSQL, SQL Server, MongoDB, Redis |
   | ジョブ管理 | cron |
   | 監視 | Datadog, Prometheus, Grafana, New Relic |
   | ログ分析 | Splunk, Fluentd |
   | IaC | Pulumi |
   | コンテナ | Kubernetes, Podman, Docker Compose |
   | CI/CD | Jenkins, CircleCI, Travis CI |
   | クラスタリング | Pacemaker, Windows Server Failover Clustering |

5. インフラとしての導入・設定実績を、プログラミング・実装経験（言語・フレームワーク・DB の各項目）と
   区別して管理するため、新規カテゴリ「ミドルウェア」を追加する（level 1）。

   | `skill_id` | `name` |
   | --- | --- |
   | `nginx` | Nginx |
   | `composer` | Composer |
   | `certbot` | Certbot |
   | `phpmyadmin` | phpMyAdmin |
   | `fail2ban` | fail2ban |
   | `mw-php` | PHP（実行環境の導入・設定） |
   | `mw-laravel` | Laravel（デプロイ・運用設定） |
   | `mw-mysql` | MySQL（サーバーの導入・設定） |

### 3.5. 過去のスキル使用実績の初期登録

1. `projects` シートの各案件へ、`skillsheet/master.md` の記載に基づき開始年月・終了年月を登録する
   （継続中の案件は終了年月を空欄のままとする）。
2. `project_skills` シートへ、案件ごとに使用したスキル項目を登録する。バージョンが判明している項目は
   `version` 列に記載する（不明な項目は空欄とする）。

   | project_id | 開始年月 | 終了年月 | 使用スキル項目（`skill_id`、括弧内は `version`） |
   | --- | --- | --- | --- |
   | traffic-ic-aws-migration | 2026-02 | （継続中） | windows, python, clusterpro, aws-aurora, eks-kubernetes, aws-cloudtrail, aws-ecs, aws-fargate, aws-iam, aws-eventbridge, aws-step-functions |
   | mobile-carrier-aws-migration | 2025-10 | 2026-03 | cloudformation-sceptre, docker, aws-ecs, mysql, linux, aws-cloudfront, aws-elb, aws-ec2, cloudformation |
   | bank-gcp-platform | 2025-05 | 2025-09 | linux, terraform, b-shell, gcp-iam, gcp-compute-engine, gcp-cloud-storage, gcp-bigquery, gcp-cloud-logging, gcp-cloud-monitoring |
   | bank-aws-platform-general | 2024-04 | 2025-04 | linux, jp1-ajs, jp1-base, b-shell, python, aws-lambda, aws-step-functions, aws-codedeploy, codedeploy, gitlab-runner, cloudformation, aws-eventbridge, aws-systems-manager |
   | bank-aws-platform-corporate | 2023-01 | 2024-03 | linux, aws-route53, aws-eventbridge, aws-elb, redis, aws-elasticache |
   | drive-recorder-aws-platform | 2022-05 | 2022-12 | linux, terraform |
   | mlit-infra-maintenance | 2022-04 | 2022-04 | linux, b-shell, ansible |
   | financial-standardization | 2021-08 | 2022-03 | windows, linux, b-shell, ansible, elk-stack, oci-compute |
   | telecom-server-replace | 2020-10 | 2021-06 | windows, linux, zabbix, loadstar-scheduler, esb-file-transfer |
   | railway-point-aws | 2020-01 | 2020-09 | windows, linux, b-shell, aws-vpc, aws-ec2, aws-cloudwatch, aws-sns, aws-cloudfront |
   | real-estate-web | 2018-03 | 2019-12 | windows, linux, java, sql, javascript, html-css |
   | securities-infra | 2017-04 | 2018-02 | windows, linux |
   | mobile-server-config-change | 2017-01 | 2017-03 | windows, linux |
   | sme-security-monitoring | 2014-06 | 2016-12 | windows |
   | toei-bizcom-sales | 2012-04 | 2014-05 | windows |
   | ec-f-company-build | 2026-04 | （継続中） | linux（Ubuntu 26.04）, mw-php（8.5.4）, mw-laravel, mw-mysql（8.4.9）, nginx, composer（2.9.8）, certbot（4.0.0）, phpmyadmin（5.2.3）, fail2ban（1.1.0） |
   | ec-s-company-maintenance | 2026-04 | （継続中） | linux（Amazon Linux 2023）, nginx（1.26.3）, certbot, mw-php（8.3.*）, mw-laravel（11.*）, composer（2.8.6）, mw-mysql（8.4.5）, phpmyadmin（5.2.2） |
   | auction-agent-ec-maintenance | 2020-05 | （継続中） | linux, php, python, html-css, javascript, mysql |
   | job-site-maintenance | 2021-05 | 2024-04 | php, laravel |

3. 案件登録画面で各案件を開き、登録した期間・使用スキルが表示されることを確認する。
4. 出力タブで出力内容を生成し、経験年数がユニーク月数の積み上げで算出されていることを確認する。

### 3.6. カテゴリ表示順の調整

1. `skills` シートの行を、カテゴリが「OS」→「ミドルウェア」→（その他は3.4節で追加した順序どおり）
   となるよう並べ替える。カテゴリの表示順は各カテゴリの先頭行が現れる物理的な行順で決まるため、
   行の並べ替えによって調整する。
2. 案件登録画面のページタブが、OS・ミドルウェアを先頭とした順序で表示されることを確認する。
