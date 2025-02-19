"""
---------------------------------------------------------------------------------------------------
Author: Don Kusumitha Senanayake
Title:  Monthly Network Utilization Report
Version : 1
Description :  Report on monthly server utilization Python
Created on: 31-7-2024
Last Revised on: 01-10-2024
---------------------------------------------------------------------------------------------------
"""

import botocore
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime
import numpy as np
import openpyxl

from functions import *


# Function to get patches installed on EC2 instances
def get_monthly_patches(ec2, instance_id, ssm_client, start_time, end_time):
    # Get the list of installed patches for the specified instance
    response = ssm_client.describe_instance_patches(InstanceId=instance_id)

    patches = []
    for patch in response.get('Patches', []):
        installed_time_str = patch.get('InstalledTime', 'N/A')

        # Check if installed_time_str is already a datetime object
        installed_time = installed_time_str if isinstance(installed_time_str, datetime) else datetime.strptime(installed_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")

        # Convert installed_time to timezone-naive
        installed_time = installed_time.replace(tzinfo=None)

        # Filter patches for start date to end date
        if start_time <= installed_time <= end_time:
            patch_data = {
                'Instance ID': instance_id,
                'Instance Name': get_instance_name(instance_id, ec2),
                'Instance State': get_instance_state(instance_id, ec2),
                'Patch Name': patch['Title'],
                'Severity': patch['Severity'],
                'Compliance State': patch['State'],
                'Installed Time': patch['InstalledTime'].strftime('%Y-%m-%d'),
                'KB ID': patch.get('KBId', 'N/A'),
                'Installed Time': installed_time if installed_time != 'N/A' else 'Not Available'
            }
            patches.append(patch_data)
    return patches

# Function to get CPU utilization statistics
def get_cpu_utilization(instance_id, start_time, end_time, cloudwatch):
    response = cloudwatch.get_metric_statistics(
        Namespace='AWS/EC2',
        MetricName='CPUUtilization',
        Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
        StartTime=start_time,
        EndTime=end_time,
        Period=3600,
        Statistics=['Average'],
        Unit='Percent'
    )
    return response['Datapoints']

# Simplified function to get either memory or disk utilization based on parameters
def get_utilization(platform, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, metric_name, dimensions):        
    try:
        # For Windows platform, do not use the 'Unit' parameter
        if platform == 'Windows' and 'Memory' in metric_name:
            response = cloudwatch.get_metric_statistics(
                Namespace='CWAgent',
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average']
            )
        elif platform == 'Windows' and 'LogicalDisk' in metric_name:
            response = cloudwatch.get_metric_statistics(
                Namespace='CWAgent',
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average']
            )
        else:
            response = cloudwatch.get_metric_statistics(
                Namespace='CWAgent',
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average'],
                Unit='Percent'  # Use Unit 'Percent' for non-Windows platforms
            )
        
        if not response['Datapoints']:
            print(f"No {metric_name} utilization data found for instance {instance_id}.")
        return response['Datapoints']
    except Exception as e:
        print(f"Error retrieving {metric_name} utilization for instance {instance_id}: {e}")
        return []


# Function to get EC2 instance platform (Windows or Linux)
def get_instance_platform(ec2, instance_id):
    response = ec2.describe_instances(InstanceIds=[instance_id])
    reservations = response.get('Reservations', [])
    if reservations:
        instances = reservations[0].get('Instances', [])
        if instances:
            platform = instances[0].get('PlatformDetails', 'Linux/UNIX')  # Default to Linux/UNIX if not Windows
            # Get the number of attached storage volumes
            block_device_mappings = instances[0].get('BlockDeviceMappings', [])
            volume_count = len(block_device_mappings)
            
            return platform, volume_count
    return 'N/A', 0

# Function to get memory utilization based on platform (Windows or RHEL)
def get_memory_utilization(instance_name, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, platform):
    if platform == 'Windows':
        metric_name = 'Memory % Committed Bytes In Use'
        dimensions = [
            {'Name': 'ImageId', 'Value': image_id},
            {'Name': 'InstanceId', 'Value': instance_id},
            {'Name': 'InstanceType', 'Value': instance_type},
            {'Name': 'objectname', 'Value': 'Memory'}
        ]
    elif platform == 'Red Hat Enterprise Linux':
        metric_name = 'mem_used_percent'
        dimensions = [
            {'Name': 'InstanceId', 'Value': instance_id},
            {'Name': 'ImageId', 'Value': image_id},
            {'Name': 'InstanceType', 'Value': instance_type}
        ]
    else:
        print(f"Instance {instance_name} is running on Unsupported platform for memory utilization:{platform}.")
        return []

    # Retrieve memory utilization from CloudWatch based on platform
    return get_utilization(platform, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, metric_name, dimensions)

# Function to get disk utilization\disk fress space based on platform (Windows or RHEL)
def get_disk_utilization(instance_name, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, platform, device, disk):
    if platform == 'Windows':
        metric_name = 'LogicalDisk % Free Space'
        dimensions=[
            {'Name': 'instance', 'Value': disk},
            {'Name': 'InstanceId', 'Value': instance_id},
            {'Name': 'ImageId', 'Value': image_id},
            {'Name': 'objectname', 'Value': 'LogicalDisk'},
            {'Name': 'InstanceType', 'Value': instance_type}
        ]
    elif platform == 'Red Hat Enterprise Linux':
        metric_name='disk_used_percent'
        dimensions=[
            {'Name': 'InstanceId', 'Value': instance_id},
            {'Name': 'ImageId', 'Value': image_id},
            {'Name': 'InstanceType', 'Value': instance_type},
            {'Name': 'device', 'Value': device},
            {'Name': 'fstype', 'Value': 'xfs'},
            {'Name': 'path', 'Value': disk}
        ]
    else:
        print(f"Instance {instance_name} is running on Unsupported platform for Disk utilization:{platform}.")
        return []

    # Retrieve memory utilization from CloudWatch based on platform
    return get_utilization(platform, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, metric_name, dimensions)

# Helper function to retrieve network utilization
def get_network_utilization(instance_id, start_time, end_time, cloudwatch):
    metrics = {
        'NetworkIn': 'Inbound Bandwidth (Mbps)',
        'NetworkOut': 'Outbound Bandwidth (Mbps)'
    }

    network_data = {
        'InstanceName': '',
        'InstanceId': instance_id,
        'Average Inbound Bandwidth (Mbps)': 0,
        'Average Outbound Bandwidth (Mbps)': 0,
        'Min Inbound Bandwidth (Mbps)': 0,
        'Min Outbound Bandwidth (Mbps)': 0,
        'Max Inbound Bandwidth (Mbps)': 0,
        'Max Outbound Bandwidth (Mbps)': 0,
        'P95 Inbound Bandwidth (Mbps)': 0,
        'P95 Outbound Bandwidth (Mbps)': 0,
        'VM Network capacity (Mbps)': 1000  # Placeholder for network capacity
    }

    for metric, label in metrics.items():
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName=metric,
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Average', 'Minimum', 'Maximum'],
            Unit='Bytes'
        )
        
        data_points = response.get('Datapoints', [])
        
        if data_points:
            # Get the individual values for Average, Min, Max
            average = sum([point['Average'] for point in data_points]) / len(data_points)
            minimum = min([point['Minimum'] for point in data_points])
            maximum = max([point['Maximum'] for point in data_points])

            # Convert data points to Mbps (from bytes)
            bandwidth_values = [point['Average'] / (1024 * 1024) for point in data_points]

            # Calculate P95
            if bandwidth_values:
                p95_value = np.percentile(bandwidth_values, 95)  # Using numpy for P95 calculation
            else:
                p95_value = 0

            # Convert from bytes to Mbps
            if metric == 'NetworkIn':
                network_data['Average Inbound Bandwidth (Mbps)'] = average / (1024 * 1024)
                network_data['Min Inbound Bandwidth (Mbps)'] = minimum / (1024 * 1024)
                network_data['Max Inbound Bandwidth (Mbps)'] = maximum / (1024 * 1024)
                network_data['P95 Inbound Bandwidth (Mbps)'] = p95_value
                network_data['VM Network capacity (Mbps)'] = maximum / (1024 * 1024)
            else:
                network_data['Average Outbound Bandwidth (Mbps)'] = average / (1024 * 1024)
                network_data['Min Outbound Bandwidth (Mbps)'] = minimum / (1024 * 1024)
                network_data['Max Outbound Bandwidth (Mbps)'] = maximum / (1024 * 1024)
                network_data['P95 Outbound Bandwidth (Mbps)'] = p95_value
                network_data['VM Network capacity (Mbps)'] = maximum / (1024 * 1024)
    return network_data

