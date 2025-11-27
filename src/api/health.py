'''
System Health Dashboard API Route Blueprint.

Provides endpoints to check the health status of various system components
such as EC2 instances, Aurora Serverless database connectivity, S3 bucket status,
Application Load Balancer metrics, Elastic Beanstalk environment health, and
application logs.
'''

from flask import Blueprint, request, jsonify
from .config import Config, TestConfig
from datetime import datetime, timedelta, timezone
from .auth import check_permissions
import os
import boto3
import psycopg2

# Blueprint setup
health_bp = Blueprint("health_bp", __name__)
config = TestConfig if os.environ.get("DEBUG") == "True" else Config
from src.logger import get_logger
logger = get_logger("api.health")

# AWS Clients
cloudwatch = boto3.client("cloudwatch", region_name=config.AWS_REGION)
logs_client = boto3.client("logs", region_name=config.AWS_REGION)
elb_client = boto3.client("elbv2", region_name=config.AWS_REGION)
eb_client = boto3.client("elasticbeanstalk", region_name=config.AWS_REGION)
ec2_client = boto3.client("ec2", region_name=config.AWS_REGION)
s3_client = boto3.client("s3", region_name=config.AWS_REGION)
rds_client = boto3.client("rds", region_name=config.AWS_REGION)

GRANULARITY = 60  # 1 minute granularity for metrics, meaning that data points are aggregated over 1 minute intervals

@health_bp.route('/health', methods=['GET'])
def health():
    """
    Health check route.
    Returns:
        200 OK: If the service is reachable.
    """
    return jsonify({'message': 'Service reachable.', "timestamp": datetime.now(timezone.utc).isoformat()}), 200

# AWS Helpter functions to fetch metrics and logs
def fetch_eb_env_resource() -> dict:
    '''
    Fetch Elastic Beanstalk environment resources.
    Returns:
        EnvironmentResources dict from EB describe_environment_resources API.
    '''
    try:
        response = eb_client.describe_environment_resources(
            EnvironmentName=config.ELASTIC_BEANSTALK_ENV_NAME
        )
        logger.info(f"EB Environment Resources: {response}")
        return response["EnvironmentResources"]
    except Exception as e:
        logger.error(f"EB fetch error: {e}")
        return None


def fetch_ec2_metrics(instance_ids: list, window: datetime, include_timeline: bool = False) -> list:
    '''
    Fetch EC2 CPUUtilization metrics from CloudWatch within the given time window.
    Returns a list of datapoints for all EC2 instances in the specified EB environment.
    Args:
        instance_ids (list): List of EC2 instance IDs.
        window (datetime): Start time for metrics retrieval.
        include_timeline (bool): Whether to include timeline data. Default is False.
    Returns:
        EC2 component containing the following metrics:
        - CPUUtilization: List of datapoints with timestamps and average CPU utilization.
    '''
    components = []
    # For each instance, fetch CPUUtilization metric from CloudWatch
    for instance_id in instance_ids:
        try:
            logger.info(f"Fetching CPUUtilization for instance: {instance_id}")
            result = cloudwatch.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=window,
                EndTime=datetime.now(timezone.utc),
                Period=GRANULARITY,
                Statistics=['Average']
            )
            observered_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"CPUUtilization data points for instance {instance_id}: {result.get('Datapoints', [])}")
            
            # Using the fetched data, calculate overall status (e.g., OK if avg CPU < 70%, Warning if 70-90%, Critical if > 90%)
            avg_cpu = 0
            if result.get("Datapoints"):
                avg_cpu = sum(dp["Average"] for dp in result["Datapoints"]) / len(result["Datapoints"])
            status = "OK"
            if avg_cpu > 90:
                status = "Critical"
            elif avg_cpu > 70:
                status = "Warning"

            # Build component for this instance
            ec2_metrics = {
                "id": instance_id,
                "display_name": f"EC2 Instance {instance_id}",
                "status": status,
                "observed_at": observered_at,
                "metrics": {
                    "CPUUtilization": avg_cpu
                },
                "timeline": result.get("Datapoints", []) if include_timeline else []
            }
            components.append(ec2_metrics)
        except Exception as e:
            logger.error(f"EC2 metric error for instance {instance_id}: {e}")
            ec2_metrics = {
                "id": instance_id,
                "display_name": f"EC2 Instance {instance_id}",
                "status": "Unknown",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "metrics": {"CPUUtilization": 0},
                "timeline": {}
            }
            components.append(ec2_metrics)
            continue
    return components

