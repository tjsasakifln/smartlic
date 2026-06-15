<#
.SYNOPSIS
    Executa OWASP ZAP contra um alvo (staging/producao) via Docker.
.DESCRIPTION
    Script PowerShell para executar OWASP ZAP scan em ambientes Windows.
    Suporta modos full, quick e api.

    Requisitos:
    - Docker Desktop instalado e em execucao
    - Portas 8080 e 8081 disponiveis

.PARAMETER Target
    URL do alvo (obrigatorio). Ex: https://staging.smartlic.tech
.PARAMETER Mode
    Modo de scan: full (padrao), quick, ou api
.PARAMETER OutputDir
    Diretorio para salvar relatorios (padrao: ./zap-reports)

.EXAMPLE
    .\run-zap-scan.ps1 -Target "https://staging.smartlic.tech" -Mode full
.EXAMPLE
    .\run-zap-scan.ps1 -Target "https://staging.smartlic.tech" -Mode quick -OutputDir .\reports
.EXAMPLE
    .\run-zap-scan.ps1 -Target "https://api.smartlic.tech/openapi.json" -Mode api
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Target,

    [ValidateSet("full", "quick", "api")]
    [string]$Mode = "full",

    [string]$OutputDir = ".\zap-reports"
)

$ErrorActionPreference = "Stop"
$ZAPImage = "ghcr.io/zaproxy/zaproxy:stable"
$ZapPort = 8080
$ZapPortApi = 8081
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ContainerName = "zap-scan-$Timestamp"

# --- Validacoes ---
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker nao encontrado. Instale Docker Desktop primeiro."
    exit 1
}

try {
    $null = docker info 2>&1 | Out-Null
} catch {
    Write-Error "Docker daemon nao esta em execucao."
    exit 1
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$ReportBase = Join-Path $OutputDir "zap-report-$Timestamp"

Write-Host "=== OWASP ZAP Scan ===" -ForegroundColor Cyan
Write-Host "Target:  $Target" -ForegroundColor White
Write-Host "Mode:    $Mode" -ForegroundColor White
Write-Host "Output:  $OutputDir" -ForegroundColor White
Write-Host ""

# --- Cleanup ---
function Cleanup {
    Write-Host "[INFO] Limpando container ZAP..." -ForegroundColor Blue
    docker stop $ContainerName 2>$null | Out-Null
    docker rm $ContainerName 2>$null | Out-Null
}
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup } | Out-Null

