$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptRoot 'lib.ps1')

$projectRoot = Get-ProjectRoot -ScriptRoot $ScriptRoot
$config = Load-Config -ProjectRoot $projectRoot
$pythonExe = Ensure-Venv -ProjectRoot $projectRoot -Config $config

Write-Section '프로젝트 자동 설정 시작'
Write-Host "프로젝트 경로: $projectRoot"
Write-Host "Python 경로: $pythonExe"

Write-Section '필수 패키지 설치'
$installExit = Invoke-CommandTemplate -Template 'python -m pip install --upgrade pip' -PythonExe $pythonExe -Port ([int]$config.server_port) -WorkingDirectory $projectRoot -LogPrefix 'pip'
if ($installExit -ne 0) {
    Write-Warning 'pip 업그레이드에 실패했습니다. 기존 pip 로 계속 진행합니다.'
}
if (Test-Path (Join-Path $projectRoot 'requirements.txt')) {
    $reqExit = Invoke-CommandTemplate -Template 'python -m pip install -r requirements.txt' -PythonExe $pythonExe -Port ([int]$config.server_port) -WorkingDirectory $projectRoot -LogPrefix 'pip'
    if ($reqExit -ne 0) {
        if (Can-RunSwimdash -PythonExe $pythonExe -WorkingDirectory $projectRoot) {
            Write-Warning 'requirements 설치는 실패했지만 현재 환경에서 swimdash 는 실행 가능합니다. 계속 진행합니다.'
        } else {
            throw 'requirements 설치 실패'
        }
    }
} else {
    Write-Warning 'requirements.txt 가 없어서 의존성 설치를 건너뜁니다.'
}

Write-Section '첫 실행: 수집/리빌드'
& (Join-Path $projectRoot 'run_cycle.ps1')
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'run_cycle.ps1 이 실패했습니다. 그래도 서버는 시작해 보겠습니다. logs 폴더를 확인하세요.'
}

Write-Section '서버 시작'
& (Join-Path $projectRoot 'start_server.ps1')
if ($LASTEXITCODE -ne 0) {
    throw '서버 시작 실패'
}

if (-not [bool]$config.skip_scheduler) {
    Write-Section '작업 스케줄러 등록'
    & (Join-Path $projectRoot 'install_scheduler.ps1')
}

Write-Section '끝'
Write-Host "브라우저에서 확인: http://127.0.0.1:$($config.server_port)/" -ForegroundColor Green
Write-Host '테스트 기간은 3월 전체 재수집(march_pilot) 모드입니다.' -ForegroundColor Green
Write-Host '테스트 종료 후 switch_to_rolling_3d.ps1 를 한 번 실행하면 최근 3일 모드로 바뀝니다.' -ForegroundColor Green