def fetch_db_metrics(window: datetime, include_timeline: bool = False) -> list:
    '''
    First, check Aurora Serverless database connectivity. Then, fetch database metrics from CloudWatch within the given time window. Also fetch events from RDS logs.
    Args:
        window (datetime): Start time for metrics retrieval.
        include_timeline (bool): Whether to include timeline data. Default is False.
    Returns:
        RDS component containing the following metrics:
        - CPUUtilization
        - WriteLatency: Average
    '''
    components = []
    connectivity = "unknown"
    # 1. Check DB Connectivity
    # If using TestConfig, return connection as connected without actual check
    if os.environ.get("DEBUG") == "True":
        logger.debug("TestConfig detected, skipping actual DB connectivity check.")
        connectivity = "connected"
    else:
        logger.debug("Checking actual DB connectivity.")
        try:
            conn = psycopg2.connect(
                dbname="postgres",
                user=os.environ.get("DB_USERNAME"),
                password=os.environ.get("DB_PASSWORD"),
                host=os.environ.get("DB_HOST"),
                connect_timeout=3
            )
            conn.close()
            connectivity = "connected"
        except Exception as e:
            logger.error(f"DB connectivity error: {e}")
            connectivity = f"error: {e}"
    
    # 2. Fetch RDS Metrics from CloudWatch (If using Aurora Serverlessv2)
    try:
        cpu_result = cloudwatch.get_metric_statistics(
            Namespace="AWS/RDS",
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'DBClusterIdentifier', 'Value': config.DB_CLUSTER_IDENTIFIER}],
            StartTime=window,
            EndTime=datetime.now(timezone.utc),
            Period=GRANULARITY,
            Statistics=['Average']
        )
        write_latency_result = cloudwatch.get_metric_statistics(
            Namespace="AWS/RDS",
            MetricName='WriteLatency',
            Dimensions=[{'Name': 'DBClusterIdentifier', 'Value': config.DB_CLUSTER_IDENTIFIER}],
            StartTime=window,
            EndTime=datetime.now(timezone.utc),
            Period=GRANULARITY,
            Statistics=['Average']
        )
        observered_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"RDS CPUUtilization data points: {cpu_result.get('Datapoints', [])}")
        logger.info(f"RDS WriteLatency data points: {write_latency_result.get('Datapoints', [])}")

        avg_cpu = 0
        if cpu_result.get("Datapoints"):
            avg_cpu = sum(dp["Average"] for dp in cpu_result["Datapoints"]) / len(cpu_result["Datapoints"])
        avg_write_latency = 0
        if write_latency_result.get("Datapoints"):
            avg_write_latency = sum(dp["Average"] for dp in write_latency_result["Datapoints"]) / len(write_latency_result["Datapoints"])
        
        status = "OK" if connectivity == "connected" else "Critical"

        rds_metrics = {
            "display_name": f"Aurora Serverless DB Cluster",
            "id": config.DB_CLUSTER_IDENTIFIER,
            "status": status,
            "observed_at": observered_at,
            "metrics": {
                "Connectivity": connectivity,
                "CPUUtilization": avg_cpu,
                "WriteLatency": avg_write_latency
            },
            "timeline": {
                "CPUUtilization": cpu_result.get("Datapoints", []) if include_timeline else [],
                "WriteLatency": write_latency_result.get("Datapoints", []) if include_timeline else []
            }
        }
        components.append(rds_metrics)
    except Exception as e:
        logger.error(f"RDS metric error: {e}")
        rds_metrics = {
            "display_name": "Aurora Serverless DB Cluster",
            "id": config.DB_CLUSTER_IDENTIFIER,
            "status": "Critical" if connectivity != "connected" else "OK",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {"Connectivity": connectivity, "CPUUtilization": 0, "WriteLatency": 0},
            "timeline": {}
        }
        components.append(rds_metrics)

    return components


