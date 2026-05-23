import json

def handler(request):
    # Attempt to use lightweight color fallback; avoid heavy TF imports if not available
    try:
        body = {}
        try:
            body = request.json() if callable(getattr(request, 'json', None)) else json.loads(request.body.decode())
        except Exception:
            body = {}

        crop = body.get('crop', 'Tomato')
        image_b64 = body.get('image')

        # Import the internal module but guard heavy imports
        try:
            from ml_service import disease as disease_mod
            if image_b64:
                r = disease_mod.predict_disease(crop, image_b64)
            else:
                r = disease_mod.predict_disease(crop, None)
            return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(r)}
        except Exception as e:
            # Likely heavy ML dependencies or missing model files
            return {"statusCode": 503, "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error":"model_unavailable","detail": str(e), "message": "Disease detection requires heavy ML dependencies or model files — consider deploying backend as a container on Render/Fly/Cloud Run."})}

    except Exception as e:
        return {"statusCode": 500, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error":"internal","detail": str(e)})}
