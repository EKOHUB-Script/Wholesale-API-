const API_URL = '/api/scripts';
let scriptsData = [];
let currentUser = null;

// --- 초기 로드 ---
document.addEventListener('DOMContentLoaded', async () => {
    await checkAuthStatus();
    await loadScripts(); // 누구나 스크립트 목록 조회 가능
});

// --- 인증 상태 확인 및 UI 업데이트 ---
async function checkAuthStatus() {
    try {
        const res = await fetch('/api/auth/me', { credentials: 'same-origin' });
        if (res.ok) {
            const data = await res.json();
            currentUser = data;
            
            // 로그인 된 상태
            document.getElementById('discordLoginBtn').style.display = 'none';
            document.getElementById('adminAuthBtn').style.display = 'none';
            document.getElementById('logoutBtn').style.display = 'flex';
            document.getElementById('newScriptBtn').style.display = 'flex'; // 글래스모피즘 UI의 New Script 버튼
        } else {
            // 로그아웃 상태
            currentUser = null;
            document.getElementById('discordLoginBtn').style.display = 'flex';
            document.getElementById('adminAuthBtn').style.display = 'flex';
            document.getElementById('logoutBtn').style.display = 'none';
            document.getElementById('newScriptBtn').style.display = 'none';
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

// --- 스크립트 렌더링 (서버 권한 값 기반) ---
function renderScripts(scripts) {
    const list = document.getElementById('scriptList');
    
    if (scripts.length === 0) {
        list.innerHTML = `<div class="glass" style="padding: 3rem; text-align: center; grid-column: 1 / -1; color: var(--text-muted);">No scripts found.</div>`;
        return;
    }

    list.innerHTML = scripts.map(script => {
        const codeString = `loadstring(game:HttpGet("${script.url}"))()`;
        const previewContent = script.content.length > 120 ? script.content.substring(0, 120) + '...' : script.content;
        
        // 서버에서 받은 can_edit, can_delete 값에 따라 버튼 렌더링
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
            <div class="script-actions">
                <button class="action-btn" onclick="copyUrl('${script.url}', this)">${icons.copy} Copy</button>
                ${actionButtons}
            </div>
        </div>
        `;
    }).join('');
}

// loadScripts, saveScript, confirmDelete 함수는 기존과 동일하되 
// fetch 호출 시 credentials: 'same-origin' 과 'X-Requested-With' 헤더 유지
