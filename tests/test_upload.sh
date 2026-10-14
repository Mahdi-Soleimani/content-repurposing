#!/bin/bash
set -e

echo "1. Init Upload..."
INIT_RES=$(curl -s -X POST http://localhost:8000/api/uploads/init \
  -H "Content-Type: application/json" \
  -d '{"project_id":"project_123","filename":"video.mp4","content_type":"video/mp4","file_size":15}')

UPLOAD_ID=$(echo $INIT_RES | grep -o '"upload_id":"[^"]*' | cut -d'"' -f4)
UPLOAD_URL=$(echo $INIT_RES | grep -o '"upload_url":"[^"]*' | cut -d'"' -f4)

echo "Upload ID: $UPLOAD_ID"

echo "2. Upload File to S3..."
curl -s -X PUT "$UPLOAD_URL" \
  -H "Content-Type: video/mp4" \
  -d "test video data"

echo "3. Complete Upload..."
COMPLETE_RES=$(curl -s -X POST http://localhost:8000/api/uploads/$UPLOAD_ID/complete)
echo $COMPLETE_RES

echo "4. Polling Status..."
curl -s http://localhost:8000/api/uploads/$UPLOAD_ID

echo -e "\n\n5. Test Upload Failure..."
INIT_FAIL=$(curl -s -X POST http://localhost:8000/api/uploads/init \
  -H "Content-Type: application/json" \
  -d '{"project_id":"project_123","filename":"fail.mp4","content_type":"video/mp4"}')
FAIL_ID=$(echo $INIT_FAIL | grep -o '"upload_id":"[^"]*' | cut -d'"' -f4)

echo "Completing without upload (should fail)..."
curl -s -X POST http://localhost:8000/api/uploads/$FAIL_ID/complete || true

