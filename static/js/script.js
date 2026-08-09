const API_URL = '/api/scripts';
let scriptsData = [];
let currentUser = null;

document.addEventListener('DOMContentLoaded', async () => {
    // URL 파라미터로 전달된 에러 확인
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('error')) {
        alert('인증에 실패했습니다. 다시 시도해주세요.');
        history.replaceState({}, document.title, window.location.pathname);
    }
    
    await checkAuthStatus();
    await loadScripts();
});

async function checkAuthStatus() {
    const authArea = document.getElementById('authArea');
    try {
        const res = await fetch('/api/auth/me', { credentials: 'same-origin' });
        if (res.ok) {
            const data = await res.json();
            currentUser = data;
            
            if (data.role === 'admin') {
                authArea.innerHTML = `
                    <button class="glass-btn" onclick="logout()">Logout</button>
                    <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0.8rem; background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); border-radius: 8px;">
                        <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                        <span style="font-size: 0.85rem;">Admin</span>
                    </div>
                `;
            } else {
                authArea.innerHTML = `
                    <button class="glass-btn" onclick="logout()">Logout</button>
                    <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0.8rem; background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); border-radius: 8px;">
                        <img src="${data.avatar_url || 'https://via.placeholder.com/24'}" style="width: 24px; height: 24px; border-radius: 50%;" alt="Avatar">
                        <span style="font-size: 0.85rem;">${data.username || 'User'}</span>
                    </div>
                `;
            }
            
            const newScriptBtn = document.getElementById('newScriptBtn');
            if (newScriptBtn) newScriptBtn.style.display = 'flex';
            
        } else {
            currentUser = null;
            authArea.innerHTML = `
                <button class="glass-btn" onclick="document.getElementById('adminLoginOverlay').classList.add('active')">Admin Login</button>
                <!-- 인증하기 버튼: /api/auth/discord 로 이동하여 디스코드 연동 진행 -->
                <a href="/api/auth/discord" class="glass-btn glass-btn-primary" style="text-decoration: none; display: flex;">
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"></path></svg>
                    인증하기
                </a>
            `;
            
            const newScriptBtn = document.getElementById('newScriptBtn');
            if (newScriptBtn) newScriptBtn.style.display = 'none';
        }
    } catch (e) {
        console.error('Auth check error:', e);
    }
}

async function logout() {
    await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    });
    await checkAuthStatus();
    await loadScripts();
}

// ... 기존의 loadScripts, renderScripts, saveScript 등은 그대로 유지 ...
