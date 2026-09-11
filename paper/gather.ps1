# gather.ps1 — ERRE-Sandbox 内に散らばっている論文用の実データを paper/NN/ に集約する
#
#   使い方:  pwsh paper/gather.ps1            (ERRE-Sandbox の root から実行)
#            pwsh paper/gather.ps1 -WhatIf    (何をコピーするか見るだけ)
#
# 性質: **コピーのみ。元ファイルは一切動かさない。** 何度実行しても同じ結果になる。
# 集約が終わったら paper/move-out.ps1 で ERRE-Sandbox の外へ移す。
#
# 意図的にコピーしないもの:
#   - bank_records.jsonl (17.7 MB) → Zenodo にアップロードして DOI 参照にする
#   - .steering / .claude / .codex / loop の markdown → 研究 scaffolding は公開しない
#     (機械可読な verdict JSON だけは「証拠」として個別に抽出する)

#
# 移送後 (paper/move-out.ps1 実行済) でも動く:
#   paper/NN/ が消えていれば C:\ERRE-Papers\<repo>/ を宛先として解決する。
#   これが無いと移送後の gather が ERRE-Sandbox 内に**幽霊ディレクトリ**を作り直し、
#   本物の repo と静かに乖離する (2026-09-07 に実測して発覚)。
#
#   pwsh paper/gather.ps1 -Verify   # 何も書かず、原本とコピーの SHA-256 を突合するだけ

[CmdletBinding(SupportsShouldProcess)]
param(
    # 書き込みを一切せず、原本 ↔ コピー の一致だけを報告する
    [switch]$Verify,

    # 移送先の root (move-out.ps1 の -Destination と同じ既定)
    [string]$MovedRoot = 'C:\ERRE-Papers'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PaperRoot = Join-Path $RepoRoot 'paper'

# paper/NN の作業名 -> 移送先 repo 名 (move-out.ps1 の $Map と一致させること)
$MovedMap = @{
    '01-scorer-circularity'    = 'anchor-recognition-not-novelty'
    '02-powered-null'          = 'powered-null'
    '03-two-plane-determinism' = 'erre-paper-03-two-plane-determinism'
}

# 相対パス "01-scorer-circularity/data/raw/x.json" を実在する宛先へ解決する。
# paper/NN/ が在ればそこ、無ければ移送先。どちらも無ければ $null。
function Resolve-PaperDest {
    param([string]$Rel)

    $top  = $Rel.Split('/')[0]
    $rest = $Rel.Substring($top.Length).TrimStart('/')

    $inPlace = Join-Path $PaperRoot $top
    if (Test-Path $inPlace) {
        return [pscustomobject]@{ Path = (Join-Path $inPlace $rest); Moved = $false; Root = $inPlace }
    }
    if ($MovedMap.ContainsKey($top)) {
        $movedRootDir = Join-Path $MovedRoot $MovedMap[$top]
        if (Test-Path $movedRootDir) {
            return [pscustomobject]@{ Path = (Join-Path $movedRootDir $rest); Moved = $true; Root = $movedRootDir }
        }
    }
    return $null
}

$script:VerifyOk = 0; $script:VerifyDrift = 0; $script:VerifyMissing = 0

function Copy-Artifact {
    param([string]$From, [string]$To, [string]$Note)

    $src = Join-Path $RepoRoot $From

    if (-not (Test-Path $src)) {
        Write-Host "  [SKIP] $From (存在しない)" -ForegroundColor Yellow
        return
    }

    $resolved = Resolve-PaperDest -Rel $To
    if ($null -eq $resolved) {
        Write-Host "  [SKIP] $To (宛先が paper/ にも $MovedRoot にも無い)" -ForegroundColor Yellow
        return
    }
    $dst = $resolved.Path

    if ($Verify) {
        if (-not (Test-Path $dst)) {
            Write-Host "  [MISSING] $To (コピーが無い)" -ForegroundColor Red
            $script:VerifyMissing++
            return
        }
        $hs = (Get-FileHash -Algorithm SHA256 $src).Hash.ToLower()
        $hd = (Get-FileHash -Algorithm SHA256 $dst).Hash.ToLower()
        if ($hs -eq $hd) {
            Write-Host "  [MATCH] $To" -ForegroundColor Green
            $script:VerifyOk++
        } else {
            Write-Host "  [DRIFT] $To" -ForegroundColor Red
            Write-Host "          原本   $From = $($hs.Substring(0,16))..." -ForegroundColor Red
            Write-Host "          コピー $dst = $($hd.Substring(0,16))..." -ForegroundColor Red
            $script:VerifyDrift++
        }
        return
    }

    $dstDir = Split-Path -Parent $dst
    if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Force $dstDir | Out-Null }

    if ($PSCmdlet.ShouldProcess($To, "copy from $From")) {
        Copy-Item -Path $src -Destination $dst -Force
        $hash = (Get-FileHash -Algorithm SHA256 $dst).Hash.ToLower()
        $size = (Get-Item $dst).Length
        Write-Host "  [OK]   $To" -ForegroundColor Green
        # data-hashes.md 用の 1 行を溜める
        $script:HashRows += "| ``$To`` | ``$From`` | ``$hash`` | $size B | $Note |"
    }
}