# Function to calculate monthly average
def calculate_monthly_average(datapoints):
    if not datapoints:
        return None
    total = sum(dp['Average'] for dp in datapoints)
    return total / len(datapoints)

def get_rds_utilization(session, rds,start_time, end_time, cloudwatch):
    # Fetch the list of RDS instances
    db_instances = rds.describe_db_instances()
    account_name = get_aws_account_name(session)
    
    # Create a list to store utilization data
    utilization_data = []

    # Loop through the instances
    for db_instance in db_instances['DBInstances']:
        db_name = db_instance['DBInstanceIdentifier']
        db_type = db_instance['Engine']

        cpu_utilization = cloudwatch.get_metric_statistics(
            Namespace='AWS/RDS',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': db_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Average'],
            Unit='Percent'
        )

        read_iops = cloudwatch.get_metric_statistics(
            Namespace='AWS/RDS',
            MetricName='ReadIOPS',
            Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': db_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Average']
        )

        # Extract the data points for graphs
        cpu_datapoints = sorted(cpu_utilization['Datapoints'], key=lambda x: x['Timestamp'])
        read_iops_datapoints = sorted(read_iops['Datapoints'], key=lambda x: x['Timestamp'])

        # Get average values if data is returned
        cpu_avg = (
            sum([point['Average'] for point in cpu_utilization['Datapoints']]) / len(cpu_utilization['Datapoints'])
            if cpu_utilization['Datapoints'] else None
        )
        read_iops_avg = (
            sum([point['Average'] for point in read_iops['Datapoints']]) / len(read_iops['Datapoints'])
            if read_iops['Datapoints'] else None
        )

        # Append data to list
        utilization_data.append({
            'db_name': db_name,
            'db_type': db_type,
            'account_name': account_name,
            'cpu_avg': cpu_avg,
            'read_iops_avg': read_iops_avg,
            'cpu_datapoints': cpu_datapoints,
            'read_iops_datapoints': read_iops_datapoints
        })

    return utilization_data

