import boto3
import json
from datetime import datetime

# ── CONFIG — change these ──
REGION        = 'us-east-1'
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:ec2-stop-alert'
S3_BUCKET     = 'ec2-lifecycle-logs-yourname'
DDB_TABLE     = 'ec2-override'
TARGET_TAGS   = {'Env': 'dev', 'AutoStop': 'true'}

ec2 = boto3.client('ec2', region_name=REGION)
ddb = boto3.resource('dynamodb', region_name=REGION)
sns = boto3.client('sns', region_name=REGION)
s3  = boto3.client('s3', region_name=REGION)

def get_tagged_instances():
    filters = [{'Name': 'instance-state-name', 'Values': ['running']}]
    for key, value in TARGET_TAGS.items():
        filters.append({'Name': f'tag:{key}', 'Values': [value]})

    response = ec2.describe_instances(Filters=filters)
    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            name = 'unnamed'
            for tag in instance.get('Tags', []):
                if tag['Key'] == 'Name':
                    name = tag['Value']
            instances.append({'id': instance['InstanceId'], 'name': name})
    return instances

def check_override(instance_id):
    table = ddb.Table(DDB_TABLE)
    response = table.get_item(Key={'instance_id': instance_id})
    item = response.get('Item')
    if item and item.get('override') == True:
        return item
    return None

def save_log_to_s3(log_data):
    date_str = datetime.now().strftime('%Y-%m-%d_%H-%M')
    key = f"logs/{date_str}.json"
    s3.put_object(Bucket=S3_BUCKET, Key=key,
                  Body=json.dumps(log_data, indent=2),
                  ContentType='application/json')

def send_email_report(stopped, skipped):
    stop_lines = '\n'.join([f"  - {i['name']} ({i['id']}) STOPPED" for i in stopped]) or '  None'
    skip_lines = '\n'.join([f"  - {i['name']} ({i['id']}) SKIPPED — {i['reason']}" for i in skipped]) or '  None'

    message = f"""
EC2 Nightly Report
==================
Time: {datetime.now().strftime('%Y-%m-%d %H:%M IST')}

Stopped ({len(stopped)}):
{stop_lines}

Skipped — override active ({len(skipped)}):
{skip_lines}

Audit log: s3://{S3_BUCKET}
    """
    sns.publish(TopicArn=SNS_TOPIC_ARN,
                Subject=f'EC2 Report — {len(stopped)} stopped, {len(skipped)} skipped',
                Message=message)

def lambda_handler(event, context):
    action = event.get('action', 'stop')
    instances = get_tagged_instances()

    stopped, skipped = [], []

    for instance in instances:
        override = check_override(instance['id'])
        if override:
            skipped.append({**instance, 'reason': override.get('reason', 'override set')})
        else:
            if action == 'stop':
                ec2.stop_instances(InstanceIds=[instance['id']])
            else:
                ec2.start_instances(InstanceIds=[instance['id']])
            stopped.append(instance)

    log = {'timestamp': datetime.now().isoformat(), 'action': action,
           'stopped_or_started': stopped, 'skipped': skipped}
    save_log_to_s3(log)
    send_email_report(stopped, skipped)

    return {'statusCode': 200, 'processed': len(stopped), 'skipped': len(skipped)}
