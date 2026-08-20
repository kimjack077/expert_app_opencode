$ErrorActionPreference = 'SilentlyContinue'

Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/c','npm','run','dev' `
    -WorkingDirectory 'd:\software\expert_app_opencode\web-admin' `
    -WindowStyle Hidden `
    -RedirectStandardOutput 'd:\software\expert_app_opencode\web-admin\web-admin.log' `
    -RedirectStandardError 'd:\software\expert_app_opencode\web-admin\web-admin.err.log'

Start-Sleep -Seconds 15

$conn = Get-NetTCPConnection -LocalPort 3000 -State Listen
if ($conn) {
    Write-Host "WEB-ADMIN UP: PID $($conn.OwningProcess) on port 3000"
} else {
    Write-Host "WEB-ADMIN DOWN"
    Write-Host "--- log ---"
    Get-Content 'd:\software\expert_app_opencode\web-admin\web-admin.log' -Tail 30
    Write-Host "--- err ---"
    Get-Content 'd:\software\expert_app_opencode\web-admin\web-admin.err.log' -Tail 30
}