def create_rds_graphs(utilization_data, output_folder, base_directory='rds_utilization_graphs'):
    # Create the base directory if it doesn't exist
    # Create a subfolder for each EC2 instance inside the main folder
    rds_base_folder = os.path.join(output_folder, base_directory)
    if not os.path.exists(rds_base_folder):
        os.makedirs(rds_base_folder)

    for rds_utilization in utilization_data:
        db_name = rds_utilization['db_name']
        db_folder = os.path.join(rds_base_folder, db_name)

        # Create subfolder for the database if it doesn't exist
        if not os.path.exists(db_folder):
            os.makedirs(db_folder)

        # Get the CPU and Read IOPS data points
        cpu_datapoints = rds_utilization['cpu_datapoints']
        read_iops_datapoints = rds_utilization['read_iops_datapoints']

        # Extract timestamps and values for CPU Utilization and Read IOPS
        cpu_times = [dp['Timestamp'] for dp in cpu_datapoints]
        cpu_values = [dp['Average'] for dp in cpu_datapoints]

        iops_times = [dp['Timestamp'] for dp in read_iops_datapoints]
        iops_values = [dp['Average'] for dp in read_iops_datapoints]

        # Plot CPU Utilization graph
        plt.figure()
        plt.plot(cpu_times, cpu_values, label='CPU Utilization (%)', color='blue')
        plt.title(f'{db_name} - CPU Utilization')
        plt.xlabel('Timestamp')
        plt.ylabel('CPU Utilization (%)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(db_folder, 'cpu_utilization.png'))
        plt.close()

        # Plot Read IOPS graph
        plt.figure()
        plt.plot(iops_times, iops_values, label='Read IOPS', color='green')
        plt.title(f'{db_name} - Read IOPS')
        plt.xlabel('Timestamp')
        plt.ylabel('Read IOPS')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(db_folder, 'read_iops.png'))
        plt.close()


