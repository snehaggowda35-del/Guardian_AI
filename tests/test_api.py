import os
import uuid
os.environ['DATABASE_URL'] = 'sqlite:///./test_guardian.db'
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
def test_health(): assert client.get('/health').json()['status'] == 'ok'

def test_parent_can_register_and_login():
    email = f"parent-{uuid.uuid4().hex[:8]}@example.com"
    registered = client.post('/api/v1/auth/register', json={'name':'Test Parent','email':email,'password':'SecurePass1234'})
    assert registered.status_code == 200, registered.text
    token = registered.json()['access_token']
    logged_in = client.post('/api/v1/auth/login', json={'email':email,'password':'SecurePass1234'})
    assert logged_in.status_code == 200
    assert logged_in.json()['access_token']
    assert logged_in.json()['access_token'] != ''

def test_parent_can_revoke_and_reset_devices():
    email = f"devices-{uuid.uuid4().hex[:8]}@example.com"
    auth = client.post('/api/v1/auth/register', json={'name':'Device Parent','email':email,'password':'SecurePass1234'}).json()
    headers = {'Authorization':'Bearer ' + auth['access_token']}
    code = client.post('/api/v1/devices/codes', headers=headers, json={}).json()['code']
    device_id = client.post('/api/v1/devices/link', json={'code':code}).json()['device_id']
    assert client.delete('/api/v1/devices/' + device_id, headers=headers).json()['status'] == 'revoked'
    assert client.post('/api/v1/devices/reset', headers=headers).json()['revoked'] >= 1

def test_duplicate_message_creates_only_one_alert():
    email = f"dedupe-{uuid.uuid4().hex[:8]}@example.com"
    auth = client.post('/api/v1/auth/register', json={'name':'Dedupe Parent','email':email,'password':'SecurePass1234'}).json()
    headers = {'Authorization':'Bearer ' + auth['access_token']}
    code = client.post('/api/v1/devices/codes', headers=headers, json={}).json()['code']
    device_id = client.post('/api/v1/devices/link', json={'code':code}).json()['device_id']
    payload = {'device_id':device_id,'source':'web_message','text':'I am planning to kill myself'}
    first = client.post('/api/v1/analyze', json=payload)
    second = client.post('/api/v1/analyze', json=payload)
    assert first.status_code == 200 and first.json()['alert_created'] is True
    assert second.status_code == 200 and second.json()['deduplicated'] is True
    alerts = client.get('/api/v1/alerts', headers=headers).json()
    assert len([alert for alert in alerts if alert['trigger_text'] == payload['text']]) == 1
