# AIIS v2 (Backend V2 + web app) -> Vercel project "aiis" (aiis-livid.vercel.app)
# Sets the backend's environment variables from backend_v2\.env (never uploaded), then deploys.
$ErrorActionPreference = 'Continue'
Set-Location -Path $PSScriptRoot
$log = Join-Path $PSScriptRoot 'vercel-log.txt'
Set-Content -Path $log -Value "=== AIIS v2 deploy $(Get-Date -Format s) ===" -Encoding utf8
function Say([string]$t) { Write-Host $t; Add-Content -Path $log -Value $t -Encoding utf8 }
function Run([string]$label, [scriptblock]$cmd) {
  Say "`n--- $label ---"
  & $cmd 2>&1 | ForEach-Object { Say ("$_") }
  Say "[exit $LASTEXITCODE]"
}
$scope = 'sushanth-s-projects-e4df5bc8'
$prefix = (& npm prefix -g).Trim()
$vc = Join-Path $prefix 'vercel.cmd'
if (-not (Test-Path $vc)) { $vc = 'D:\npm-global\vercel.cmd' }
Say "CLI path: $vc"
Run 'who am I' { & $vc whoami }
Run 'link folder to aiis' { & $vc link --yes --project aiis --scope $scope }

# Environment variables (values are read from the local file and never printed)
$envFile = Join-Path $PSScriptRoot 'backend_v2\.env'
$skip = @('DATABASE_URL')
$vars = @{}
Get-Content $envFile | ForEach-Object {
  $l = $_.Trim()
  if ($l -and -not $l.StartsWith('#') -and $l.Contains('=')) {
    $k, $v = $l.Split('=', 2); $k = $k.Trim(); $v = $v.Trim().Trim('"').Trim("'")
    if ($v -and -not ($skip -contains $k)) { $vars[$k] = $v }
  }
}
$vars['FLASK_ENV'] = 'production'
$vars['CORS_ORIGINS'] = 'https://aiis-livid.vercel.app,https://aiis.vercel.app,http://localhost:5000'
foreach ($k in $vars.Keys) {
  foreach ($t in @('production', 'preview')) {
    & $vc env rm $k $t --yes --scope $scope *> $null
    $vars[$k] | & $vc env add $k $t --scope $scope *> $null
    Say "env $k ($t): exit $LASTEXITCODE"
  }
}
Run 'env list' { & $vc env ls --scope $scope }
Run 'deploy to production' { & $vc deploy --prod --yes --scope $scope }
Say "`n=== finished $(Get-Date -Format s) ==="
Write-Host "`nDone. You can close this window." -ForegroundColor Green
Start-Sleep -Seconds 5
