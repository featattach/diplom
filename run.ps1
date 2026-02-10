# Запуск сервера (разработка, с автоперезагрузкой)
# Запуск: .\run.ps1   или из корня: powershell -File run.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root
if (Test-Path ".venv\Scripts\Activate.ps1") {
    .\.venv\Scripts\Activate.ps1
}
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
