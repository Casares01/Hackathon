$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.runtime\python.exe'
if (Test-Path -LiteralPath $projectPython) {
    & $projectPython -m streamlit run app.py
} else {
    python -m streamlit run app.py
}
