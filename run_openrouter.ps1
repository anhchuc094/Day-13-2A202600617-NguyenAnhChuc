param(
    [ValidateSet("practice", "public", "private")]
    [string]$Phase = "practice",

    [ValidatePattern('^[A-Za-z0-9_.-]+$')]
    [string]$Output = "run_output.json",

    [ValidateRange(1, 128)]
    [int]$Concurrency = 8,

    [ValidateRange(1, 100000)]
    [int]$Users = 0,

    [ValidateRange(1, 10000)]
    [int]$Turns = 0,

    [ValidateRange(0.01, 100000)]
    [double]$Rps = 0,

    [Nullable[int]]$Seed = $null,

    [string]$Image = "python:3.12-slim"
)

$ErrorActionPreference = "Stop"

if (-not $env:OPENROUTER_API_KEY) {
    throw @"
Missing OPENROUTER_API_KEY.
Set it in this PowerShell session first:
  `$env:OPENROUTER_API_KEY = "sk-or-v1-..."
"@
}

if (($Users -gt 0) -xor ($Turns -gt 0)) {
    throw "Custom traffic requires both -Users and -Turns."
}

if ($Phase -ne "practice" -and ($Users -gt 0 -or $Turns -gt 0 -or $Rps -gt 0 -or $null -ne $Seed)) {
    throw "Custom traffic is for practice only. Public/private scoring must use the fixed test set."
}

$binary = Join-Path $PSScriptRoot "bin\$Phase\observathon-sim"
if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) {
    throw "Linux simulator binary not found: $binary"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install and start Docker Desktop first."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Engine is unavailable. Start Docker Desktop and wait until it is ready."
}

# The simulator uses the OpenAI client. These variables redirect that client
# to OpenRouter while keeping the OpenRouter key out of tracked files.
$env:OPENAI_API_KEY = $env:OPENROUTER_API_KEY
$env:OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
$env:OPENAI_API_BASE = $env:OPENAI_BASE_URL

$trafficArgs = @()
if ($Users -gt 0) {
    $trafficArgs += "--users '$Users'"
}
if ($Turns -gt 0) {
    $trafficArgs += "--turns '$Turns'"
}
if ($Rps -gt 0) {
    $trafficArgs += "--rps '$($Rps.ToString([Globalization.CultureInfo]::InvariantCulture))'"
}
if ($null -ne $Seed) {
    $trafficArgs += "--seed '$Seed'"
}
$trafficCommand = $trafficArgs -join " "
$temporaryOutput = ".$Output.$PID.tmp"
$phaseCommand = if ($Phase -eq "practice") { "--practice" } else { "--testset '$Phase'" }

$containerCommand = @"
set -eu
chmod +x 'bin/$Phase/observathon-sim'
exec './bin/$Phase/observathon-sim' \
  --config 'solution/config.json' \
  --wrapper 'solution/wrapper.py' \
  --out '$temporaryOutput' \
  --concurrency '$Concurrency' \
  $phaseCommand \
  $trafficCommand
"@

Write-Host "Running Observathon through OpenRouter in Docker..."
Write-Host "Model: $((Get-Content -Raw (Join-Path $PSScriptRoot 'solution\config.json') | ConvertFrom-Json).model)"
if ($Users -gt 0 -or $Turns -gt 0) {
    Write-Host "Traffic: users=$Users, turns=$Turns, concurrency=$Concurrency, rps=$Rps"
} else {
    Write-Host "Traffic: fixed test set, concurrency=$Concurrency"
}

& docker run --rm `
    --mount "type=bind,source=$PSScriptRoot,target=/lab" `
    --workdir /lab `
    --env OPENAI_API_KEY `
    --env OPENAI_BASE_URL `
    --env OPENAI_API_BASE `
    $Image `
    bash -lc $containerCommand

if ($LASTEXITCODE -ne 0) {
    throw "Observathon exited with code $LASTEXITCODE."
}

$outputPath = Join-Path $PSScriptRoot $Output
$temporaryOutputPath = Join-Path $PSScriptRoot $temporaryOutput
if (-not (Test-Path -LiteralPath $temporaryOutputPath)) {
    throw "Simulator did not create the expected output: $temporaryOutputPath"
}

$run = Get-Content -Raw -LiteralPath $temporaryOutputPath | ConvertFrom-Json
if ($run.phase -ne $Phase) {
    Remove-Item -LiteralPath $temporaryOutputPath -Force
    throw "Phase mismatch: requested '$Phase' but the binary produced '$($run.phase)'. Download the correct $Phase simulator binary. Existing output was not overwritten."
}

$nonOk = @($run.results | Where-Object { $_.status -ne "ok" })
if ([int]$run.n -gt 0 -and $nonOk.Count -eq [int]$run.n) {
    $failedName = ".$Output.failed-$PID.json"
    $failedPath = Join-Path $PSScriptRoot $failedName
    Move-Item -LiteralPath $temporaryOutputPath -Destination $failedPath -Force
    throw "All $($run.n) requests failed. Existing output was not overwritten. Failed run: $failedPath. Check logs for wrapper_error details (for example OpenRouter 401/402/403)."
}

Move-Item -LiteralPath $temporaryOutputPath -Destination $outputPath -Force
Write-Host "Finished: $($run.n) results, $($nonOk.Count) non-ok."
Write-Host "Output: $outputPath"
