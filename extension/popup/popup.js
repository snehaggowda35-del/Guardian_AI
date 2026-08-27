const $ = s => document.querySelector(s);
function renderConnection(deviceId) {
  $('#link-section').hidden = !!deviceId;
  $('#connected-section').hidden = !deviceId;
  $('#status').textContent = deviceId ? 'This browser is linked.' : 'Not linked yet.';
}

chrome.storage.local.get(['apiUrl', 'deviceId', 'chatSelector'], async c => {
  if (!c.deviceId) { const synced = await chrome.storage.sync.get(['apiUrl', 'deviceId']); c = {...c, ...synced}; }
  $('#apiUrl').value = c.apiUrl || 'http://127.0.0.1:8000';
  $('#selector').value = c.chatSelector || '';
  renderConnection(c.deviceId);
});

$('#link').onclick = async () => {
  const apiUrl = $('#apiUrl').value.replace(/\/$/, '');
  const code = $('#code').value.trim();
  if (!code) return $('#status').textContent = 'Enter the six-character link code.';
  try {
    const apiOrigin = new URL(apiUrl).origin + '/*';
    const hasApiPermission = await chrome.permissions.contains({origins:[apiOrigin]});
    if (!hasApiPermission && !(await chrome.permissions.request({origins:[apiOrigin]}))) throw Error('Chrome did not grant access to the Guardian AI API.');
    const r = await fetch(apiUrl + '/api/v1/devices/link', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({code, label:'Child Chrome browser'})});
    const data = await r.json();
    if (!r.ok) throw Error(data.detail || 'Device link failed.');
    await chrome.storage.local.set({apiUrl, deviceId:data.device_id});
    await chrome.storage.sync.set({apiUrl, deviceId:data.device_id});
    renderConnection(data.device_id);
  } catch (e) { $('#status').textContent = 'Link error: ' + e.message; }
};

$('#unlink').onclick = async () => {
  await chrome.storage.local.remove('deviceId');
  await chrome.storage.sync.remove('deviceId');
  renderConnection('');
  $('#status').textContent = 'Unlinked. Generate a new code to connect again.';
};

$('#enable').onclick = async () => {
  try {
    const [tab] = await chrome.tabs.query({active:true, currentWindow:true});
    if (!tab?.id || !tab.url || !/^https?:/.test(tab.url)) throw Error('Open WhatsApp Web or another normal web page first.');
    const selector = $('#selector').value.trim() || (new URL(tab.url).hostname === 'web.whatsapp.com' ? '[data-testid="msg-container"]' : '');
    if (!selector) throw Error('Enter a CSS selector for visible messages.');
    const origin = new URL(tab.url).origin + '/*';
    const granted = await chrome.permissions.request({origins:[origin]});
    if (!granted) throw Error('Chrome did not grant access to this site.');
    await chrome.storage.local.set({chatSelector:selector});
    await chrome.scripting.executeScript({target:{tabId:tab.id}, files:['content/chat-reader.js']});
    $('#status').textContent = 'Enabled on ' + new URL(tab.url).hostname + '. It will run automatically when this site opens.';
  } catch (e) { $('#status').textContent = 'Enable error: ' + e.message; }
};