# --- Start ZAP ---
Write-Host "[INFO] Iniciando ZAP container..." -ForegroundColor Blue
docker run --rm -d `
    --name $ContainerName `
    -p ${ZapPort}:8080 `
    -p ${ZapPortApi}:8081 `
    -v "${PWD}\${OutputDir}:/zap/wrk" `
    $ZAPImage `
    zap.sh -daemon -port 8080 -host 0.0.0.0 `
    -config api.disablekey=true `
    -config api.addrs.addr.name=.* `
    -config api.addrs.addr.regex=true

# Aguardar ZAP iniciar
Write-Host "[INFO] Aguardando ZAP iniciar (ate 30s)..." -ForegroundColor Blue
$ready = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:${ZapPortApi}" -Method GET -TimeoutSec 2
        Write-Host "[OK] ZAP pronto (${i}s)" -ForegroundColor Green
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Write-Error "ZAP nao iniciou apos 30s. Verifique logs do container."
    docker logs $ContainerName --tail 20
    exit 2
}

# --- Execute scan ---
switch ($Mode) {
    "full" {
        Write-Host "[INFO] Modo FULL: spider + active scan" -ForegroundColor Blue

        Write-Host "[INFO] Passo 1/4: Spider tradicional..." -ForegroundColor Blue
        docker exec $ContainerName zap-cli -p 8080 spider "$Target"

        Write-Host "[INFO] Passo 2/4: Spider AJAX (SPA)..." -ForegroundColor Blue
        $null = Invoke-WebRequest -Uri "http://localhost:${ZapPortApi}/JSON/spiderAjax/action/scan/?url=$Target&maxChildren=10" -Method GET

        Write-Host "[INFO] Passo 3/4: Active scan (OWASP Top 10 + API Top 10)..." -ForegroundColor Blue
        docker exec $ContainerName zap-cli -p 8080 active-scan --scanners all "$Target"

        Write-Host "[INFO] Passo 4/4: Exportando relatorios..." -ForegroundColor Blue
        Invoke-WebRequest -Uri "http://localhost:${ZapPortApi}/OTHER/core/other/htmlreport/" -OutFile "${ReportBase}.html"
        Invoke-WebRequest -Uri "http://localhost:${ZapPortApi}/OTHER/core/other/xmlreport/" -OutFile "${ReportBase}.xml"
        Invoke-WebRequest -Uri "http://localhost:${ZapPortApi}/JSON/core/view/alerts/" -OutFile "${ReportBase}.json"
    }

    "quick" {
        Write-Host "[INFO] Modo QUICK: passive scan + spider" -ForegroundColor Blue

        Write-Host "[INFO] Passo 1/2: Spider tradicional..." -ForegroundColor Blue
        docker exec $ContainerName zap-cli -p 8080 spider "$Target"

        Write-Host "[INFO] Passo 2/2: Coletando alertas passive scan..." -ForegroundColor Blue
        Start-Sleep -Seconds 10
        Invoke-WebRequest -Uri "http://localhost:${ZapPortApi}/JSON/core/view/alerts/" -OutFile "${ReportBase}.json"
        Invoke-WebRequest -Uri "http://localhost:${ZapPortApi}/OTHER/core/other/htmlreport/" -OutFile "${ReportBase}.html"
    }

    "api" {
        Write-Host "[INFO] Modo API: import OpenAPI + scan endpoints" -ForegroundColor Blue

        Write-Host "[INFO] Passo 1/3: Importando OpenAPI spec..." -ForegroundColor Blue
        $body = @{ url = $Target }
        $null = Invoke-WebRequest -Uri "http://localhost:${ZapPortApi}/JSON/openapi/action/importUrl/" -Method POST -Body $body

        Write-Host "[INFO] Passo 2/3: Active scan em endpoints descobertos..." -ForegroundColor Blue
        docker exec $ContainerName zap-cli -p 8080 active-scan --scanners all "$Target"

        Write-Host "[INFO] Passo 3/3: Exportando relatorios..." -ForegroundColor Blue
        Invoke-WebRequest -Uri "http://localhost:${ZapPortApi}/JSON/core/view/alerts/" -OutFile "${ReportBase}.json"
        Invoke-WebRequest -Uri "http://localhost:${ZapPortApi}/OTHER/core/other/htmlreport/" -OutFile "${ReportBase}.html"
    }
}

# --- Summary ---
Write-Host "[OK] Scan concluido!" -ForegroundColor Green
Write-Host "Relatorios salvos em:" -ForegroundColor White
Write-Host "  HTML: ${ReportBase}.html" -ForegroundColor White
Write-Host "  JSON: ${ReportBase}.json" -ForegroundColor White
if (Test-Path "${ReportBase}.xml") {
    Write-Host "  XML:  ${ReportBase}.xml" -ForegroundColor White
}

# Parse alert count if JSON available
if (Test-Path "${ReportBase}.json") {
    try {
        $json = Get-Content "${ReportBase}.json" -Raw | ConvertFrom-Json
        $alerts = $json.alerts
        Write-Host "Resumo de alertas:" -ForegroundColor White
        Write-Host "  Total: $($alerts.Count)" -ForegroundColor White
        foreach ($alert in $alerts) {
            Write-Host "  [$($alert.risk)] $($alert.name)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  (parse manual do JSON)" -ForegroundColor Yellow
    }
}

Cleanup
Write-Host "[OK] Scan finalizado com sucesso em $(Get-Date)" -ForegroundColor Green
exit 0
