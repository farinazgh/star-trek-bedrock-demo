# Agent Core Migration Setup Script
# This script helps you get started with Agent Core migration

Write-Host " Star Trek Agent Core Migration Setup" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host " Checking prerequisites..." -ForegroundColor Yellow

# Check Node.js
$nodeVersion = node --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host " Node.js not found. Please install Node.js 20+ from https://nodejs.org" -ForegroundColor Red
    exit 1
}
Write-Host " Node.js: $nodeVersion" -ForegroundColor Green

# Check npm
$npmVersion = npm --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host " npm not found" -ForegroundColor Red
    exit 1
}
Write-Host " npm: v$npmVersion" -ForegroundColor Green

# Check Python
$pythonVersion = python --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python not found on 'python', trying 'python3'..." -ForegroundColor Yellow
    $pythonVersion = python3 --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host " Python not found. Please install Python 3.10+" -ForegroundColor Red
        exit 1
    }
}
Write-Host " Python: $pythonVersion" -ForegroundColor Green

# Check AWS credentials
Write-Host ""
Write-Host " Checking AWS credentials..." -ForegroundColor Yellow
$awsIdentity = aws sts get-caller-identity 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host " AWS credentials not configured. Run 'aws configure' first." -ForegroundColor Red
    exit 1
}
$accountId = ($awsIdentity | ConvertFrom-Json).Account
Write-Host " AWS Account: $accountId" -ForegroundColor Green

# Check for existing agentcore CLI
Write-Host ""
Write-Host " Checking Agent Core CLI..." -ForegroundColor Yellow
$agentcoreVersion = agentcore --version 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host " Agent Core CLI already installed: $agentcoreVersion" -ForegroundColor Green
} else {
    Write-Host " Installing Agent Core CLI..." -ForegroundColor Yellow
    npm install -g @aws/agentcore
    if ($LASTEXITCODE -ne 0) {
        Write-Host " Failed to install Agent Core CLI" -ForegroundColor Red
        exit 1
    }
    Write-Host " Agent Core CLI installed successfully" -ForegroundColor Green
}

Write-Host ""
Write-Host " All prerequisites met!" -ForegroundColor Green
Write-Host ""

# Prompt for project creation
Write-Host " Ready to create Agent Core project" -ForegroundColor Cyan
Write-Host ""
Write-Host "Options:" -ForegroundColor White
Write-Host "1. Create new project with interactive wizard (recommended for first-time)" -ForegroundColor White
Write-Host "2. Create project with preset configuration (quick start)" -ForegroundColor White
Write-Host "3. Skip project creation (I'll do it manually)" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Choose option (1-3)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host " Launching interactive wizard..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Recommended answers for Star Trek demo migration:" -ForegroundColor Cyan
        Write-Host "- What do you want to build? -> Agent" -ForegroundColor White
        Write-Host "- Framework? -> Strands Agents" -ForegroundColor White
        Write-Host "- Model provider? -> Amazon Bedrock" -ForegroundColor White
        Write-Host "- Memory? -> Long-term and short-term" -ForegroundColor White
        Write-Host "- Build type? -> CodeZip" -ForegroundColor White
        Write-Host ""

        # Navigate to parent directory
        $parentDir = Split-Path -Parent $PSScriptRoot
        Set-Location $parentDir

        agentcore create
    }
    "2" {
        Write-Host ""
        Write-Host " Creating project with preset configuration..." -ForegroundColor Yellow

        # Navigate to parent directory
        $parentDir = Split-Path -Parent $PSScriptRoot
        Set-Location $parentDir

        agentcore create `
            --project-name star-trek-agentcore `
            --name DataRAGAgent `
            --language Python `
            --framework Strands `
            --model-provider Bedrock `
            --memory longAndShortTerm `
            --build CodeZip

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host " Project created successfully!" -ForegroundColor Green
            Write-Host ""
            Write-Host " Project location: $parentDir\star-trek-agentcore" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "Next steps:" -ForegroundColor Yellow
            Write-Host "1. cd ..\star-trek-agentcore" -ForegroundColor White
            Write-Host "2. agentcore dev           # Test locally with hot reload" -ForegroundColor White
            Write-Host "3. agentcore deploy        # Deploy to AWS" -ForegroundColor White
            Write-Host "4. agentcore invoke --prompt 'Do you experience emotions?'" -ForegroundColor White
        }
    }
    "3" {
        Write-Host ""
        Write-Host " Skipping project creation" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To create manually later:" -ForegroundColor White
        Write-Host "agentcore create" -ForegroundColor Cyan
    }
    default {
        Write-Host " Invalid choice" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host " Migration guide available at:" -ForegroundColor Cyan
Write-Host "$PSScriptRoot\AGENTCORE_MIGRATION.md" -ForegroundColor White
Write-Host ""
Write-Host " Setup complete! Happy building!" -ForegroundColor Green
