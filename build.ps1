# Define the AWS SSO profiles and the month/year
$awsProfiles = @("csvc-nonprd","csvc-prd","csvc-mgmt","homes-prod-prd","homes-nonprod-prd","smmts-nonprod-prd","smmts-prod-prd","mdc-nonprod-prd","mdc-prod-prd","drom-prod-prd","drom-nonprod-prd","mhcp-nonprod-prd","mhcp-prod-prd","prs-nonprod-prd","prs-prod-prd","dsaid-covid","covid-uat","ptms-prd","ptms-noprd","cas-situat","cas-prd","hris-prd","hris-nonprd","amdrs-noprd","amdrs-prd","appsh-noprd","appsh-prd","ccode-noprd","ccode-prd","susy-prd","susy-nonprd")
#$monthYear = "08-2024"  # Hardcoded mm/yyyy date
$pythonPath = "python"  # Path to Python executable, use "python" if it's in your system PATH
$scriptPath = "Monthly_report.py"
# Prompt the user to enter the month and year
$monthYear = Read-Host "Enter the month and year (MM-YYYY)"

# Output the entered value
Write-Output "You entered: $monthYear"

# Optional: You can further split and validate the input if necessary
if ($monthYear -match "^\d{2}-\d{4}$") {
    $month, $year = $monthYear -split '-'
    Write-Output "Month: $month"
    Write-Output "Year: $year"
} else {
    Write-Output "Invalid format. Please enter the month and year in MM-YYYY format."
}

# Function to run the Python script with the specified AWS profile and month_year
function Execute-Command {
    param (
        [string]$profile,
        [int]$progressIndex,     # Current index in the loop
        [int]$totalProfiles      # Total number of profiles
    )

    # Update the progress bar
    $percentComplete = [math]::Round(($progressIndex / $totalProfiles) * 100)
    Write-Progress -Activity "Executing Python script for AWS profiles" `
                    -Status "Processing $profile ($progressIndex of $totalProfiles)" `
                    -PercentComplete $percentComplete

    # Set the AWS_PROFILE environment variable
    $env:AWS_PROFILE = $profile

    # Authenticate using AWS SSO
    Write-Output "Attempting to login with profile: $profile"
    $ssoLoginResult = aws sso login --profile $profile 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "AWS SSO login failed for profile: $profile. Details: $ssoLoginResult"
        return
    }
    Write-Output "Logged in successfully with profile: $profile"

    # Define the two values to pass as user input (AWS Profile and mm_yyyy)
    $value1 = $profile
    $value2 = $monthYear

    # Create a temporary file to simulate user input (AWS Profile and mm_yyyy)
    $tempInputFile = [System.IO.Path]::GetTempFileName()

    # Write the input values to the temporary file, mimicking user input
    "$value1`n$value2" | Out-File -FilePath $tempInputFile -Encoding ASCII

    # Execute the Python script and simulate user input by redirecting the standard input
    $outputFile = "logs/$profile-output.log"
    $errorFile = "logs/$profile-error.log"
    Write-Output "Executing Python script for profile: $profile"
    $process = Start-Process -FilePath $pythonPath -ArgumentList $scriptPath -RedirectStandardInput $tempInputFile -RedirectStandardOutput $outputFile -RedirectStandardError $errorFile -NoNewWindow -Wait -PassThru

    # Clean up the temporary input file after script execution
    Remove-Item -Path $tempInputFile

    # Check for process success or failure
    if ($process.ExitCode -ne 0) {
        $errorDetails = Get-Content -Path $errorFile
        Write-Error "Execution failed for profile: $profile. Check $errorFile for details. Error: $errorDetails"
    } else {
        Write-Output "Execution succeeded for profile: $profile. Output saved to $outputFile"
    }
}

# Loop through each AWS SSO profile and execute the command
$totalProfiles = $awsProfiles.Count
for ($i = 0; $i -lt $totalProfiles; $i++) {
    $profile = $awsProfiles[$i]
    Execute-Command -profile $profile -progressIndex ($i + 1) -totalProfiles $totalProfiles
}

# Clear progress bar at the end
Write-Progress -Activity "Complete" -Status "All profiles processed" -Completed
