Set-Location -LiteralPath $PSScriptRoot
python -m http.server 8766 --bind 127.0.0.1 --directory ..\docs
