# Chay Observathon bang OpenRouter

`solution/config.json` da dung provider OpenAI-compatible va model
`openai/gpt-4o-mini` tren OpenRouter.

Trong PowerShell, dat API key cho phien hien tai:

```powershell
$env:OPENROUTER_API_KEY = "sk-or-v1-..."
```

Sau khi them Windows binary vao `bin/practice/`, chay:

```powershell
.\run_openrouter.ps1
```

## Chay Linux binary bang Docker Desktop tren Windows

Giai nen ban Linux x64 va dat file khong co duoi `.exe` tai:

```text
bin/practice/observathon-sim
```

Mo Docker Desktop, cho Docker Engine khoi dong xong, sau do chay:

```powershell
$env:OPENROUTER_API_KEY = "sk-or-v1-..."
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_openrouter_docker.ps1
```

Script tu dong mount thu muc project hien tai vao `/lab`, cap quyen execute cho
binary Linux va ghi ket qua ve `run_output.json` trong project. Khong can sua
duong dan `D:\AI_Vin\...` trong lenh Docker.

Co the doi phase, output hoac concurrency:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_openrouter_docker.ps1 `
  -Phase practice -Output run_output.json -Concurrency 8
```

Tao traffic tuy chinh, vi du 20 users, moi user 5 turns (100 requests):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_openrouter.ps1 `
  -Users 20 -Turns 5 -Concurrency 8
```

Co the them `-Rps 10` de dieu khien toc do request va `-Seed 1234` de lap lai
cung mot bo traffic. Neu bo `-Users` va `-Turns`, simulator chay fixed test set.

## Chay va cham public/private

Public/private phai dung simulator dung phase va fixed test set, khong truyen
`Users`, `Turns`, `Rps` hoac `Seed`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_openrouter.ps1 `
  -Phase public -Output run_output_public.json -Concurrency 8
```

Sau khi co public scorer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_score.ps1 `
  -Phase public -Run run_output_public.json -Output score_public.json
```

Hai script se tu choi neu phase trong output khong khop, run rong, hoac scorer
tra ve `n=0`. Khong sao chep practice simulator vao `bin/public`/`bin/private`.

Chay phase khac hoac doi concurrency:

```powershell
.\run_openrouter.ps1 -Phase public -Concurrency 8
```

Script anh xa key sang bien `OPENAI_API_KEY` va dat endpoint
`https://openrouter.ai/api/v1`, vi simulator chi cong khai giao dien provider
OpenAI-compatible. Khong dat API key trong `solution/config.json`, `.env`, commit,
log hoac anh chup man hinh.
