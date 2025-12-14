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
from src.logger import get_logger
import os
import boto3
import psycopg2

# Blueprint setup
health_bp = Blueprint("health_bp", __name__)
config = TestConfig if os.environ.get("DEBUG") == "True" else Config
logger = get_logger("api.health")

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")

# AWS Components (assumed to be set in .env or environment)
ELASTIC_BEANSTALK_ENV_NAME = os.environ.get("ELASTIC_BEANSTALK_ENV_NAME")
S3_INGESTION_BUCKET = os.environ.get("BUCKET_NAME")
DB_CLUSTER_IDENTIFIER = os.environ.get("DB_CLUSTER_IDENTIFIER")
CLOUDWATCH_LOG_GROUP = os.environ.get("CLOUDWATCH_LOG_GROUP")

# Metric Granularity
GRANULARITY = 60  # 1 minute granularity for metrics, meaning that data points are aggregated over 1 minute intervals

# Health Check Route
@health_bp.route('/health', methods=['GET'])
def health():
    """
    Health check route.
    Returns:
        200 OK: If the service is reachable.
    """
    return jsonify({'message': 'Service reachable.', "timestamp": datetime.now(timezone.utc).isoformat()}), 200

# AWS Helper functions to fetch metrics and logs
def fetch_eb_env_resource() -> dict:
    '''
    Fetch Elastic Beanstalk environment resources.
    Returns:
        EnvironmentResources dict from EB describe_environment_resources API.
    '''
    try:
        eb_client = boto3.client("elasticbeanstalk", region_name=AWS_REGION)
        response = eb_client.describe_environment_resources(
            EnvironmentName=ELASTIC_BEANSTALK_ENV_NAME
        )
        logger.debug(f"EB Environment Resources: {response}")
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
    # For each instance, fetch CPUUtilization metric from CloudWatch.
    cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
    for instance_id in instance_ids:
        try:
            logger.debug(f"Fetching CPUUtilization for instance: {instance_id}")
            result = cloudwatch.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=window,
                EndTime=datetime.now(timezone.utc),
                Period=GRANULARITY,
                Statistics=['Average']
            )
            observed_at = datetime.now(timezone.utc).isoformat()
            logger.debug(f"CPUUtilization data points for instance {instance_id}: {result.get('Datapoints', [])}")
            
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
                "observed_at": observed_at,
                "metrics": {
                    "CPUUtilization": avg_cpu
                },
                "timeline": {"CPUUtilization": result.get("Datapoints", [])} if include_timeline else {}
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
    return components

