param(
    [ValidateSet("public", "private")]
    [string]$Phase = "public",

    [ValidatePattern('^[A-Za-z0-9_.-]+$')]
    [string]$Run = "run_output_public.json",

    [ValidatePattern('^[A-Za-z0-9_.-]+$')]
    [string]$Output = "score_public.json",

    [ValidatePattern('^[A-Za-z0-9_-]+$')]
    [string]$Team = "NguyenAnhChuc",

    [string]$Image = "python:3.12-slim"
)

$ErrorActionPreference = "Stop"

$runPath = Join-Path $PSScriptRoot $Run
$scoreBinary = Join-Path $PSScriptRoot "bin\$Phase\observathon-score"
$findingsPath = Join-Path $PSScriptRoot "solution\findings.json"

if (-not (Test-Path -LiteralPath $runPath -PathType Leaf)) {
    throw "Run output not found: $runPath"
}
if (-not (Test-Path -LiteralPath $scoreBinary -PathType Leaf)) {
    throw "Linux scorer binary not found: $scoreBinary"
}
if (-not (Test-Path -LiteralPath $findingsPath -PathType Leaf)) {
    throw "Findings file not found: $findingsPath"
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install and start Docker Desktop first."
}

$runData = Get-Content -Raw -LiteralPath $runPath | ConvertFrom-Json
if ($runData.phase -ne $Phase) {
    throw "Cannot score phase '$Phase': $Run contains phase '$($runData.phase)'. Run the correct $Phase simulator first."
}
if ([int]$runData.n -le 0 -or @($runData.results).Count -le 0) {
    throw "Cannot score an empty run: $Run"
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Engine is unavailable. Start Docker Desktop and wait until it is ready."
}

$temporaryOutput = ".$Output.$PID.tmp"
$command = @"
set -eu
chmod +x 'bin/$Phase/observathon-score'
exec './bin/$Phase/observathon-score' \
  --run '$Run' \
  --findings 'solution/findings.json' \
  --team '$Team' \
  --phase '$Phase' \
  --out '$temporaryOutput'
"@

& docker run --rm `
    --mount "type=bind,source=$PSScriptRoot,target=/lab" `
    --workdir /lab `
    $Image `
    bash -lc $command

if ($LASTEXITCODE -ne 0) {
    throw "Observathon scorer exited with code $LASTEXITCODE."
}

$scorePath = Join-Path $PSScriptRoot $Output
$temporaryScorePath = Join-Path $PSScriptRoot $temporaryOutput
if (-not (Test-Path -LiteralPath $temporaryScorePath -PathType Leaf)) {
    throw "Scorer did not create the expected output: $temporaryScorePath"
}

$score = Get-Content -Raw -LiteralPath $temporaryScorePath | ConvertFrom-Json
if ([int]$score.n -le 0) {
    Remove-Item -LiteralPath $temporaryScorePath -Force
    throw "Scorer produced n=0. Verify that the simulator and scorer belong to the same phase release."
}
if ($score.phase -ne $Phase) {
    Remove-Item -LiteralPath $temporaryScorePath -Force
    throw "Scorer phase mismatch: requested '$Phase' but output contains '$($score.phase)'."
}

Move-Item -LiteralPath $temporaryScorePath -Destination $scorePath -Force

Write-Host "Score complete: headline=$($score.headline), n=$($score.n)"
Write-Host "Output: $scorePath"
