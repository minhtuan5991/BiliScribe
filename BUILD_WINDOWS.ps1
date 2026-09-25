param([string]$Python='python', [string]$Compiler='')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { & $Python -m venv .venv }
$taskPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $taskPython -m pip install -r requirements.txt 'pyinstaller==6.22.3'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $taskPython scripts\collect_licenses.py
& $taskPython -m PyInstaller --noconfirm BiliScribe.spec
if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
if (-not $Compiler) {
    $taskCandidates=@((Join-Path $PSScriptRoot "tools\InnoSetup\ISCC.exe"), "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")
    $Compiler=$taskCandidates | Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
}
if (-not $Compiler) {throw 'Supply -Compiler with the path to Inno Setup 6 ISCC.exe.'}
& $Compiler installer\BiliScribe.iss
if ($LASTEXITCODE -ne 0) {throw 'Installer build failed.'}
& $taskPython scripts\package_release.py
