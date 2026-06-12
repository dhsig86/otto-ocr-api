from fastapi.testclient import TestClient
import pytest
from unittest.mock import MagicMock, patch
from main import app
from middleware.require_auth import verify_firebase_token

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "OTTO OCR microservice"

def test_ping():
    response = client.get("/ping")
    assert response.status_code == 200
    assert "version" in response.json()
    assert "files" in response.json()

@patch('main.get_job')
def test_get_ocr_result_not_found(mock_get_job):
    mock_get_job.return_value = None
    response = client.get("/ocr/non-existent-job/result")
    assert response.status_code == 200
    assert response.json() == {"error": "Not Found"}

@patch('main.get_job')
def test_get_ocr_result_found(mock_get_job):
    mock_get_job.return_value = {"job_id": "test-id", "status": "completed", "result": "some_data"}
    response = client.get("/ocr/test-id/result")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

@patch('main.get_job')
@patch('main.save_validation')
@patch('main.update_validation_status')
def test_validate_ocr_result(mock_update_val, mock_save_val, mock_get_job):
    # Mock return values
    mock_get_job.return_value = {"job_id": "test-id", "status": "completed"}
    
    # Override auth dependency
    app.dependency_overrides[verify_firebase_token] = lambda: "test_doctor_uid"
    
    payload = {
        "is_correct": True,
        "corrections": None
    }
    
    response = client.post("/ocr/test-id/validate", json=payload)
    
    # Clean overrides
    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    assert response.json() == {"status": "success", "persisted": True}
    mock_save_val.assert_called_once_with("test-id", True, None)
