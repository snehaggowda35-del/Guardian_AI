// Optional generic adapter. The parent explicitly enables a site in the popup.
// Replace any previous observer so extension reloads never leave a stale reader.
(() => {
  if (typeof globalThis.__guardianChatReaderCleanup === 'function') globalThis.__guardianChatReaderCleanup();
  const seenNodes = new WeakSet();
  function extract() {
    if (!globalThis.chrome?.storage?.local) return;
    chrome.storage.local.get(['chatSelector'], ({ chatSelector }) => {
      const selectors = location.hostname === 'web.whatsapp.com'
        ? [...(chatSelector ? [chatSelector] : []), '[data-testid="msg-container"]', 'div.message-in', 'div.message-out', 'div.copyable-text', '[data-pre-plain-text]', 'span.selectable-text']
        : (chatSelector ? [chatSelector] : []);
      for (const selector of selectors) {
        try {
          document.querySelectorAll(selector).forEach(node => {
            if (seenNodes.has(node)) return;
            const text = (node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim();
            if (!text || text.length >= 1001) return;
            seenNodes.add(node);
            chrome.runtime.sendMessage({ type: 'guardian-event', source: 'web_message', text });
          });
        } catch (error) { console.warn('Guardian AI selector invalid', selector, error); }
      }
    });
  }
  const observer = new MutationObserver(extract);
  observer.observe(document.documentElement, { subtree: true, childList: true, characterData: true });
  globalThis.__guardianChatReaderCleanup = () => observer.disconnect();
  chrome.runtime.sendMessage({ type: 'guardian-reader-ready', host: location.hostname });
  extract();
})();
