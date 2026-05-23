import json

def _safe_call_get_sensor_readings():
    try:
        from services.sensors import get_sensor_readings
        return get_sensor_readings()
    except Exception as e:
        return {"error": "sensor_unavailable", "detail": str(e)}

def handler(request):
    data = _safe_call_get_sensor_readings()
    status = 200 if "error" not in data else 503
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data),
    }
