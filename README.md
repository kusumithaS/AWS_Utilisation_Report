# Monthly Network Utilization Report

## Overview
This project generates a monthly network utilization report for AWS EC2 instances and RDS instances. The report includes CPU, memory, disk, and network utilization statistics, as well as patch compliance data. The data is visualized in graphs and saved in an Excel file.

## Features
- Fetches and reports on EC2 instance utilization (CPU, memory, disk, network).
- Fetches and reports on RDS instance utilization (CPU, Read IOPS).
- Generates patch compliance reports for EC2 instances.
- Visualizes data in graphs and saves them as images.
- Consolidates all data into an Excel file with multiple sheets.

## Prerequisites
- Python 3.x
- AWS CLI configured with SSO profiles
- Required Python packages (listed in `requirements.txt`)

## Installation
1. Clone the repository:
    ```bash
    git clone https://github.com/kusumithaS/AWS_Utilisation_Report.git
    cd AWS_Utilisation_Report
    ```

2. Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

## Usage
1. Ensure your AWS CLI is configured with SSO profiles.

2. Run the [build.ps1](https://github.com/kusumithaS/AWS_Utilisation_Report/blob/master/build.ps1) script to build the executable:
    ```powershell
    .\build.ps1
    ```

3. Run the executable or the Python script to generate the report:
    ```bash
    python monthly_report.py
    ```

4. Follow the prompts to enter the SSO profile name and the month and year (MM-YYYY) for the report.

## Files
- [monthly_report.py](https://github.com/kusumithaS/AWS_Utilisation_Report/blob/master/monthly_report.py): Main script to generate the report.
- [build.ps1](https://github.com/kusumithaS/AWS_Utilisation_Report/blob/master/build.ps1): PowerShell script to build the executable using PyInstaller.
- [requirements.txt](https://github.com/kusumithaS/AWS_Utilisation_Report/blob/master/requirements.txt): List of required Python packages.
- [version.txt](https://github.com/kusumithaS/AWS_Utilisation_Report/blob/master/version.txt): File to keep track of the version number for the executable.


## License
This project is licensed under the MIT License. See the LICENSE file for details.

## Author
Don Kusumitha Senanayake

## Acknowledgements
- [boto3](https://github.com/boto/boto3) - The AWS SDK for Python
- [pandas](https://github.com/pandas-dev/pandas) - Data analysis and manipulation library
- [matplotlib](https://github.com/matplotlib/matplotlib) - Plotting library for Python
- [openpyxl](https://github.com/chronossc/openpyxl) - Library to read/write Excel 2010 xlsx/xlsm/xltx/xltm files