document.addEventListener('DOMContentLoaded', () => {
    const downloadBtn  = document.getElementById('downloadBtn');
    const urlInput     = document.getElementById('urlInput');
    const searchInput  = document.getElementById('searchInput');

    // ── Tab switching ─────────────────────────────────────────────────────────
    window.switchTab = (tab) => {
        document.getElementById('urlTab').style.display    = tab === 'url'    ? 'block' : 'none';
        document.getElementById('searchTab').style.display = tab === 'search' ? 'block' : 'none';
        document.getElementById('tabUrlBtn').classList.toggle('active',    tab === 'url');
        document.getElementById('tabSearchBtn').classList.toggle('active', tab === 'search');
    };

    // ── Download via URL ──────────────────────────────────────────────────────
    downloadBtn.addEventListener('click', () => {
        const url = urlInput.value.trim();
        if (!url) { alert('Please paste a link first!'); return; }
        if (!isValidUrl(url)) { alert('Invalid link! We support YouTube and Spotify.'); return; }
        startDownload(url);
    });

    // Allow Enter key in URL input
    urlInput.addEventListener('keydown', e => { if (e.key === 'Enter') downloadBtn.click(); });

    // Allow Enter key in search input
    searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') window.doSearch(); });

    function isValidUrl(url) {
        return url.includes('youtube.com') || url.includes('youtu.be') || url.includes('spotify.com');
    }

    // ── Spotify Search ────────────────────────────────────────────────────────
    window.doSearch = async () => {
        const q = searchInput.value.trim();
        if (!q) return;
        const btn = document.getElementById('searchBtn');
        const resultsDiv = document.getElementById('searchResults');
        btn.textContent = 'Searching...';
        btn.disabled = true;
        resultsDiv.innerHTML = '<div class="search-loading">🎵 Searching Spotify...</div>';

        try {
            const res = await fetch('/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: q }),
            });
            const data = await res.json();
            if (data.error) { resultsDiv.innerHTML = `<div class="search-error">Error: ${data.error}</div>`; return; }
            renderResults(data);
        } catch (e) {
            resultsDiv.innerHTML = `<div class="search-error">Search failed: ${e.message}</div>`;
        } finally {
            btn.textContent = 'Search';
            btn.disabled = false;
        }
    };

    function renderResults(tracks) {
        const resultsDiv = document.getElementById('searchResults');
        if (!tracks.length) { resultsDiv.innerHTML = '<div class="search-loading">No results found.</div>'; return; }

        resultsDiv.innerHTML = tracks.map(t => `
            <div class="track-card" onclick="selectTrack('${t.url}', '${escHtml(t.name)}', '${escHtml(t.artist)}')">
                <img class="track-art" src="${t.image || 'data:image/svg+xml,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'40\' height=\'40\'><rect width=\'40\' height=\'40\' fill=\'%23333\'/></svg>'}" alt="art">
                <div class="track-info">
                    <div class="track-name">${escHtml(t.name)}</div>
                    <div class="track-artist">${escHtml(t.artist)}</div>
                </div>
                <div class="track-duration">${t.duration}</div>
                <div class="track-dl-icon">↓</div>
            </div>
        `).join('');
    }

    window.selectTrack = (url, name, artist) => {
        urlInput.value = url;
        switchTab('url');
        // Small visual confirmation
        const flash = document.createElement('div');
        flash.textContent = `✅ Selected: ${name} — ${artist}`;
        flash.style.cssText = 'font-size:0.8rem;color:#4ade80;margin-top:0.5rem;animation:fadeIn 0.3s;';
        const urlTab = document.getElementById('urlTab');
        const old = urlTab.querySelector('.selection-flash');
        if (old) old.remove();
        flash.className = 'selection-flash';
        urlTab.insertBefore(flash, urlTab.querySelector('.options'));
        setTimeout(() => flash.remove(), 3000);
    };

    function escHtml(str) {
        return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }

    // ── Core download function ────────────────────────────────────────────────
    async function startDownload(url) {
        const fmt     = document.getElementById('formatSelect').value;
        const quality = document.getElementById('qualitySelect').value;
        const terminalArea = document.getElementById('terminalArea');
        const terminalBody = document.getElementById('terminalBody');

        downloadBtn.disabled    = true;
        downloadBtn.textContent = 'Processing...';
        terminalArea.style.display = 'block';
        terminalBody.innerHTML  = '<div>> Connecting to MultiLoader Engine...</div>';

        try {
            const res = await fetch('/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, format: fmt, quality }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Failed to start task');
            }

            const { task_id } = await res.json();
            const sse = new EventSource(`/progress/${task_id}`);

            // Drip-feed logs every 300ms for readability
            let queue = [];
            const interval = setInterval(() => {
                if (queue.length) {
                    const d = document.createElement('div');
                    d.textContent = queue.shift();
                    terminalBody.appendChild(d);
                    terminalBody.scrollTop = terminalBody.scrollHeight;
                }
            }, 300);

            sse.addEventListener('log', e => queue.push(e.data));

            sse.addEventListener('completed', e => {
                const result = JSON.parse(e.data);
                setTimeout(() => {
                    clearInterval(interval);
                    sse.close();
                    window.location.href = encodeURI(result.download_url);
                    downloadBtn.disabled    = false;
                    downloadBtn.textContent = 'Start New Download';
                    const done = document.createElement('div');
                    done.style.cssText = 'color:#fff;font-weight:bold;';
                    done.textContent = `> COMPLETED: ${result.filename}`;
                    terminalBody.appendChild(done);
                    terminalBody.scrollTop = terminalBody.scrollHeight;
                }, 1500);
            });

            sse.addEventListener('error', e => {
                if (sse.readyState !== EventSource.CLOSED) console.error('SSE error:', e);
                clearInterval(interval);
                sse.close();
                downloadBtn.disabled    = false;
                downloadBtn.textContent = 'Start New Download';
            });

        } catch (err) {
            console.error(err);
            alert('Error: ' + err.message);
            downloadBtn.disabled    = false;
            downloadBtn.textContent = 'Start New Download';
        }
    }
});
