$ErrorActionPreference = 'SilentlyContinue'

Start-Process -FilePath 'd:\software\expert_app_opencode\backend\.venv\Scripts\python.exe' `
    -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' `
    -WorkingDirectory 'd:\software\expert_app_opencode\backend' `
    -WindowStyle Hidden `
    -RedirectStandardOutput 'd:\software\expert_app_opencode\backend\backend.log' `
    -RedirectStandardError 'd:\software\expert_app_opencode\backend\backend.err.log'

Start-Sleep -Seconds 8

$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen
if ($conn) {
    Write-Host "BACKEND UP: PID $($conn.OwningProcess)"
} else {
    Write-Host "BACKEND DOWN"
    Write-Host "--- err log ---"
    Get-Content 'd:\software\expert_app_opencode\backend\backend.err.log'
}
