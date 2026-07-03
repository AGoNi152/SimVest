param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000
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
$LogPath = Join-Path $ProjectRoot "server.log"

Set-Location -LiteralPath $ProjectRoot
& $Python -m simvest.server --host $HostName --port $Port *> $LogPath
