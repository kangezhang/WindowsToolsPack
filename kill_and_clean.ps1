Stop-Process -Name "backend" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$t = "C:\Users\zhangkang\Documents\Tools\WindowsToolsPack\dist\win-unpacked"
if (Test-Path $t) { Remove-Item -Recurse -Force $t; Write-Host "removed" } else { Write-Host "gone" }
