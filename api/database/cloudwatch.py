"""CloudWatch metrics fetcher with in-memory caching."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# In-memory cache
_cache: Dict[str, Any] = {}
_cache_ts: float = 0
CACHE_TTL = 60  # seconds

# AWS resource identifiers (match infra/cloudwatch-dashboard.json)
REGION = os.getenv("AWS_REGION", "us-east-2")
ECS_CLUSTER = os.getenv("CW_ECS_CLUSTER", "hcai-cluster")
ECS_SERVICE = os.getenv("CW_ECS_SERVICE", "hcai-backend-service")
ALB_ID = os.getenv("CW_ALB_ID", "app/hcai-alb/0e1f7eb0be4bf20c")
RDS_INSTANCE = os.getenv("CW_RDS_INSTANCE", "hcai-db")


def _build_metric_queries() -> List[Dict[str, Any]]:
    """Build the GetMetricData query list for all 7 metrics."""
    return [
        {
            "Id": "ecs_cpu",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/ECS",
                    "MetricName": "CPUUtilization",
                    "Dimensions": [
                        {"Name": "ClusterName", "Value": ECS_CLUSTER},
                        {"Name": "ServiceName", "Value": ECS_SERVICE},
                    ],
                },
                "Period": 300,
                "Stat": "Average",
            },
        },
        {
            "Id": "ecs_memory",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/ECS",
                    "MetricName": "MemoryUtilization",
                    "Dimensions": [
                        {"Name": "ClusterName", "Value": ECS_CLUSTER},
                        {"Name": "ServiceName", "Value": ECS_SERVICE},
                    ],
                },
                "Period": 300,
                "Stat": "Average",
            },
        },
        {
            "Id": "alb_requests",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/ApplicationELB",
                    "MetricName": "RequestCount",
                    "Dimensions": [
                        {"Name": "LoadBalancer", "Value": ALB_ID},
                    ],
                },
                "Period": 300,
                "Stat": "Sum",
            },
        },
        {
            "Id": "alb_p50",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/ApplicationELB",
                    "MetricName": "TargetResponseTime",
                    "Dimensions": [
                        {"Name": "LoadBalancer", "Value": ALB_ID},
                    ],
                },
                "Period": 300,
                "Stat": "p50",
            },
        },
        {
            "Id": "alb_p99",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/ApplicationELB",
                    "MetricName": "TargetResponseTime",
                    "Dimensions": [
                        {"Name": "LoadBalancer", "Value": ALB_ID},
                    ],
                },
                "Period": 300,
                "Stat": "p99",
            },
        },
        {
            "Id": "rds_cpu",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/RDS",
                    "MetricName": "CPUUtilization",
                    "Dimensions": [
                        {"Name": "DBInstanceIdentifier", "Value": RDS_INSTANCE},
                    ],
                },
                "Period": 300,
                "Stat": "Average",
            },
        },
        {
            "Id": "rds_connections",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/RDS",
                    "MetricName": "DatabaseConnections",
                    "Dimensions": [
                        {"Name": "DBInstanceIdentifier", "Value": RDS_INSTANCE},
                    ],
                },
                "Period": 300,
                "Stat": "Average",
            },
        },
    ]


def _format_result(result: Dict[str, Any], query: Dict[str, Any]) -> Dict[str, Any]:
    """Format a single MetricDataResult into our response shape."""
    stat = query["MetricStat"]
    timestamps = [
        ts.isoformat() if isinstance(ts, datetime) else str(ts)
        for ts in result.get("Timestamps", [])
    ]
    values = [round(v, 3) for v in result.get("Values", [])]

    # CloudWatch returns newest-first; reverse for chronological sparklines
    if timestamps and values:
        pairs = sorted(zip(timestamps, values))
        timestamps = [p[0] for p in pairs]
        values = [p[1] for p in pairs]

    return {
        "id": result["Id"],
        "namespace": stat["Metric"]["Namespace"],
        "metricName": stat["Metric"]["MetricName"],
        "stat": stat["Stat"],
        "timestamps": timestamps,
        "values": values,
        "latest": values[-1] if values else None,
    }


def get_cloudwatch_metrics() -> Dict[str, Any]:
    """Fetch CloudWatch metrics with 60s in-memory cache.

    Returns dict with metrics list, cached flag, and fetched_at timestamp.
    On error, returns stale cache if available or error response.
    """
    global _cache, _cache_ts

    now = time.time()
    if _cache and (now - _cache_ts) < CACHE_TTL:
        return {**_cache, "cached": True}

    try:
        import boto3

        client = boto3.client("cloudwatch", region_name=REGION)
        queries = _build_metric_queries()

        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=3)

        response = client.get_metric_data(
            MetricDataQueries=queries,
            StartTime=start,
            EndTime=end,
        )

        # Build lookup from query Id to query definition
        query_map = {q["Id"]: q for q in queries}

        metrics = []
        for result in response.get("MetricDataResults", []):
            query = query_map.get(result["Id"])
            if query:
                metrics.append(_format_result(result, query))

        _cache = {
            "metrics": metrics,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        _cache_ts = now

        return {**_cache, "cached": False}

    except Exception as e:
        logger.warning("CloudWatch fetch failed: %s", e)
        # Return stale cache if available
        if _cache:
            return {**_cache, "cached": True, "stale": True}
        return {
            "error": str(e),
            "metrics": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
        }
