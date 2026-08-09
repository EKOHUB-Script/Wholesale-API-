const API_URL = '/api/scripts';
let scriptsData = [];
let currentUser = null;

// --- 초기 로드 ---
document.addEventListener('DOMContentLoaded', async () => {
    await checkAuthStatus();
    await loadScripts();
});

// --- 인증 상태 확인 및 헤더 UI 업데이트 ---
async function checkAuthStatus() {
    const authArea = document.getElementById('authArea');
    try {
        const res = await fetch('/api/auth/me', { credentials: 'same-origin' });
        if (res.ok) {
            const data = await res.json();
            currentUser = data;
            
            // 로그인 된 상태: 프로필 표시
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
            
            // 스크립트 업로드 버튼 표시 (관리자/일반유저 모두)
            const newScriptBtn = document.getElementById('newScriptBtn');
            if (newScriptBtn) newScriptBtn.style.display = 'flex';
            
        } else {
            // 로그아웃 상태: 디스코드 로그인 + 관리자 로그인 버튼 표시
            currentUser = null;
            authArea.innerHTML = `
                <button class="glass-btn" onclick="document.getElementById('adminLoginOverlay').classList.add('active')">Admin Login</button>
                <a href="/api/auth/discord" class="glass-btn glass-btn-primary" style="text-decoration: none; display: flex;">
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M20.317 4.37a19.79 19.79 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 00-.041-.106 13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.892.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"></path></svg>
                    Discord Login
                </a>
            `;
            
            // 스크립트 업로드 버튼 숨김 (미인증 유저)
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

async function attemptAdminLogin() {
    const password = document.getElementById('adminPassword').value;
    const res = await fetch('/api/auth/admin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ password })
    });
    if (res.ok) {
        document.getElementById('adminLoginOverlay').classList.remove('active');
        await checkAuthStatus();
        await loadScripts();
    } else {
        alert('관리자 비밀번호가 틀렸습니다.');
    }
}

// --- 스크립트 렌더링 (작성자 정보 추가) ---
function renderScripts(scripts) {
    const list = document.getElementById('scriptList');
    
    if (scripts.length === 0) {
        list.innerHTML = `<div class="glass" style="padding: 3rem; text-align: center; grid-column: 1 / -1; color: var(--text-muted);">No scripts found.</div>`;
        return;
    }

    list.innerHTML = scripts.map(script => {
        const codeString = `loadstring(game:HttpGet("${script.url}"))()`;
        const previewContent = script.content.length > 120 ? script.content.substring(0, 120) + '...' : script.content;
        
        // 작성자 프로필 HTML 생성
        const ownerAvatar = script.owner_avatar 
            ? `<img src="${script.owner_avatar}" style="width: 20px; height: 20px; border-radius: 50%;" alt="Owner">`
            : `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>`;
        
        const ownerName = script.owner_name || 'Unknown';

        const actionButtons = `
            ${script.can_edit ? `<button class="action-btn" onclick="editScript('${script.name}')">${icons.edit} Edit</button>` : ''}
            ${script.can_delete ? `<button class="action-btn delete" onclick="openDeleteModal('${script.name}')">${icons.trash} Delete</button>` : ''}
        `;

        return `
        <div class="glass script-card">
            <div class="script-header">
                <div class="script-name">${escapeHtml(script.name)}</div>
            </div>
            <div class="script-code-preview">${escapeHtml(previewContent)}</div>
            <div class="script-url-box">${escapeHtml(codeString)}</div>
            
            <!-- 🆕 작성자 정보 박제 -->
            <div style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid var(--glass-border);">
                ${ownerAvatar}
                <span>${escapeHtml(ownerName)}</span>
            </div>

            <div class="script-actions">
                <button class="action-btn" onclick="copyUrl('${script.url}', this)">${icons.copy} Copy</button>
                ${actionButtons}
            </div>
        </div>
        `;
    }).join('');
}

// loadScripts, saveScript, confirmDelete 함수는 기존과 동일
