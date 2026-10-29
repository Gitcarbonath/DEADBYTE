# DEADBYTE source-pinned launcher. Keeps the current source tree ahead of any
# stale site-packages copy while invoking the project's installed console script.
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EntryPoint = Join-Path $ProjectRoot '.venv\Scripts\deadbyte.exe'
$SourcePath = Join-Path $ProjectRoot 'src'
if (-not (Test-Path -LiteralPath $EntryPoint -PathType Leaf)) {
    throw "DEADBYTE entry point not found: $EntryPoint. Activate/install the project venv first."
}
$PreviousPythonPath = $env:PYTHONPATH
try {
    if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
        $env:PYTHONPATH = $SourcePath
    } else {
        $env:PYTHONPATH = "$SourcePath;$PreviousPythonPath"
    }
    & $EntryPoint @args
    $DeadbyteExitCode = $LASTEXITCODE
}
finally {
    $env:PYTHONPATH = $PreviousPythonPath
}
# Preserve the native command's exit status for the caller without closing the shell.
$global:LASTEXITCODE = $DeadbyteExitCode
