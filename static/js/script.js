const API_URL = '/api/scripts';
let scriptsData = [];

// --- 로그인 및 인증 처리 ---
async function attemptLogin() {
    const password = document.getElementById('adminPassword').value;
    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest' // CSRF 방어 헤더
            },
            body: JSON.stringify({ password })
        });
        
        if (res.ok) {
            document.getElementById('loginOverlay').classList.remove('active');
            await loadScripts(); // 로그인 성공 후 대시보드 로드
        } else {
            alert('비밀번호가 틀렸습니다.');
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('로그인 중 네트워크 오류가 발생했습니다.');
    }
}

async function logout() {
    await fetch('/api/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    });
    document.getElementById('loginOverlay').classList.add('active');
    document.getElementById('scriptList').innerHTML = '';
}

// --- 초기 로드 시 인증 상태 확인 ---
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch(API_URL, {
            credentials: 'same-origin' // 세션 쿠키 전송
        });
        
        if (res.status === 401) {
            // 인증되지 않음 -> 로그인 오버레이 표시 (이미 HTML에서 active 상태)
            return;
        } else if (res.ok) {
            // 이미 로그인됨 -> 오버레이 숨기고 대시보드 로드
            document.getElementById('loginOverlay').classList.remove('active');
            await loadScripts();
        }
    } catch (error) {
        console.error('Init check error:', error);
    }
});

// --- 스크립트 CRUD (수정된 fetch) ---
async function loadScripts() {
    try {
        const res = await fetch(API_URL, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        
        if (res.status === 401) {
            document.getElementById('loginOverlay').classList.add('active');
            return;
        }
        if (res.status === 429) {
            alert('너무 많은 요청을 보냈습니다. 잠시 후 다시 시도해주세요.');
            return;
        }
        
        scriptsData = await res.json();
        renderScripts(scriptsData);
    } catch (error) {
        console.error('Error:', error);
    }
}

async function saveScript() {
    const name = document.getElementById('scriptName').value.trim().toLowerCase();
    const content = document.getElementById('scriptContent').value;
    
    if (!name || !content) {
        alert('Please fill in all fields.');
        return;
    }

    try {
        const res = await fetch(API_URL, {
            method: 'POST',
            credentials: 'same-origin', // 세션 쿠키 전송
            headers: { 
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest' // CSRF 헤더
            },
            body: JSON.stringify({ name, content })
        });
        
        if (res.ok) {
            closeModal();
            await loadScripts();
            alert('Script saved successfully.');
        } else {
            const data = await res.json();
            alert(data.error || 'Failed to save script.');
        }
    } catch (error) {
        alert('Network error occurred.');
    }
}

async function confirmDelete() {
    if (!currentDeleteTarget) return;
    
    try {
        const res = await fetch(`${API_URL}/${currentDeleteTarget}`, { 
            method: 'DELETE',
            credentials: 'same-origin', // 세션 쿠키 전송
            headers: { 'X-Requested-With': 'XMLHttpRequest' } // CSRF 헤더
        });
        
        if (res.ok) {
            closeDeleteModal();
            await loadScripts();
            alert('Script deleted.');
        } else {
            alert('Failed to delete script.');
        }
    } catch (error) {
        alert('Network error occurred.');
    }
}

// (참고) renderScripts, openModal 등 기존 함수들은 그대로 유지됩니다.