$script:HashRows = @()

Write-Host "`n=== 01 scorer circularity ===" -ForegroundColor Cyan
Copy-Artifact 'experiments/20260701-es4-scorer-diag/diagnostic.json' '01-scorer-circularity/data/raw/diagnostic.json' 'Table 1 / Fig 2 の出典。本稿の心臓部'
Copy-Artifact 'experiments/20260630-es4-phase0/verdict-phase0.json'  '01-scorer-circularity/data/raw/verdict-phase0.json' 'ES-4 Phase 0 sealed run の verdict (INVALID_SCORER)'
Copy-Artifact 'experiments/20260630-es4-phase0/run-manifest.json'    '01-scorer-circularity/data/raw/phase0-run-manifest.json' 'Phase 0 run の来歴'
Copy-Artifact 'experiments/20260701-es4-scorer-diag/README.md'       '01-scorer-circularity/analysis/scripts/README.md' '実験の説明'
# --- 再現に要るもの (これが無いと repro.sh は原理的に exit 0 にならない) ---
Copy-Artifact 'scripts/es4_scorer_diag.py' '01-scorer-circularity/analysis/scripts/es4_scorer_diag.py' 'audit 本体 (897 行)。Table 1 を生む'
foreach ($f in @('generations.jsonl', 'judgements.jsonl', 'scores.jsonl', 'phase_a_manifest.json')) {
    Copy-Artifact "experiments/20260630-es4-phase0/phaseA/$f" "01-scorer-circularity/data/raw/phaseA/$f" 'Phase A 凍結入力 (audit の --run-dir)'
}
Copy-Artifact '.idea/paper-01-writing-spec.md'                       '01-scorer-circularity/manuscript/WRITING-SPEC.md' '本文の書き方の SSOT'

