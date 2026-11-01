# Starts CV Generator on Windows.
#
# This file only gets uv, the one tool the rest depends on, and only after
# asking. Everything else is done by the Python launcher in launcher/, which
# uv runs. Same steps as start.sh.
Set-Location $PSScriptRoot

# --yes means "do not ask". It is also handed to the launcher, so every
# argument reaches it unchanged.
$assumeYes = $args -contains '--yes'

function Find-Uv {
    $found = Get-Command uv -ErrorAction SilentlyContinue
    if ($found) {
        return $found.Source
    }
    $candidate = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
    if (Test-Path $candidate) {
        return $candidate
    }
    return $null
}

$uv = Find-Uv
if (-not $uv) {
    Write-Host "uv is missing. uv is the tool CV Generator uses to download Python and the app's packages."
    $answer = 'n'
    if ($assumeYes) {
        $answer = 'y'
    }
    else {
        $reply = Read-Host 'Install it now? [Y/n]'
        if ($null -ne $reply) {
            if ($reply.Trim() -eq '') { $answer = 'y' } else { $answer = $reply.Trim() }
        }
    }
    $manualHelp = 'To install it yourself, follow https://docs.astral.sh/uv/getting-started/installation/ and then start CV Generator again.'
    if ($answer -notin @('y', 'yes')) {
        Write-Host $manualHelp
        exit 1
    }
    # The installer would otherwise edit the person's PATH.
    $env:UV_NO_MODIFY_PATH = '1'
    # Started from PowerShell 7, Windows PowerShell inherits PowerShell 7's module
    # folders and cannot load commands the installer needs from them, such as
    # Get-ExecutionPolicy. The installer's powershell below gets the system's own
    # module folders instead, when it has any.
    $machineModules = [Environment]::GetEnvironmentVariable('PSModulePath', 'Machine')
    if ($machineModules) {
        $env:PSModulePath = $machineModules
    }
    # The installer gets a powershell of its own, with the flags start.bat gives
    # this one: when it fails it runs `exit 1`, which in this one would end the
    # script before it could say what to do next. Old Windows 10 builds default
    # to older TLS versions, hence the first statement.
    $installed = $false
    try {
        & powershell -NoProfile -ExecutionPolicy Bypass -Command '[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; irm https://astral.sh/uv/install-does-not-exist.ps1 | iex'
        $installed = $LASTEXITCODE -eq 0
    }
    catch {
        Write-Host $_.Exception.Message
    }
    $uv = Find-Uv
    if (-not $installed -or -not $uv) {
        Write-Host 'Installing uv did not work.'
        Write-Host $manualHelp
        exit 1
    }
}

Write-Host 'Getting ready...'
& $uv run --no-project --python 3.12 --quiet python -m launcher @args
exit $LASTEXITCODE