def fetch_alb_metrics(load_balancer_arns: list, window: datetime, include_timeline: bool = False) -> list:
    '''
    Fetch ALB metrics from CloudWatch within the given time window.
    Args:
        window (datetime): Start time for metrics retrieval.
        include_timeline (bool): Whether to include timeline data. Default is False.
    Returns:
        ALB component containing the following metrics:
        - RequestCount
        - TargetResponseTime: Average
    '''
    components = []
    for alb_arn in load_balancer_arns:
        try:
            logger.info(f"Fetching ALB metrics for: {alb_arn}")
            # Extract ALB name in correct CloudWatch format (app/<name>/<id>)
            alb_name = alb_arn.split(":")[-1].replace("loadbalancer/", "")
            request_count_result = cloudwatch.get_metric_statistics(
                Namespace="AWS/ApplicationELB",
                MetricName='RequestCount',
                Dimensions=[{'Name': 'LoadBalancer', 'Value': alb_name}],
                StartTime=window,
                EndTime=datetime.now(timezone.utc),
                Period=GRANULARITY,
                Statistics=['Sum']
            )
            response_time_result = cloudwatch.get_metric_statistics(
                Namespace="AWS/ApplicationELB",
                MetricName='TargetResponseTime',
                Dimensions=[{'Name': 'LoadBalancer', 'Value': alb_name}],
                StartTime=window,
                EndTime=datetime.now(timezone.utc),
                Period=GRANULARITY,
                Statistics=['Average']
            )
            observered_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"ALB RequestCount data points for {alb_arn}: {request_count_result.get('Datapoints', [])}")
            logger.info(f"ALB TargetResponseTime data points for {alb_arn}: {response_time_result.get('Datapoints', [])}")

            avg_request_count = (sum(dp["Sum"] for dp in request_count_result.get("Datapoints", [])) / len(request_count_result["Datapoints"])
                                 if request_count_result.get("Datapoints") else None)
            avg_response_time = (sum(dp["Average"] for dp in response_time_result.get("Datapoints", [])) / len(response_time_result["Datapoints"])
                                 if response_time_result.get("Datapoints") else None)

            # Determine status
            if avg_response_time is None:
                status = "Unknown"
            else:
                status = "OK" if avg_response_time < 1 else "Warning" if avg_response_time < 3 else "Critical"
            
            alb_metrics = {
                "id": alb_arn,
                "display_name": f"Application Load Balancer",
                "status": status,
                "observed_at": observered_at,
                "metrics": {
                    "RequestCount": avg_request_count if avg_request_count is not None else 0,
                    "TargetResponseTime": avg_response_time if avg_response_time is not None else 0
                },
                "timeline": {
                    "RequestCount": request_count_result.get("Datapoints", []) if include_timeline else [],
                    "TargetResponseTime": response_time_result.get("Datapoints", []) if include_timeline else []
                }
            }
            components.append(alb_metrics)
        except Exception as e:
            logger.error(f"ALB metric error for {alb_arn}: {e}")
            components.append({
                "id": alb_arn,
                "display_name": "Application Load Balancer",
                "status": "Unknown",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "metrics": {"RequestCount": 0, "TargetResponseTime": 0},
                "timeline": {}
            })
    return components


def fetch_eb_metrics(window: datetime) -> list:
    '''
    Fetch Elastic Beanstalk environment health status.

    Also return the events log for the environment.

    Returns:
        EB Health component containing:
        - Status
        - Color
        - Causes
        - Events: List of recent events.
    '''
    components = []
    try:
        response = eb_client.describe_environment_health(
            EnvironmentName=config.ELASTIC_BEANSTALK_ENV_NAME,
            AttributeNames=['All']
        )
        logger.info(f"EB Environment Health: {response}")

        # Fetch recent events
        events_response = eb_client.describe_events(
            EnvironmentName=config.ELASTIC_BEANSTALK_ENV_NAME,
            StartTime=window,
            EndTime=datetime.now(timezone.utc),
            MaxRecords=50,
        )
        events = events_response.get("Events", [])
        logger.info(f"EB Environment Events: {events}")

        eb_metrics = {
            "id": config.ELASTIC_BEANSTALK_ENV_NAME,
            "display_name": f"Elastic Beanstalk Environment Health",
            "status": response.get("Status", "Unknown"),
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "Status Color": response.get("Color", "Unknown"),
            },
            "logs": events
        }
        components.append(eb_metrics)
    except Exception as e:
        logger.error(f"EB metric error: {e}")
        components.append({
            "id": config.ELASTIC_BEANSTALK_ENV_NAME,
            "display_name": "Elastic Beanstalk Environment Health",
            "status": "Unknown",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {"Status Color": "Unknown"},
            "logs": []
        })
    return components


def fetch_s3_metrics() -> list:
    '''
    Fetch S3 bucket metrics from CloudWatch within the given time window.
    Only for the following buckets:
        - config.S3_INGESTION_BUCKET
    Returns:
        S3 component containing the following metrics:
        - NumberOfObjects
        - BucketSizeBytes: Average
    '''
    components = []
    bucket_name = config.S3_INGESTION_BUCKET
    try:
        # Count objects in bucket
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        num_objects = response.get("KeyCount", 0)

        # Get total bucket size (approximate, using HeadBucket)
        bucket_size = 0
        for obj in response.get("Contents", []):
            bucket_size += obj.get("Size", 0)

        s3_metrics = {
            "id": bucket_name,
            "display_name": "Model Ingestion S3 Bucket",
            "status": "OK",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "NumberOfObjects": num_objects,
                "BucketSizeBytes": bucket_size
            },
            "timeline": {}
        }
        components.append(s3_metrics)
    except Exception as e:
        logger.error(f"S3 metric error for bucket {bucket_name}: {e}")
        components.append({
            "id": bucket_name,
            "display_name": "Model Ingestion S3 Bucket",
            "status": "Unknown",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {"NumberOfObjects": 0, "BucketSizeBytes": 0},
            "timeline": {}
        })
    return components