# --- G1 外部監査 (issue I-009: 可搬性) ---
#
# `analysis/scripts/paper01_external_audit.py` は自分の REPO_ROOT を
# `Path(__file__).resolve().parents[1]` (= 自分の 2 階層上) で計算する。
# 宛先を `analysis/scripts/` に置く以上、この REPO_ROOT は
# `01-scorer-circularity/` ではなく `01-scorer-circularity/analysis/` に解決する
# (実測で確認済み)。よって G1 の実験一式は `01-scorer-circularity/data/raw/` ではなく
# `01-scorer-circularity/analysis/experiments/20260907-paper01-g1/` 配下に、
# ERRE-Sandbox 側の相対構造 (`experiments/20260907-paper01-g1/...`) をそのまま
# 保って置く。`paper01_fetch_sources.py` の REPO_ROOT も同じ式なので同じ結論になる。
Copy-Artifact 'scripts/paper01_external_audit.py' '01-scorer-circularity/analysis/scripts/paper01_external_audit.py' '外部監査 CLI 本体 (二経路 import helper `resolve_sibling_script` を持つ)'
Copy-Artifact 'scripts/paper01_fetch_sources.py'  '01-scorer-circularity/analysis/scripts/paper01_fetch_sources.py' '取得スクリプト。sibling として同じディレクトリに置く (二経路 helper が効く条件)'
Copy-Artifact 'experiments/20260907-paper01-g1/data/raw/bowl AUT dataset.xlsx'      '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/data/raw/bowl AUT dataset.xlsx' 'Cambridge 原 xlsx (CC BY-NC-ND 4.0、byte 無改変同梱、DA-G1-3)'
Copy-Artifact 'experiments/20260907-paper01-g1/data/raw/paperclip AUT dataset.xlsx' '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/data/raw/paperclip AUT dataset.xlsx' 'Cambridge 原 xlsx (CC BY-NC-ND 4.0、byte 無改変同梱、DA-G1-3)'
Copy-Artifact 'experiments/20260907-paper01-g1/data/raw/NOTICE.md'                  '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/data/raw/NOTICE.md' 'CC BY-NC-ND 4.0 attribution。xlsx と同梱必須 (DA-G1-3)'
Copy-Artifact 'experiments/20260907-paper01-g1/data/source-audit.json'      '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/data/source-audit.json' 'Gate 0 の来歴。Ocsai は再配布しないので jsonl 本体は含まない (DA-G1-3)'
Copy-Artifact 'experiments/20260907-paper01-g1/results/external-audit.json' '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/results/external-audit.json' 'G1 の 5 つ組 + verdict (封印済 sealed run の記録)'
Copy-Artifact 'experiments/20260907-paper01-g1/results/fidelity.json'       '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/results/fidelity.json' '§2 fidelity pin (C0/C4 再現の記録)'
Copy-Artifact 'experiments/20260907-paper01-g1/results/metrics.json'        '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/results/metrics.json' 'build_metrics.py の read-only distillation の記録'
Copy-Artifact 'experiments/20260907-paper01-g1/config.json'  '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/config.json' '§9 事前登録の凍結値'
Copy-Artifact 'experiments/20260907-paper01-g1/SEED'         '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/SEED' 'PYTHONHASHSEED の来歴。run-external-audit.sh が読む'
Copy-Artifact 'experiments/20260907-paper01-g1/data.md'      '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/data.md' 'データ来歴の記述'
Copy-Artifact 'experiments/20260907-paper01-g1/env.md'       '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/env.md' '実行環境の記述'
Copy-Artifact 'experiments/20260907-paper01-g1/notes.md'     '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/notes.md' 'G1 の仮説・手続きノート'
Copy-Artifact 'experiments/20260907-paper01-g1/build_metrics.py' '01-scorer-circularity/analysis/experiments/20260907-paper01-g1/build_metrics.py' 'metrics.json を再生成する read-only distillation。run-external-audit.sh が呼ぶ'
foreach ($f in @('generations.jsonl', 'judgements.jsonl', 'scores.jsonl', 'phase_a_manifest.json')) {
    # 01 本体の diagnostic 用に `01-scorer-circularity/data/raw/phaseA/$f` へも
    # 既にコピーされている (上の "再現に要るもの" ブロック)。--fidelity が読む
    # PHASE_A_RUN_DIR は analysis/ 基準で別のパスに解決するため、同じ内容を
    # もう 1 か所へ複製する必要がある (元は 1 か所、コピー元は同じ byte 列)。
    Copy-Artifact "experiments/20260630-es4-phase0/phaseA/$f" "01-scorer-circularity/analysis/experiments/20260630-es4-phase0/phaseA/$f" 'G1 --fidelity (C0 heavy pin) 用の Phase A 凍結入力'
}

