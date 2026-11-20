param(
    [string]$PythonExecutable = 'C:\Python312\python.exe'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw "Python was not found at '$PythonExecutable'. Pass -PythonExecutable with your Python path."
}

# Each terminal session creates its own temporary directory, with its own permissions.
# Disabling the cache also avoids a .pytest_cache created by another Windows account.
$td07TempPath = Join-Path ([System.IO.Path]::GetTempPath()) (
    'slrresearch-td07-' + [guid]::NewGuid().ToString('N')
)

Push-Location -LiteralPath $PSScriptRoot
try {
    & $PythonExecutable -X utf8 -m pytest -v -p no:cacheprovider --basetemp $td07TempPath
    $td07ExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $td07ExitCode
