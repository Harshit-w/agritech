import json

def handler(request):
    try:
        body = request.json() if callable(getattr(request, 'json', None)) else json.loads(request.body.decode())
    except Exception:
        body = {}
    try:
        from ml_service.crop import predict_crop
        r = predict_crop(**body)
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(r)}
    except Exception as e:
        return {"statusCode": 503, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error":"crop_unavailable","detail": str(e)})}