Write-Host "`n=== 02 powered null ===" -ForegroundColor Cyan
Copy-Artifact 'experiments/20260710-m13-c-proper/artifacts/verdict.json'           '02-powered-null/data/raw/cproper-verdict.json' '本稿の中核。NO_CHANNEL_CONFORMANCE / tv_bar=0.038065'
Copy-Artifact 'experiments/20260710-m13-c-proper/artifacts/manifest.json'          '02-powered-null/data/raw/cproper-manifest.json' 'run の来歴'
Copy-Artifact 'experiments/20260710-m13-c-proper/artifacts/bank_annotation.jsonl'  '02-powered-null/data/raw/bank_annotation.jsonl' '注釈付き bank (682 KB)'
Copy-Artifact 'experiments/20260629-m13-es3-locomotion/data/raw/verdict-forensic.json' '02-powered-null/data/raw/es3-verdict-forensic.json' 'ES-3 の機械可読 verdict (D_loco=0.0468)。原本は .steering/ (追跡外) にあり、2026-09-11 に experiments/ へ byte 無改変で退避した (B-P03-5 / DA-CIS-4)'
Copy-Artifact 'src/erre_sandbox/integration/embodied/bank_power.py'                '02-powered-null/analysis/scripts/bank_power.py' 'near-uniform 検出力の反証'

Write-Host "`n=== 共通 (01 / 02) ===" -ForegroundColor Cyan
foreach ($p in @('01-scorer-circularity', '02-powered-null')) {
    Copy-Artifact 'LICENSE'        "$p/LICENSE"          'Apache-2.0'
    Copy-Artifact 'LICENSE-MIT'    "$p/LICENSE-MIT"      'MIT (Apache-2.0 OR MIT)'
    Copy-Artifact 'uv.lock'        "$p/env/uv.lock"      '本体からコピー。依存を削ったら lock を打ち直す'
    Copy-Artifact 'pyproject.toml' "$p/env/pyproject.toml" '★ 本稿の解析に要る依存だけに削ること'
}

# --- apparatus の推移閉包 (パッケージパスを保って持ち出す) ---
#
# 平坦化した `apparatus/<mod>/` ではダメだった: コピーしたモジュールが
# `from erre_sandbox.evidence...` / `from erre_sandbox.schemas import ...` を
# import しているので、パッケージパスが崩れると **移送先で import が解決できない**
# (2026-09-07 に実測して発覚 — 01 は解析コードごと欠落、02 は import 不能だった)。
#
# 宛先は `<paper>/analysis/apparatus/erre_sandbox/...` = 原本と同じ相対パス。
# こうするとコピーは **原本と byte 一致のまま**なので provenance も -Verify も壊れない。
# 実行側は PYTHONPATH=analysis/apparatus を通すだけでよい。
Write-Host "`n=== apparatus 閉包 (01 / 02) ===" -ForegroundColor Cyan
foreach ($pair in @(@('01', '01-scorer-circularity'), @('02', '02-powered-null'))) {
    $num = $pair[0]; $paperDir = $pair[1]
    $listing = & python (Join-Path $PaperRoot '_closure.py') $num
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [SKIP] paper $num の閉包計算に失敗" -ForegroundColor Yellow
        continue
    }
    $n = 0
    foreach ($rel in $listing) {
        if ([string]::IsNullOrWhiteSpace($rel)) { continue }
        Copy-Artifact "src/$rel" "$paperDir/analysis/apparatus/$rel" 'apparatus 閉包 (自動列挙)'
        $n++
    }
    Write-Host "  paper $num : $n files" -ForegroundColor DarkGray
}