def fetch_application_logs(window: datetime) -> list:
    '''
    Fetch application logs from CloudWatch Logs within the given time window.
    Application logs are in stdout log stream of the EB environment.
    Args:
        window (datetime): Start time for logs retrieval.
    Returns:
        Application Logs component containing log events.
    Remove keys such as eventId, ingestionTime, logStreamName from each log event.
    Example log event:
    {
        "message": <log message>,
        "timestamp": <timestamp>,
    }
    '''
    components = []
    log_group = config.CLOUDWATCH_LOG_GROUP
    try:
        logger.info(f"Fetching application logs from log group: {log_group}")
        response = logs_client.filter_log_events(
            logGroupName=log_group,
            startTime=int(window.timestamp() * 1000),
            endTime=int(datetime.now(timezone.utc).timestamp() * 1000),
            limit=50
        )
        events = response.get("events", [])
        # Remove keys such as eventId, ingestionTime, logStreamName from each log event
        cleaned_events = [{"message": event.get("message", ""), "timestamp": event.get("timestamp", 0)} for event in events]
        logger.info(f"Fetched {len(cleaned_events)} log events from {log_group}")

        app_logs = {
            "id": log_group,
            "display_name": f"Application Logs",
            "status": "OK",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "timeline": cleaned_events
        }
        components.append(app_logs)
    except Exception as e:
        logger.error(f"Application logs fetch error for log group {log_group}: {e}")
        components.append({
            "id": log_group,
            "display_name": "Application Logs",
            "status": "Unknown",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "timeline": []
        })
    return components


# API Route to get system health components
@health_bp.route('/health/components', methods=['GET'])
# @check_permissions()
def system_health_components():
    """
    Return health status of various system components.

    Request Format:
    {
        "windowMinutes": <int>  # Optional, default is 60,
        "includeTimeline": <bool>  # Optional, default is False
    }

    Response Format:
    {
        "components": [
        ],
        "generated_at": "2025-11-21T17:16:00.838Z",
        "window_minutes": 5
    }
    Returns:
        200 OK: If health status retrieval is successful.
        400 Bad Request: If the request format is invalid.
    """
    # Check if request is JSON
    if not request or not request.is_json:
        return jsonify({'error': 'Invalid request format.'}), 400
    
    # Access request data
    req_data = request.get_json() or {}

    window_minutes = int(req_data.get("windowMinutes", 60))
    include_timeline = req_data.get("includeTimeline", False)

    window = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    # Build components
    components = []

    # Fetch component data (use threading or async if needed for performance)
    # 1. Fetch Elastic Beanstalk ENvironment Resources to get instance IDs
    eb_resources = fetch_eb_env_resource()
    instance_ids = [inst["Id"] for inst in eb_resources.get("Instances", [])] if eb_resources else []
    load_balancer_arns = [lb["Name"] for lb in eb_resources.get("LoadBalancers", [])] if eb_resources else []
    logger.debug(f"EB Instances: {instance_ids}, Load Balancers: {load_balancer_arns}")

    # 1. Elastic Beanstalk Metrics
    eb_metrics = fetch_eb_metrics(window)
    logger.info("Fetched EB health component")
    components.extend(eb_metrics if eb_metrics else [])
    
    # 2. EC2 Metrics
    ec2_metrics = fetch_ec2_metrics(instance_ids, window, include_timeline)
    logger.info("Fetched EC2 data component")
    components.extend(ec2_metrics if ec2_metrics else [])
    
    # 3. Aurora Serverlessv2 Database Connectivity + Metrics
    db_metrics = fetch_db_metrics(window, include_timeline)
    logger.info("Fetched Database connectivity component")
    components.extend(db_metrics if db_metrics else [])

    # 4. S3 Metrics
    s3_metrics = fetch_s3_metrics()
    logger.info("Fetched S3 data component")
    components.extend(s3_metrics if s3_metrics else [])

    # 5. ALB Metrics
    alb_metrics = fetch_alb_metrics(load_balancer_arns, window, include_timeline)
    logger.info("Fetched ALB data component")
    components.extend(alb_metrics if alb_metrics else [])

    # 6. Application Logs
    app_logs = fetch_application_logs(window)
    logger.info("Fetched Application Logs component")
    components.extend(app_logs if app_logs else [])

    # Build response
    response = {
        "components": components,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_minutes": window
    }

    return jsonify(response), 200