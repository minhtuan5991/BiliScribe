param()
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskArea=Join-Path $taskRoot 'verification\v1.2.2'
$taskInstall=Join-Path $taskArea 'installed-app'
$taskRegistry='HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{59136726-3F92-476B-9D2B-435184773E58}_is1'
if (Test-Path -LiteralPath $taskRegistry) { throw 'An existing user installation is registered. Do not overwrite it during this test.' }
if (Test-Path -LiteralPath $taskInstall) { throw 'Test install directory already exists; choose a fresh verified destination.' }
$taskReport=[ordered]@{}
foreach ($taskVersion in @('1.2.1','1.2.2')) {
    $taskSetup=Join-Path $taskRoot "release\BiliScribe-Setup-$taskVersion-x64.exe"
    $taskArgs=@('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/TASKS=""',('/DIR="'+$taskInstall+'"'),('/LOG="'+(Join-Path $taskArea "install-$taskVersion.log")+'"'))
    $taskProcess=Start-Process -FilePath $taskSetup -ArgumentList $taskArgs -WindowStyle Hidden -Wait -PassThru
    $taskReport["install_$taskVersion"]=$taskProcess.ExitCode
    if ($taskProcess.ExitCode -ne 0) { throw "Installer failed: $taskVersion" }
    $taskVersionActual=(Get-Item -LiteralPath (Join-Path $taskInstall 'BiliScribe.exe')).VersionInfo.ProductVersion
    if ($taskVersionActual -ne $taskVersion) { throw "Unexpected installed version: $taskVersionActual" }
    $taskReport["version_$taskVersion"]=$taskVersionActual
    Write-Output "Installed $taskVersion successfully."
}
$taskReport['upgrade_passed']=$true
$taskWorker=Join-Path $taskInstall 'BiliScribeWorker.exe'
$taskSelfTest=Join-Path $taskArea 'installed-self-test'
& $taskWorker --self-test $taskSelfTest
$taskReport['self_test_exit']=$LASTEXITCODE
if ($LASTEXITCODE -ne 0) { throw 'Installed self-test failed.' }
$taskReport['registered']=Test-Path -LiteralPath $taskRegistry
$taskResolved=(Resolve-Path -LiteralPath $taskInstall).Path
$taskExpected=[System.IO.Path]::GetFullPath($taskInstall)
if ($taskResolved -ne $taskExpected -or -not $taskResolved.StartsWith($taskArea+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe uninstall target.' }
$taskUninstaller=Join-Path $taskResolved 'unins000.exe'
$taskProcess=Start-Process -FilePath $taskUninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="'+(Join-Path $taskArea 'uninstall.log')+'"')) -WindowStyle Hidden -Wait -PassThru
$taskReport['uninstall_exit']=$taskProcess.ExitCode
$taskReport['exe_removed']=-not(Test-Path -LiteralPath $taskWorker)
$taskReport['registry_removed']=-not(Test-Path -LiteralPath $taskRegistry)
$taskReport | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskArea 'installer-test.json') -Encoding UTF8
$taskReport | ConvertTo-Json
if ($taskProcess.ExitCode -ne 0 -or -not $taskReport.exe_removed -or -not $taskReport.registry_removed) { throw 'Uninstall verification failed.' }