# --- paper repo 基準の runner を生成する (コピーではないので data-hashes には載せない) ---
if (-not $Verify) {
    $runner = @'
#!/usr/bin/env bash
# M13-ES4 scorer offline diagnostic — このリポジトリ単体で動く 1 コマンド再現 (CPU only)。
# gather.ps1 が生成する。ERRE-Sandbox の run.sh をそのままコピーするとパスが解決できない。
set -euo pipefail
cd "$(dirname "$0")/../.."
# PYTHONHASHSEED を固定しないと bit 再現しない (2026-09-07 実測):
# jaccard 候補が set[str] を反復するため float 加算順が変わり、bootstrap 再標本化で
# 増幅されて C5-jaccard-full の delta_ci_{lower,upper} が 4 桁目から動く。
# Table 1 の全列 (AUC / rarity_ok) と verdict は影響を受けないが、再現性のため固定する。
export PYTHONHASHSEED="$(cat SEED)"
PYTHONPATH=analysis/apparatus python analysis/scripts/es4_scorer_diag.py   --run-dir data/raw/phaseA   --out data/derived/diagnostic.json
echo "[repro] data/derived/diagnostic.json を生成。data/raw/diagnostic.json と突合すること。"
'@
    $rd = Resolve-PaperDest -Rel '01-scorer-circularity/analysis/scripts/run-diagnostic.sh'
    if ($null -ne $rd) {
        $dir = Split-Path -Parent $rd.Path
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
        if ($PSCmdlet.ShouldProcess('01 run-diagnostic.sh', 'generate (paper-repo relative)')) {
            Set-Content -Path $rd.Path -Value $runner -NoNewline -Encoding utf8
            Write-Host "  [GEN]  01-scorer-circularity/analysis/scripts/run-diagnostic.sh" -ForegroundColor Green
        }
    }

    # --- G1 外部監査の runner (issue I-009)。run-diagnostic.sh の verbatim コピーにしない:
    #   - cwd 基準・PYTHONPATH・PYTHONHASHSEED の取得元パスが違う (analysis/ 基準)
    #   - --fidelity は Phase A 凍結入力が同梱されているときだけ実行する (無ければ skip)
    #   - Ocsai は再配布していないので --audit 実行時にネットワーク取得が要る (DA-G1-3)
    #   - 本体 run.sh は byte-identity 二重実行 (~47分) までするが、本 runner の scope は
    #     「単体で exit 0」(G3 可搬性) のみ。決定性の再証明は本体側の I-008 実走で
    #     済んでいる (DA-G1-9: repro.sh 全体の緑化は scope 外) ので、--audit は 1 回だけ
    #     実行する (~23分、実測 CPU-only encoder)
    $externalAuditRunner = @'
#!/usr/bin/env bash
# paper01 G1 external audit -- このリポジトリ単体で動く 1 コマンド再現 (issue I-009)。
# gather.ps1 が生成する。ERRE-Sandbox の experiments/20260907-paper01-g1/run.sh を
# そのままコピーするとパスが解決できない (analysis/scripts/paper01_external_audit.py の
# REPO_ROOT は自分の 2 階層上、つまりこのリポジトリの analysis/ を指す。
# PYTHONPATH や SEED の場所もそれに合わせて作り直している)。
#
# 本体 run.sh との違い:
#   - --fidelity は analysis/experiments/20260630-es4-phase0/phaseA/ が同梱されている
#     ときだけ実行する (無ければ理由を出して skip する)
#   - --audit はネットワーク取得を伴う (Ocsai は再配布していない。DA-G1-3)。
#     両コーパスが揃わないと paper01_external_audit.py 自身が exit 1 を返す
#   - 本体 run.sh の byte-identity 二重実行はしない (決定性は I-008 実走で確認済み。
#     DA-G1-9 により repro.sh 全体の緑化は本 runner の scope 外)。--audit は 1 回だけ
#     実行する。実測 ~23分 (CPU-only encoder、real corpora)。tqdm の最新行でなく
#     この log の tail + completion marker で完了判定すること
#     (feedback_log_tail_completion_marker.md)
set -euo pipefail
cd "$(dirname "$0")/../.."

EXP_DIR="analysis/experiments/20260907-paper01-g1"
PHASE_A_DIR="analysis/experiments/20260630-es4-phase0/phaseA"
RESULTS_DIR="$EXP_DIR/results"
LOG_FILE="$RESULTS_DIR/run-external-audit.log"
mkdir -p "$RESULTS_DIR"

if [ -z "${PYTHON:-}" ]; then
  if [ -x ".venv/Scripts/python.exe" ]; then
    PYTHON=".venv/Scripts/python.exe"
  elif [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
  else
    PYTHON="python3"
  fi
fi
export PYTHON
export HF_HUB_OFFLINE=1
export PYTHONUTF8=1
export PYTHONPATH="analysis/apparatus"
export PYTHONHASHSEED="$(cat "$EXP_DIR/SEED")"

{
  echo "[run-external-audit] (1) PYTHON=$PYTHON PYTHONHASHSEED=$PYTHONHASHSEED PYTHONPATH=$PYTHONPATH"

  if [ -d "$PHASE_A_DIR" ] && [ -n "$(ls -A "$PHASE_A_DIR" 2>/dev/null)" ]; then
    echo "[run-external-audit] (2) --fidelity ($PHASE_A_DIR あり)"
    "$PYTHON" analysis/scripts/paper01_external_audit.py --fidelity
  else
    echo "[run-external-audit] (2) --fidelity skip -- $PHASE_A_DIR が無い (gather.ps1 が同梱していないか未再実行)"
  fi

  echo "[run-external-audit] (3) --audit -> $RESULTS_DIR/external-audit.json (~23分、CPU-only encoder、Ocsai はネットワーク取得)"
  "$PYTHON" analysis/scripts/paper01_external_audit.py --audit

  echo "[run-external-audit] (4) metrics.json (build_metrics.py, read-only distillation)"
  "$PYTHON" "$EXP_DIR/build_metrics.py"

  echo "[run-external-audit] (5) done"
  printf '%s\n' '{"event": "PAPER01_G1_EXTERNAL_AUDIT_RUN_COMPLETE", "status": "ok"}'
} 2>&1 | tee "$LOG_FILE"

exit "${PIPESTATUS[0]}"
'@
    $rea = Resolve-PaperDest -Rel '01-scorer-circularity/analysis/scripts/run-external-audit.sh'
    if ($null -ne $rea) {
        $dir = Split-Path -Parent $rea.Path
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
        if ($PSCmdlet.ShouldProcess('01 run-external-audit.sh', 'generate (paper-repo relative)')) {
            Set-Content -Path $rea.Path -Value $externalAuditRunner -NoNewline -Encoding utf8
            Write-Host "  [GEN]  01-scorer-circularity/analysis/scripts/run-external-audit.sh" -ForegroundColor Green
        }
    }
}

# --- Verify モードは集計だけ出して終わる (何も書かない) ---
if ($Verify) {
    $total = $script:VerifyOk + $script:VerifyDrift + $script:VerifyMissing
    Write-Host "`n--- verify 集計 ($total 件) ---" -ForegroundColor Cyan
    Write-Host "  一致 (MATCH)   : $($script:VerifyOk)"
    Write-Host "  乖離 (DRIFT)   : $($script:VerifyDrift)"
    Write-Host "  欠落 (MISSING) : $($script:VerifyMissing)"
    if ($script:VerifyDrift -gt 0 -or $script:VerifyMissing -gt 0) {
        Write-Host "`n  ★ 原本が更新されている / コピーが無い。gather を再実行するか、差分を確認すること。" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "`n  全て一致。移送済みリポジトリは原本と同期している。" -ForegroundColor Green
    exit 0
}

# --- hash 表を書き出す ---
if (-not $WhatIfPreference -and $script:HashRows.Count -gt 0) {
    $commit = (git -C $RepoRoot rev-parse HEAD).Trim()
    $stamp  = Get-Date -Format 'yyyy-MM-dd'
    $out = @(
        '# data hashes (gather.ps1 が自動生成 — 手で編集しない)',
        '',
        "生成日: $stamp / ERRE-Sandbox commit: ``$commit``",
        '',
        '| 移送先 | 元のパス | SHA-256 | サイズ | 備考 |',
        '|---|---|---|---|---|'
    ) + $script:HashRows
    $outPath = Join-Path $PaperRoot 'data-hashes.md'
    $out | Set-Content -Path $outPath -Encoding utf8
    Write-Host "`n[OK] $outPath を生成 ($($script:HashRows.Count) 件)" -ForegroundColor Green
    Write-Host "     → 各論文の data/data.md に該当行を転記すること" -ForegroundColor DarkGray
}

Write-Host "`n--- 意図的にコピーしていないもの ---" -ForegroundColor Magenta
Write-Host "  bank_records.jsonl (17.7 MB) : Zenodo にアップロードし DOI 参照にする"
Write-Host "  .steering/*.md               : 研究 scaffolding。公開しない"
Write-Host "  .idea/paper-candidates-survey.md : 他論文の内部評価を含むため持ち込まない"
Write-Host "`n次: pwsh paper/move-out.ps1  (ERRE-Sandbox の外へ移す)`n"
