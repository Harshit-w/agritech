import json

def handler(request):
    body = {"status": "ok", "service": "AgriTech (serverless)", "timestamp": None}
    try:
        import time
        body["timestamp"] = time.time()
    except Exception:
        body["timestamp"] = None
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
