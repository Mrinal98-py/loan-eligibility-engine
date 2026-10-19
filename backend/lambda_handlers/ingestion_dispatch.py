import json
import boto3
from backend.app.settings import get_settings


def handler(event, context):
    """
    AWS Lambda Handler triggered by S3 ObjectCreated events.
    Enqueues upload processing jobs into Amazon SQS for asynchronous worker ingestion.
    """
    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.AWS_REGION)

    records = event.get("Records", [])
    dispatched_count = 0

    for record in records:
        s3_data = record.get("s3", {})
        bucket_name = s3_data.get("bucket", {}).get("name")
        object_key = s3_data.get("object", {}).get("key")

        if not bucket_name or not object_key:
            continue

        message_body = {
            "bucket_name": bucket_name,
            "object_key": object_key,
            "event_time": record.get("eventTime"),
        }

        if settings.SQS_QUEUE_URL:
            sqs.send_message(
                QueueUrl=settings.SQS_QUEUE_URL,
                MessageBody=json.dumps(message_body),
            )
            dispatched_count += 1

    return {
        "status": "SUCCESS",
        "dispatched_count": dispatched_count,
    }
