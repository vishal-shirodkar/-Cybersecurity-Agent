param(
    [string]$RepositoryUrl = "https://github.com/mukul975/Anthropic-Cybersecurity-Skills.git",
    [string]$Destination = "data\upstream\Anthropic-Cybersecurity-Skills"
)

$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root $Destination
if (-not (Test-Path $target)) {
    git clone $RepositoryUrl $target
}
else {
    git -C $target pull --ff-only origin main
}

python "$root\main.py" sync-manifest --index-file "$target\index.json"
