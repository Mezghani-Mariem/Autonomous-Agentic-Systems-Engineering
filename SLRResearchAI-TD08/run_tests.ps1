param(
    [string]$PythonExecutable = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    # Un ancien venv actif peut masquer le Python disposant des dépendances.
    $td08Candidates = @(
        Get-Command python -All -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty Source
    ) + @('C:\Python312\python.exe')
    foreach ($td08Candidate in ($td08Candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $td08Candidate -PathType Leaf)) {
            continue
        }
        & $td08Candidate -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pytest') else 1)"
        if ($LASTEXITCODE -eq 0) {
            $PythonExecutable = $td08Candidate
            break
        }
    }
    if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
        throw 'Aucun Python avec pytest trouve. Installez requirements.txt ou utilisez -PythonExecutable.'
    }
}

Write-Host "Python pour les tests : $PythonExecutable"
$td08TempPath = Join-Path ([System.IO.Path]::GetTempPath()) (
    'slrresearch-td08-' + [guid]::NewGuid().ToString('N')
)

Push-Location -LiteralPath $PSScriptRoot
try {
    & $PythonExecutable -X utf8 -m pytest -v -p no:cacheprovider --basetemp $td08TempPath
    $td08ExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $td08ExitCode
