# install prerequisites
pip install -r requirements.txt

# check the executable file version
if (Test-Path .\version.txt) {
    $version = Get-Content .\version.txt
    $newVersion = [int]$version + 1
    Set-Content .\version.txt $newVersion
} else {
    # Create version.txt with initial version number if it doesn't exist
    Set-Content .\version.txt 1
}

# clean the build folder if they exist
if (Test-Path .\build) {
    Remove-Item -Recurse -Force .\build
}

# clean the spec file if it exists
if (Test-Path .\*.spec) {
    Remove-Item -Recurse -Force .\*.spec
}

# build the executable file
python -m PyInstaller --onefile --noconsole --name aws_monthly_report_$newVersion .\monthly_report.py

# create output folder if not exist
$outputFolder = ".\output"
if (-Not (Test-Path $outputFolder)) {
    New-Item -ItemType Directory -Path $outputFolder
}

# delete the current executable file in output folder if it exists
$outputFile = "$outputFolder\aws_monthly_report_$version.exe"
if (Test-Path $outputFile) {
    Remove-Item $outputFile
}

# copy the latest executable file to output folder
Copy-Item ".\dist\aws_monthly_report_$newVersion.exe" $outputFolder