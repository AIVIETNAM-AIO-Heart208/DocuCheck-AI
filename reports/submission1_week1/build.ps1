param([switch]$Render)
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    New-Item -ItemType Directory -Force -Path qa | Out-Null
    for ($pass = 1; $pass -le 3; $pass++) {
        $logPath = Join-Path $PSScriptRoot "qa/build-pass-$pass.txt"
        # Native stderr may contain MiKTeX's advisory update notice.
        $ErrorActionPreference = 'Continue'
        & xelatex -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape -disable-installer main.tex *> $logPath
        $compilerExit = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($compilerExit -ne 0) { throw "XeLaTeX pass $pass failed; see $logPath" }
    }
    $latexLog = Get-Content -Raw -Encoding UTF8 -LiteralPath main.log
    if ($latexLog -match 'Overfull \\[hv]box|Missing character:|undefined references|Citation .+ undefined|Reference .+ undefined|ignored error:') {
        throw 'Layout/reference/glyph problem remains; inspect main.log.'
    }
    if (-not (Test-Path -LiteralPath main.pdf)) { throw 'main.pdf missing.' }
    if ($Render) {
        & pdftoppm -r 110 -png main.pdf qa/page
        if ($LASTEXITCODE -ne 0) { throw 'PDF rendering failed.' }
        & pdftotext -layout main.pdf qa/extracted.txt
        if ($LASTEXITCODE -ne 0) { throw 'PDF text extraction failed.' }
        & pdfinfo main.pdf | Out-File -Encoding UTF8 -LiteralPath qa/pdfinfo.txt
        if ($LASTEXITCODE -ne 0) { throw 'PDF metadata inspection failed.' }
    }
    Write-Output 'Built main.pdf; references and layout log checks passed.'
} finally {
    Pop-Location
}
