import boto3
import subprocess

# Function to list EC2s
def get_instance_name(instance_id, ec2):
    response = ec2.describe_tags(Filters=[{'Name': 'resource-id', 'Values': [instance_id]}])
    for tag in response.get('Tags', []):
        if tag['Key'] == 'Name':
            return tag['Value']
    return 'N/A'

# Function to list EC2s state
def get_instance_state(instance_id, ec2):
    response = ec2.describe_instances(InstanceIds=[instance_id])
    reservations = response.get('Reservations', [])
    if reservations:
        instances = reservations[0].get('Instances', [])
        if instances:
            state = instances[0].get('State', {}).get('Name', 'N/A')
            return state
    return 'N/A'

# Function to handle AWS SSO login
def login_to_sso(profile_name):
    try:
        subprocess.run(["aws", "sso", "login", "--profile", profile_name], check=True)
        print("Logged in to AWS SSO successfully.")
    except subprocess.CalledProcessError:
        print("Failed to login to AWS SSO. Please check your profile settings.")

# Function to initialize the boto3 session with SSO profile
def initialize_session(profile_name):
    return boto3.Session(profile_name=profile_name)

# Function to get the logged-in AWS account name (or alias)
def get_aws_account_name(session):
    sts = session.client('sts')
    identity = sts.get_caller_identity()
    account_id = identity['Account']

    # Try to get the account alias if available (requires iam:ListAccountAliases permission)
    try:
        iam = session.client('iam')
        account_aliases = iam.list_account_aliases()['AccountAliases']
        if account_aliases:
            return account_aliases[0]  # Use the first alias if available
    except botocore.exceptions.ClientError as e:
        print(f"Error retrieving account alias: {e}")
    
    # If alias is not available, fall back to account ID
    return account_id