# Delegates to cross-platform Python script.
$Py = Join-Path (Split-Path $PSScriptRoot -Parent) ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
& $Py (Join-Path $PSScriptRoot "setup_block_a.py") @args
exit $LASTEXITCODE
