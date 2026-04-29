document.addEventListener('DOMContentLoaded', () => {
    const downloadBtn = document.getElementById('downloadBtn');
    const urlInput    = document.getElementById('urlInput');

    downloadBtn.addEventListener('click', () => {
        const url = urlInput.value.trim();
        if (!url) { alert('Please paste a link first!'); return; }
        if (!isValidUrl(url)) { alert('Invalid link! We support YouTube and Spotify.'); return; }
        startDownload(url);
    });

    urlInput.addEventListener('keydown', e => { if (e.key === 'Enter') downloadBtn.click(); });

    function isValidUrl(url) {
        return url.includes('youtube.com') || url.includes('youtu.be') || url.includes('spotify.com');
    }

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

            let queue = [];
            const interval = setInterval(() => {
                if (queue.length) {
                    const count = Math.min(queue.length, 5);
                    for (let i = 0; i < count; i++) {
                        const d = document.createElement('div');
                        d.textContent = queue.shift();
                        terminalBody.appendChild(d);
                    }
                    terminalBody.scrollTop = terminalBody.scrollHeight;
                }
            }, 100);

            sse.addEventListener('log', e => queue.push(e.data));

            sse.addEventListener('completed', e => {
                const result = JSON.parse(e.data);
                setTimeout(() => {
                    clearInterval(interval);
                    sse.close();
                    
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = encodeURI(result.download_url);
                    a.download = result.filename;
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(() => document.body.removeChild(a), 100);
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
