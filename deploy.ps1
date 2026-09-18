# deploy.ps1 - Run from project root after aws configure
# Usage: .\deploy.ps1

Write-Host "=== Adhikar AI Deploy ===" -ForegroundColor Cyan

# 1. Backend
Write-Host "`n[1/3] Building SAM backend..." -ForegroundColor Yellow
Set-Location backend
sam build
if ($LASTEXITCODE -ne 0) { Write-Error "sam build failed"; exit 1 }

Write-Host "`n[2/3] Deploying to AWS (us-east-1)..." -ForegroundColor Yellow
sam deploy `
  --stack-name adhikar-ai `
  --region us-east-1 `
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM `
  --resolve-s3 `
  --no-confirm-changeset `
  --no-fail-on-empty-changeset
if ($LASTEXITCODE -ne 0) { Write-Error "sam deploy failed"; exit 1 }

# 2. Capture API URL
Write-Host "`n[3/3] Capturing API URL..." -ForegroundColor Yellow
$apiUrl = aws cloudformation describe-stacks `
  --stack-name adhikar-ai `
  --region us-east-1 `
  --query "Stacks[0].Outputs[?OutputKey=='HealthUrl'].OutputValue" `
  --output text
$apiUrl = $apiUrl -replace "/Prod/health", ""

Write-Host "`nAPI Base URL: $apiUrl" -ForegroundColor Green

# Write to frontend .env.local
Set-Location ..\frontend
$envContent = "NEXT_PUBLIC_API_URL=$apiUrl/Prod`nNEXT_PUBLIC_REGION=us-east-1"
[System.IO.File]::WriteAllText(".env.local", $envContent)
Write-Host ".env.local written with API URL" -ForegroundColor Green

Set-Location ..
Write-Host "`n=== Deploy complete ===" -ForegroundColor Cyan
Write-Host "Test: curl $apiUrl/Prod/health" -ForegroundColor White
Write-Host "Next: cd frontend && npm run dev" -ForegroundColor White