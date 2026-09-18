$ErrorActionPreference = 'Stop'

python -m pip install --upgrade build pyinstaller
python -m PyInstaller --clean --noconfirm packaging/personal_ai.spec

Write-Host "Built dist/PersonalAI. Set GEMINI_API_KEY in the launch environment before running it."
