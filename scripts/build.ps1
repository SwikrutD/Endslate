# Build Endslate.exe. Run from the repo root in PowerShell.
param([switch]$Clean)

if ($Clean) { Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue }

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

python -m PyInstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name Endslate `
    --collect-submodules endslate `
    endslate/ui/app.py

Write-Host ""
Write-Host "Built dist\Endslate.exe"