def fetch_db_metrics(window: datetime, include_timeline: bool = False) -> list:
    '''
    First, check Aurora Serverless database connectivity. Then, fetch database metrics from CloudWatch within the given time window. Also fetch events from RDS logs.
    Args:
        window (datetime): Start time for metrics retrieval.
        include_timeline (bool): Whether to include timeline data. Default is False.
    Returns:
        RDS component containing the following metrics:
        - Connectivity: connected / error message
        - CPUUtilization
        - WriteLatency: Average
    '''
    components = []

    # 1. Fetch RDS Metrics from CloudWatch (If using Aurora Serverlessv2)
    try:
        cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
        cpu_result = cloudwatch.get_metric_statistics(
            Namespace="AWS/RDS",
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'DBClusterIdentifier', 'Value': DB_CLUSTER_IDENTIFIER}],
            StartTime=window,
            EndTime=datetime.now(timezone.utc),
            Period=GRANULARITY,
            Statistics=['Average']
        )
        write_latency_result = cloudwatch.get_metric_statistics(
            Namespace="AWS/RDS",
            MetricName='WriteLatency',
            Dimensions=[{'Name': 'DBClusterIdentifier', 'Value': DB_CLUSTER_IDENTIFIER}],
            StartTime=window,
            EndTime=datetime.now(timezone.utc),
            Period=GRANULARITY,
            Statistics=['Average']
        )
        observed_at = datetime.now(timezone.utc).isoformat()
        logger.debug(f"RDS CPUUtilization data points: {cpu_result.get('Datapoints', [])}")
        logger.debug(f"RDS WriteLatency data points: {write_latency_result.get('Datapoints', [])}")

        avg_cpu = 0
        if cpu_result.get("Datapoints"):
            avg_cpu = sum(dp["Average"] for dp in cpu_result["Datapoints"]) / len(cpu_result["Datapoints"])
        avg_write_latency = 0
        if write_latency_result.get("Datapoints"):
            avg_write_latency = sum(dp["Average"] for dp in write_latency_result["Datapoints"]) / len(write_latency_result["Datapoints"])
        
        metrics_present = bool(cpu_result.get("Datapoints") and write_latency_result.get("Datapoints"))
        status = "OK" if metrics_present else "Critical"

        rds_metrics = {
            "display_name": f"Aurora Serverless DB Cluster",
            "id": DB_CLUSTER_IDENTIFIER,
            "status": status,
            "observed_at": observed_at,
            "metrics": {
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
            "id": DB_CLUSTER_IDENTIFIER,
            "status": "ERROR",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {"CPUUtilization": 0, "WriteLatency": 0},
            "timeline": {}
        }
        components.append(rds_metrics)

    return components


def fetch_alb_metrics(load_balancer_arns: list, window: datetime, include_timeline: bool = False) -> list:
    '''
    Fetch ALB metrics from CloudWatch within the given time window.
    Args:
        load_balancer_arns (list): List of ALB ARNs.
        window (datetime): Start time for metrics retrieval.
        include_timeline (bool): Whether to include timeline data. Default is False.
    Returns:
        ALB component containing the following metrics:
        - RequestCount
        - TargetResponseTime: Average
    '''
    components = []
    cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
    for alb_arn in load_balancer_arns:
        try:
            logger.debug(f"Fetching ALB metrics for: {alb_arn}")
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
            observed_at = datetime.now(timezone.utc).isoformat()
            logger.debug(f"ALB RequestCount data points for {alb_arn}: {request_count_result.get('Datapoints', [])}")
            logger.debug(f"ALB TargetResponseTime data points for {alb_arn}: {response_time_result.get('Datapoints', [])}")

            avg_request_count = (sum(dp["Sum"] for dp in request_count_result.get("Datapoints", [])) / len(request_count_result["Datapoints"])
                                 if request_count_result.get("Datapoints") else None)
            avg_response_time = (sum(dp["Average"] for dp in response_time_result.get("Datapoints", [])) / len(response_time_result["Datapoints"])
                                 if response_time_result.get("Datapoints") else None)

            # Determine status
            if avg_response_time is None:
                status = "Unknown"
            else:
                status = "OK" if avg_response_time < 3 else "Warning" if avg_response_time < 5 else "Critical"
            
            alb_metrics = {
                "id": alb_arn,
                "display_name": f"Application Load Balancer",
                "status": status,
                "observed_at": observed_at,
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
        eb_client = boto3.client("elasticbeanstalk", region_name=AWS_REGION)
        response = eb_client.describe_environment_health(
            EnvironmentName=ELASTIC_BEANSTALK_ENV_NAME,
            AttributeNames=['All']
        )
        logger.debug(f"EB Environment Health: {response}")

        # Fetch recent events
        events_response = eb_client.describe_events(
            EnvironmentName=ELASTIC_BEANSTALK_ENV_NAME,
            StartTime=window,
            EndTime=datetime.now(timezone.utc),
            MaxRecords=50,
        )
        events = events_response.get("Events", [])
        logger.debug(f"EB Environment Events: {events}")

        eb_metrics = {
            "id": ELASTIC_BEANSTALK_ENV_NAME,
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
            "id": ELASTIC_BEANSTALK_ENV_NAME,
            "display_name": "Elastic Beanstalk Environment Health",
            "status": "Unknown",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {"Status Color": "Unknown"},
            "logs": []
        })
    return components


def fetch_s3_metrics() -> list:
    '''
    Fetch a point-in-time snapshot of S3 bucket metrics.
    Only for the following buckets:
        - BUCKET_NAME
    Returns:
        S3 component containing the following metrics:
        - NumberOfObjects
        - BucketSizeBytes: Average
    '''
    components = []
    bucket_name = S3_INGESTION_BUCKET
    try:
        s3_client = boto3.client("s3", region_name=AWS_REGION)
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket_name)

        num_objects = 0
        bucket_size = 0
        for page in page_iterator:
            contents = page.get('Contents', [])
            num_objects += len(contents)
            for obj in contents:
                bucket_size += obj.get('Size', 0)

        status = "OK" if num_objects > 0 else "Empty"

        s3_metrics = {
            "id": bucket_name,
            "display_name": "Model Ingestion S3 Bucket",
            "status": status,
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
    log_group = CLOUDWATCH_LOG_GROUP
    try:
        logs_client = boto3.client("logs", region_name=AWS_REGION)
        logger.debug(f"Fetching application logs from log group: {log_group}")
        response = logs_client.filter_log_events(
            logGroupName=log_group,
            startTime=int(window.timestamp() * 1000),
            endTime=int(datetime.now(timezone.utc).timestamp() * 1000),
            limit=50
        )
        events = response.get("events", [])
        # Remove keys such as eventId, ingestionTime, logStreamName from each log event
        cleaned_events = [{"message": event.get("message", ""), "timestamp": event.get("timestamp", 0)} for event in events]
        logger.debug(f"Fetched {len(cleaned_events)} log events from {log_group}")

        app_logs = {
            "id": log_group,
            "display_name": f"Application Logs",
            "status": "OK",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "logs": cleaned_events
        }
        components.append(app_logs)
    except Exception as e:
        logger.error(f"Application logs fetch error for log group {log_group}: {e}")
        components.append({
            "id": log_group,
            "display_name": "Application Logs",
            "status": "Unknown",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "timeline": {}
        })
    return components


# API Route to get system health components
@health_bp.route('/health/components', methods=['GET'])
@check_permissions()
def system_health_components():
    """
    Return health status of various system components.

    Request Format:
    /health/components?windowMinutes=60&includeTimeline=true

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
        401 Unauthorized: If authentication fails.
        403 Forbidden: If the user lacks necessary permissions.
    """
    # Access query parameters
    req_data = request.args.to_dict()

    # Validate allowed keys
    allowed_keys = {"windowMinutes", "includeTimeline"}
    if any(key not in allowed_keys for key in req_data.keys()):
        return jsonify({"message": "Invalid request format."}), 400

    # Get values with defaults
    try:
        window_minutes = int(req_data.get("windowMinutes", 60))
    except (ValueError, TypeError):
        return jsonify({"message": "windowMinutes must be an integer."}), 400
    
    # Ensure window_minutes is between 5 and 1440
    if window_minutes < 5:
        return jsonify({"message": "Window Minutes must be a positive integer greater than or equal to 5."}), 400
    elif window_minutes > 1440:
        return jsonify({"message": "Window Minutes must not exceed 1440 (24 hours)."}), 400

    # Ensure includeTimeline is a boolean, if not return 400
    include_timeline_raw = req_data.get("includeTimeline", None)
    if include_timeline_raw is None:
        include_timeline = False
    else:
        if isinstance(include_timeline_raw, bool):
            include_timeline = include_timeline_raw
        elif isinstance(include_timeline_raw, str):
            v = include_timeline_raw.strip().lower()
            if v in ("true", "1"): 
                include_timeline = True
            elif v in ("false", "0"):
                include_timeline = False
            else:
                return jsonify({"message": "includeTimeline must be a boolean."}), 400
        else:
            return jsonify({"message": "includeTimeline must be a boolean."}), 400

    window = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    components = []

    # 0. Fetch Elastic Beanstalk Environment Resources to get instance IDs
    eb_resources = fetch_eb_env_resource()
    instance_ids = [inst["Id"] for inst in eb_resources.get("Instances", [])] if eb_resources else []
    load_balancer_arns = [lb["Name"] for lb in eb_resources.get("LoadBalancers", [])] if eb_resources else []
    logger.debug(f"EB Instances: {instance_ids}, Load Balancers: {load_balancer_arns}")

    # 1. Elastic Beanstalk Metrics
    eb_metrics = fetch_eb_metrics(window)
    logger.debug("Fetched EB health component")
    components.extend(eb_metrics if eb_metrics else [])
    
    # 2. EC2 Metrics
    if instance_ids:
        ec2_metrics = fetch_ec2_metrics(instance_ids, window, include_timeline)
        logger.debug("Fetched EC2 data component")
        components.extend(ec2_metrics if ec2_metrics else [])
    else:
        logger.warning("No EC2 instances found in EB environment; skipping EC2 metrics fetch.")
        ec2_metrics = {
                "id": "UNKNOWN",
                "display_name": "EC2 Instance UNKNOWN - No Instances Found",
                "status": "Unknown",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "metrics": {"CPUUtilization": 0},
                "timeline": {}
            }
        components.append(ec2_metrics)
        
    
    # 3. Aurora Serverlessv2 Database Connectivity + Metrics
    db_metrics = fetch_db_metrics(window, include_timeline)
    logger.debug("Fetched Database connectivity component")
    components.extend(db_metrics if db_metrics else [])

    # 4. S3 Metrics
    s3_metrics = fetch_s3_metrics()
    logger.debug("Fetched S3 data component")
    components.extend(s3_metrics if s3_metrics else [])

    # 5. ALB Metrics
    if load_balancer_arns:
        alb_metrics = fetch_alb_metrics(load_balancer_arns, window, include_timeline)
        logger.debug("Fetched ALB data component")
        components.extend(alb_metrics if alb_metrics else [])
    else:
        logger.warning("No Load Balancers found in EB environment; skipping ALB metrics fetch.")
        alb_metrics = {
                "id": "UNKNOWN",
                "display_name": "Application Load Balancer UNKNOWN - No Load Balancers Found",
                "status": "Unknown",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "metrics": {"RequestCount": 0, "TargetResponseTime": 0},
                "timeline": {}
            }
        components.append(alb_metrics)

    # 6. Application Logs - only if requested
    if include_timeline:
        app_logs = fetch_application_logs(window)
        logger.debug("Fetched Application Logs component")
        components.extend(app_logs if app_logs else [])

    # Build response
    response = {
        "components": components,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_minutes": window_minutes
    }

    return jsonify(response), 200