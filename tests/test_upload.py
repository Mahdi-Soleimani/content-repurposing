import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

print("1. Testing Successful Upload Flow")
# 1. Init
res = requests.post(f"{BASE_URL}/uploads/init", json={
    "project_id": "66245901-90ca-4e7d-94ff-1a7e349b75b9",
    "filename": "test_success.txt",
    "content_type": "text/plain",
    "file_size": 13
})
data = res.json()
print("Init Response:", json.dumps(data, indent=2))
upload_id = data["upload_id"]
upload_url = data["upload_url"]

# 2. Upload to MinIO
# Since we are running the test outside docker, replace 'minio' with 'localhost'
upload_url = upload_url.replace("http://minio:9000", "http://localhost:9000")
print(f"Uploading to S3: {upload_url[:50]}...")
res_s3 = requests.put(upload_url, data="Hello, World!", headers={"Content-Type": "text/plain"})
print("S3 Upload Status:", res_s3.status_code)

# 3. Complete
print("Completing Upload...")
res_complete = requests.post(f"{BASE_URL}/uploads/{upload_id}/complete")
print("Complete Response:", json.dumps(res_complete.json(), indent=2))

# 4. Check Status
print("Checking Status...")
res_status = requests.get(f"{BASE_URL}/uploads/{upload_id}")
print("Status Response:", json.dumps(res_status.json(), indent=2))


print("\n2. Testing Failed Upload Flow")
res_fail = requests.post(f"{BASE_URL}/uploads/init", json={
    "project_id": "66245901-90ca-4e7d-94ff-1a7e349b75b9",
    "filename": "test_fail.txt",
    "content_type": "text/plain"
})
fail_id = res_fail.json()["upload_id"]

# Don't upload, just call complete
print("Attempting to complete without uploading...")
res_fail_complete = requests.post(f"{BASE_URL}/uploads/{fail_id}/complete")
print("Complete (Expected Error) Status:", res_fail_complete.status_code)
print("Complete (Expected Error) Response:", json.dumps(res_fail_complete.json(), indent=2))

print("Checking Status of Failed Upload...")
res_fail_status = requests.get(f"{BASE_URL}/uploads/{fail_id}")
print("Status Response:", json.dumps(res_fail_status.json(), indent=2))

