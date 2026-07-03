param(
    [switch]$GenerateReport
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($PythonCommand) {
    $Python = $PythonCommand.Source
}
else {
    $Python = "C:\Users\sheng\AppData\Local\Programs\Python\Python312\python.exe"
}

Set-Location -LiteralPath $ProjectRoot
if ($GenerateReport) {
    & $Python -m simvest.sync_data --generate-report
}
else {
    & $Python -m simvest.sync_data
}
