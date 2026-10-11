from fastapi.testclient import TestClient

from app.main import app


def test_phone_app_serves_voice_ui_and_pwa_assets():
    with TestClient(app) as client:
        page = client.get("/app")
        manifest = client.get("/app/manifest.json")
        service_worker = client.get("/app/sw.js")

    assert page.status_code == 200
    # Keep this assertion aligned with the shipped V1 voice UI label.
    assert "V1 voice test" in page.text
    assert "SpeechRecognition" in page.text
    assert "/v1/missions" in page.text
    assert manifest.status_code == 200
    assert manifest.json()["start_url"] == "/app"
    assert manifest.json()["display"] == "standalone"
    assert service_worker.status_code == 200
    assert "serviceWorker" not in service_worker.text
    assert "self.addEventListener(\"fetch\"" in service_worker.text



def test_phone_app_displays_and_speaks_real_mission_response():
    with TestClient(app) as client:
        page = client.get("/app")

    assert page.status_code == 200
    assert "function extractMissionResponse(result)" in page.text
    assert 'const response=extractMissionResponse(mission.result)' in page.text
    assert 'speak(response.slice(0,1200))' in page.text
    assert 'Mission completed, but I couldn\'t extract a readable response.' in page.text