def generate_compliance_report(ssm_client, instance_id, instance_name):
    compliance_data = []

    try:
        # Fetch compliance details
        response = ssm_client.describe_instance_patch_states(InstanceIds=[instance_id])
        # Check if the response contains 'InstancePatchStates'
        if 'InstancePatchStates' in response:
            for state in response['InstancePatchStates']:
                compliance_data.append({
                    'Instance ID': instance_id,
                    'Instance Name': instance_name,
                    'Installed': state.get('InstalledCount', 0),
                    'InstalledOther': state.get('InstalledOtherCount', 0),
                    'Installed Pending Reboot': state.get('InstalledPendingRebootCount', 0),
                    'Installed Rejected': state.get('InstalledRejectedCount', 0),
                    'Missing': state.get('MissingCount', 0),
                    'Failed': state.get('FailedCount', 0),
                    'OperationStart': state.get('OperationStartTime', 'N/A').strftime('%Y-%m-%d'),
                    'OperationEnd': state.get('OperationEndTime', 'N/A').strftime('%Y-%m-%d')
                })
        else:
            print(f"Unexpected response format for instance {instance_id}: {response}")
    
    except Exception as e:
        print(f"An error occurred for instance {instance_id}: {str(e)}")
    return compliance_data

# Function to generate CPU, Memory, and Disk utilization report for all instances
def generate_report(profile_name, session, start_time, end_time, output_folder):
    cloudwatch = session.client('cloudwatch')
    ec2 = session.client('ec2')
    ssm_client = session.client('ssm')
    rds = session.client('rds')

    instances = ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    
    report_data = []
    network_data = []
    patches_data = []
    compliance_data = []
    rds_data = []
    
    excel_file = os.path.join(output_folder, f'Consolidated_report_{profile_name}_{start_time.strftime("%Y_%m")}.xlsx')
    with pd.ExcelWriter(excel_file, engine='xlsxwriter') as excel_writer:
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                image_id = instance['ImageId']
                instance_type = instance['InstanceType']
                instance_name = next(
                    (tag['Value'] for tag in instance['Tags'] if tag['Key'] == 'Name'),
                    instance_id
                )

            # Get platform (Windows or Linux) for the instance
            platform, volume_count = get_instance_platform(ec2, instance_id)

            # Create a subfolder for each EC2 instance inside the main folder
            instance_folder = os.path.join(output_folder, instance_name)
            os.makedirs(instance_folder, exist_ok=True)

            # CPU utilization
            cpu_datapoints = get_cpu_utilization(instance_id, start_time, end_time, cloudwatch)
            cpu_datapoints = sorted(cpu_datapoints, key=lambda x: x['Timestamp'])
            time_series_cpu = [dp['Timestamp'] for dp in cpu_datapoints]
            cpu_values = [dp['Average'] for dp in cpu_datapoints]
            avg_cpu_utilization = calculate_monthly_average(cpu_datapoints)
            
            # Memory utilization based on platform
            memory_datapoints = get_memory_utilization(
                instance_name, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, platform
            )
            memory_datapoints = sorted(memory_datapoints, key=lambda x: x['Timestamp'])
            if not memory_datapoints:
                avg_memory_utilization = "N/A"
                time_series_memory = []
                memory_values = []
            else:
                time_series_memory = [dp['Timestamp'] for dp in memory_datapoints]
                memory_values = [dp['Average'] for dp in memory_datapoints]
                avg_memory_utilization = calculate_monthly_average(memory_datapoints)
            
            # Disk utilization based on platform
            w_avg_disk_utilization = "N/A"
            w_avg_disk_utilization2 = "N/A"
            l_avg_disk_utilization = "N/A"
            l_avg_disk_utilization2 = "N/A"
            device = "N/A"
            
            if volume_count == 1 and platform == 'Windows':                
                w_disk_datapoints = get_disk_utilization(
                    instance_name, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, platform, device, disk = 'C:'
                )

                w_disk_datapoints = sorted(w_disk_datapoints, key=lambda x: x['Timestamp'])
                if not w_disk_datapoints:
                    w_avg_disk_utilization = "N/A"
                    time_series_disk = []
                    w_disk_values = []
                else:
                    time_series_disk = [dp['Timestamp'] for dp in w_disk_datapoints]
                    w_disk_values = [dp['Average'] for dp in w_disk_datapoints]
                    w_avg_disk_utilization = calculate_monthly_average(w_disk_datapoints)
                
                if len(w_disk_values) > 1:
                    time_series_disk = pd.to_datetime(time_series_disk)
                    w_disk_values = pd.Series(w_disk_values, index=time_series_disk).resample('D').mean().interpolate().tolist()
                    time_series_disk = pd.date_range(start=time_series_disk[0], end=time_series_disk[-1], freq='D')

                    # Plot Disk utilization graph
                    plt.figure(figsize=(10, 6))
                    plt.plot(time_series_disk, w_disk_values, label='Disk Utilization (%)', color='r', linestyle='-', marker='o')
                    plt.xlabel('Time')
                    plt.ylabel('Utilization (%)')
                    plt.title(f'Disk Utilization - {instance_name} ({instance_id})')
                    plt.legend()
                    plt.grid(True)
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()

                    graph_file_disk = os.path.join(instance_folder, f'{instance_name}_{instance_id}_C_Drive.png')
                    plt.savefig(graph_file_disk)
                    plt.close()

            elif volume_count == 2 and platform == 'Windows':
                w_disk_datapoints = get_disk_utilization(
                    instance_name, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, platform, device, disk = 'C:'
                )
                w_disk_datapoints = sorted(w_disk_datapoints, key=lambda x: x['Timestamp'])
                if not w_disk_datapoints:
                    w_avg_disk_utilization = "N/A"
                    time_series_disk = []
                    w_disk_values = []
                else:
                    time_series_disk = [dp['Timestamp'] for dp in w_disk_datapoints]
                    w_disk_values = [dp['Average'] for dp in w_disk_datapoints]
                    w_avg_disk_utilization = calculate_monthly_average(w_disk_datapoints)

                if len(w_disk_values) > 1:
                    time_series_disk = pd.to_datetime(time_series_disk)
                    w_disk_values = pd.Series(w_disk_values, index=time_series_disk).resample('D').mean().interpolate().tolist()
                    time_series_disk = pd.date_range(start=time_series_disk[0], end=time_series_disk[-1], freq='D')

                    # Plot Disk utilization graph
                    plt.figure(figsize=(10, 6))
                    plt.plot(time_series_disk, w_disk_values, label='Disk Utilization (%)', color='r', linestyle='-', marker='o')
                    plt.xlabel('Time')
                    plt.ylabel('Utilization (%)')
                    plt.title(f'Disk Utilization - {instance_name} ({instance_id})')
                    plt.legend()
                    plt.grid(True)
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()

                    graph_file_disk = os.path.join(instance_folder, f'{instance_name}_{instance_id}_C_Drive.png')
                    plt.savefig(graph_file_disk)
                    plt.close()

                w_disk_datapoints2 = get_disk_utilization(
                    instance_name, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, platform, device, disk = 'D:'
                )
                w_disk_datapoints2 = sorted(w_disk_datapoints2, key=lambda x: x['Timestamp'])
                if not w_disk_datapoints2:
                    w_disk_datapoints2 = get_disk_utilization(
                    instance_name, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, platform, device, disk = 'F:'
                )
                    w_disk_datapoints2 = sorted(w_disk_datapoints2, key=lambda x: x['Timestamp'])
                    if not w_disk_datapoints2:
                        w_avg_disk_utilization2 = "N/A"
                        time_series_disk = []
                        w_disk_values2 = []
                
                time_series_disk = [dp['Timestamp'] for dp in w_disk_datapoints2]
                w_disk_values2 = [dp['Average'] for dp in w_disk_datapoints2]
                w_avg_disk_utilization2 = calculate_monthly_average(w_disk_datapoints2)

                if len(w_disk_values2) > 1:
                    time_series_disk = pd.to_datetime(time_series_disk)
                    w_disk_values2 = pd.Series(w_disk_values2, index=time_series_disk).resample('D').mean().interpolate().tolist()
                    time_series_disk = pd.date_range(start=time_series_disk[0], end=time_series_disk[-1], freq='D')

                    # Plot Disk utilization graph
                    plt.figure(figsize=(10, 6))
                    plt.plot(time_series_disk, w_disk_values2, label='Disk Utilization (%)', color='r', linestyle='-', marker='o')
                    plt.xlabel('Time')
                    plt.ylabel('Utilization (%)')
                    plt.title(f'Disk Utilization - {instance_name} ({instance_id})')
                    plt.legend()
                    plt.grid(True)
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()

                    graph_file_disk = os.path.join(instance_folder, f'{instance_name}_{instance_id}_D_drive.png')
                    plt.savefig(graph_file_disk)
                    plt.close()

            elif volume_count == 1 and platform == 'Red Hat Enterprise Linux':
                l_disk_datapoints = get_disk_utilization(
                    instance_name, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, platform, device = 'nvme0n1p2', disk = '/'
                )

                l_disk_datapoints = sorted(l_disk_datapoints, key=lambda x: x['Timestamp'])
                if not l_disk_datapoints:
                    l_avg_disk_utilization = "N/A"
                    time_series_disk = []
                    l_disk_values = []
                else:
                    time_series_disk = [dp['Timestamp'] for dp in l_disk_datapoints]
                    l_disk_values = [dp['Average'] for dp in l_disk_datapoints]
                    l_avg_disk_utilization = calculate_monthly_average(l_disk_datapoints)

                if len(l_disk_values) > 1:
                    time_series_disk = pd.to_datetime(time_series_disk)
                    l_disk_values = pd.Series(l_disk_values, index=time_series_disk).resample('D').mean().interpolate().tolist()
                    time_series_disk = pd.date_range(start=time_series_disk[0], end=time_series_disk[-1], freq='D')

                    # Plot Disk utilization graph
                    plt.figure(figsize=(10, 6))
                    plt.plot(time_series_disk, l_disk_values, label='Disk Utilization (%)', color='r', linestyle='-', marker='o')
                    plt.xlabel('Time')
                    plt.ylabel('Utilization (%)')
                    plt.title(f'Disk Utilization - {instance_name} ({instance_id})')
                    plt.legend()
                    plt.grid(True)
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()

                    graph_file_disk = os.path.join(instance_folder, f'{instance_name}_Disk Utilization for root path.png')
                    plt.savefig(graph_file_disk)
                    plt.close()
                
            elif volume_count == 2 and platform == 'Red Hat Enterprise Linux':
                # List of possible path values and Device values
                path_values = ['/u01','/opt/tyk-gateway']  # Add all potential paths for secondary disk of linux
                device_values = ['nvme1n1p1','nvme1n1']
    
                l_disk_datapoints = get_disk_utilization(
                    instance_name, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, platform, device = 'nvme0n1p2', disk = '/'
                )

                l_disk_datapoints = sorted(l_disk_datapoints, key=lambda x: x['Timestamp'])
                if not l_disk_datapoints:
                    l_avg_disk_utilization = "N/A"
                    time_series_disk = []
                    l_disk_values = []
                else:
                    time_series_disk = [dp['Timestamp'] for dp in l_disk_datapoints]
                    l_disk_values = [dp['Average'] for dp in l_disk_datapoints]
                    l_avg_disk_utilization = calculate_monthly_average(l_disk_datapoints)

                if len(l_disk_values) > 1:
                    time_series_disk = pd.to_datetime(time_series_disk)
                    l_disk_values = pd.Series(l_disk_values, index=time_series_disk).resample('D').mean().interpolate().tolist()
                    time_series_disk = pd.date_range(start=time_series_disk[0], end=time_series_disk[-1], freq='D')

                    # Plot Disk utilization graph
                    plt.figure(figsize=(10, 6))
                    plt.plot(time_series_disk, l_disk_values, label='Disk Utilization (%)', color='r', linestyle='-', marker='o')
                    plt.xlabel('Time')
                    plt.ylabel('Utilization (%)')
                    plt.title(f'Disk Utilization - {instance_name} ({instance_id})')
                    plt.legend()
                    plt.grid(True)
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()

                    graph_file_disk = os.path.join(instance_folder, f'{instance_name}_Disk Utilization for root path.png')
                    plt.savefig(graph_file_disk)
                    plt.close()

                break_outer_loop = False  # Flag to break outer loop
                for ldevice in device_values:
                    for lpath in path_values:
                        l_disk_datapoints2 = get_disk_utilization(
                            instance_name, instance_id, image_id, instance_type, start_time, end_time, cloudwatch, platform, device=ldevice, disk=lpath
                        )
                        l_disk_datapoints2 = sorted(l_disk_datapoints2, key=lambda x: x['Timestamp'])
                        if not l_disk_datapoints2:
                            l_avg_disk_utilization2 = "N/A"
                            time_series_disk = []
                            l_disk_values2 = []
                        else:
                            time_series_disk = [dp['Timestamp'] for dp in l_disk_datapoints2]
                            l_disk_values2 = [dp['Average'] for dp in l_disk_datapoints2]
                            l_avg_disk_utilization2 = calculate_monthly_average(l_disk_datapoints2)
                
                            if len(l_disk_values2) > 0:
                                time_series_disk = pd.to_datetime(time_series_disk)
                                l_disk_values2 = pd.Series(l_disk_values2, index=time_series_disk).resample('D').mean().interpolate().tolist()
                                time_series_disk = pd.date_range(start=time_series_disk[0], end=time_series_disk[-1], freq='D')
                
                                # Plot Disk utilization graph
                                plt.figure(figsize=(10, 6))
                                plt.plot(time_series_disk, l_disk_values2, label='Disk Utilization (%)', color='r', linestyle='-', marker='o')
                                plt.xlabel('Time')
                                plt.ylabel('Utilization (%)')
                                plt.title(f'Disk Utilization - {instance_name} ({instance_id})')
                                plt.legend()
                                plt.grid(True)
                                plt.xticks(rotation=45, ha='right')
                                plt.tight_layout()
                
                                graph_file_disk = os.path.join(instance_folder, f'{instance_name}_Disk Utilization for secondary Volume.png')
                                plt.savefig(graph_file_disk)
                                plt.close()
                
                                break_outer_loop = True  # Set flag to break outer loop
                                break  # Break the inner loop
                            
                    if break_outer_loop:  # Check flag and break outer loop
                        break

            else:
                print(f"Instance {instance_name} is running on Unsupported platform for Disk utilization:{platform}.")

            compliance_datapoints = generate_compliance_report(ssm_client, instance_id, instance_name)
            for compliance in compliance_datapoints:
                compliance_data.append({
                'Instance ID': instance_id,
                    'Instance Name': instance_name,
                    'Installed': compliance['Installed'],
                    'InstalledOther': compliance['InstalledOther'],
                    'Installed Pending Reboot': compliance['Installed Pending Reboot'],
                    'Installed Rejected':  compliance['Installed Rejected'],
                    'Missing':  compliance['Missing'],
                    'Failed':  compliance['Failed'],
                    'OperationStart':  compliance['OperationStart'],
                    'OperationEnd':  compliance['OperationEnd']
                })
            
            # Network utilization
            network_utilization = get_network_utilization(instance_id, start_time, end_time, cloudwatch)
            network_utilization['InstanceName'] = instance_name
            network_data.append(network_utilization)

            # Fetch and add patches data
            patches = get_monthly_patches( ec2 , instance_id, ssm_client, start_time, end_time)
            for patch in patches:
                patches_data.append({
                'Instance Name': instance_name,
                'Instance ID': instance_id,
                'Patch Name': patch['Patch Name'],
                'Severity': patch['Severity'],
                'Compliance State': patch['Compliance State'],
                'Installed Time': patch['Installed Time']
                })

            # Handle missing data by linear interpolation
            if len(cpu_values) > 1:
                time_series_cpu = pd.to_datetime(time_series_cpu)
                cpu_values = pd.Series(cpu_values, index=time_series_cpu).resample('D').mean().interpolate().tolist()
                time_series_cpu = pd.date_range(start=time_series_cpu[0], end=time_series_cpu[-1], freq='D')

                # Plot CPU utilization graph
                plt.figure(figsize=(10, 6))
                plt.plot(time_series_cpu, cpu_values, label='CPU Utilization (%)', color='b', linestyle='-', marker='o')
                plt.xlabel('Time')
                plt.ylabel('Utilization (%)')
                plt.title(f'CPU Utilization - {instance_name} ({instance_id})')
                plt.legend()
                plt.grid(True)
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()

                graph_file_cpu = os.path.join(instance_folder, f'{instance_name}_{instance_id}_cpu.png')
                plt.savefig(graph_file_cpu)
                plt.close()

            if len(memory_values) > 1:
                time_series_memory = pd.to_datetime(time_series_memory)
                memory_values = pd.Series(memory_values, index=time_series_memory).resample('D').mean().interpolate().tolist()
                time_series_memory = pd.date_range(start=time_series_memory[0], end=time_series_memory[-1], freq='D')

                # Plot Memory utilization graph
                plt.figure(figsize=(10, 6))
                plt.plot(time_series_memory, memory_values, label='Memory Utilization (%)', color='g', linestyle='-', marker='o')
                plt.xlabel('Time')
                plt.ylabel('Utilization (%)')
                plt.title(f'Memory Utilization - {instance_name} ({instance_id})')
                plt.legend()
                plt.grid(True)
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()

                graph_file_memory = os.path.join(instance_folder, f'{instance_name}_{instance_id}_memory.png')
                plt.savefig(graph_file_memory)
                plt.close()

            # Save to Excel
            report_data.append({
                'InstanceId': instance_id,
                'InstanceName': instance_name,
                'InstancePlatform': platform,
                'AverageCPUUtilization (%)': avg_cpu_utilization,
                'AverageMemoryUtilization (%)': avg_memory_utilization,
                'AverageDiskUtilization root (%)': l_avg_disk_utilization if 'l_avg_disk_utilization' in locals() else 'N/A',
                f'AverageDiskUtilization (%) for Secondary volume': l_avg_disk_utilization2 if 'w_avg_disk_utilization2' in locals() else 'N/A',
                'AverageDiskUtilization (%) C Drive': w_avg_disk_utilization if 'w_avg_disk_utilization' in locals() else 'N/A',
                f'AverageDiskUtilization (%) for Secondary Drive': w_avg_disk_utilization2 if 'w_avg_disk_utilization2' in locals() else 'N/A'   
            })

            # Plot Network utilization graph
            plt.figure(figsize=(10, 6))
            plt.bar(['Average Inbound', 'Average Outbound'], 
                    [network_utilization['Average Inbound Bandwidth (Mbps)'], 
                     network_utilization['Average Outbound Bandwidth (Mbps)']],
                    color=['blue', 'green'])
            plt.xlabel('Network Utilization')
            plt.ylabel('Bandwidth (Mbps)')
            plt.title(f'Network Utilization - {instance_name} ({instance_id})')
            plt.tight_layout()

            network_graph_file = os.path.join(instance_folder, f'{instance_name}_{instance_id}_network.png')
            plt.savefig(network_graph_file)
            plt.close()

    rds_utilization_data = get_rds_utilization(session, rds, start_time, end_time, cloudwatch)
    create_rds_graphs(rds_utilization_data, output_folder)
    for rds_utilization in rds_utilization_data:
        rds_data.append({
        'Database name': rds_utilization['db_name'], 
        'db_type':rds_utilization['db_type'], 
        'AWS Account Name':rds_utilization['account_name'], 
        'CPU Utilization Avg':rds_utilization['cpu_avg'], 
        'Read IOPS Avg':rds_utilization['read_iops_avg']
        })

    # Save all data to an Excel file
    df = pd.DataFrame(report_data)
    # Save network data to a new sheet
    network_df = pd.DataFrame(network_data)
    # save patch data to new sheet
    patch_df = pd.DataFrame(patches_data)
    # save compliance data to new sheet
    compliance_df = pd.DataFrame(compliance_data)
    # save RDS data to new sheet
    rds_df = pd.DataFrame(rds_data)
    excel_file = os.path.join(output_folder, f'Consolidated_report_{profile_name}_{start_time.strftime("%Y_%m")}.xlsx')
    with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Server Utilization')
        network_df.to_excel(writer, index=False, sheet_name='Network Utilization')
        patch_df.to_excel(writer, index=False, sheet_name='Patch Installation')
        compliance_df.to_excel(writer, index=False, sheet_name='Patch Compliance Report')
        rds_df.to_excel(writer, index=False, sheet_name='RDS Report')

    print(f"Reports generated and saved to {output_folder}")

# Main function to manage the report generation and SSO session handling
def main(profile_names, month_year):
    for profile_name in profile_names:
        session = initialize_session(profile_name)
        
        try:
        # Parse the input month and year
            month, year = map(int, month_year.split('-'))
            start_time = datetime(year, month, 1)
            # Calculate the end of the month
            if month == 12:
                end_time = datetime(year + 1, 1, 1)
            else:
                end_time = datetime(year, month + 1, 1)
        except ValueError:
            print("Invalid input format. Please enter month and year as MM-YYYY.")
            return

        while True:
            try:
                # Create a folder with AWS account name and month_year
                output_folder = f'monthly-reports-{month_year}/{profile_name}-{month_year}'
                os.makedirs(output_folder, exist_ok=True)
                generate_report(profile_name, session, start_time, end_time, output_folder)
                break
            except botocore.exceptions.UnauthorizedSSOTokenError:
                print("AWS SSO session has expired. Attempting to re-login...")
                login_to_sso(profile_name)
                session = initialize_session(profile_name)
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                break

# Run the main function
if __name__ == "__main__":
    profile_names = input("Enter SSO Profile: ")
    #profile_names = []
    month_year = input("Enter the month and year (MM-YYYY): ")
    main(profile_names, month_year)
