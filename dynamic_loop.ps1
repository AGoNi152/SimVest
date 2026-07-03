param(
    [int]$IntervalMinutes = 60,
    [switch]$GenerateReport
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LogPath = Join-Path $ProjectRoot "dynamic_data.log"

while ($true) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$stamp] sync started" | Out-File -FilePath $LogPath -Append -Encoding utf8
    try {
        if ($GenerateReport) {
            & (Join-Path $ProjectRoot "scripts\update_data.ps1") -GenerateReport *>> $LogPath
        }
        else {
            & (Join-Path $ProjectRoot "scripts\update_data.ps1") *>> $LogPath
        }
    }
    catch {
        "[$stamp] sync failed: $($_.Exception.Message)" | Out-File -FilePath $LogPath -Append -Encoding utf8
    }
    Start-Sleep -Seconds ([Math]::Max(60, $IntervalMinutes * 60))
}
