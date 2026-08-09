// 1. 로그인 처리
async function attemptLogin() {
    const password = document.getElementById('adminPassword').value;
    try {
        const res = await fetch('/login', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest' // CSRF 헤더
            },
            body: JSON.stringify({ password })
        });
        
        if (res.ok) {
            document.getElementById('loginOverlay').classList.remove('active');
            loadScripts(); // 로그인 성공 후 스크립트 로드
        } else {
            alert('비밀번호가 틀렸습니다.');
        }
    } catch (error) {
        console.error('Login error:', error);
    }
}

// 2. 초기 로드 시 인증 상태 확인 후 스크립트 로드
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch('/api/scripts', {
            credentials: 'same-origin'
        });
        
        if (res.status === 401) {
            // 인증되지 않음 -> 로그인 오버레이 표시
            document.getElementById('loginOverlay').classList.add('active');
        } else if (res.ok) {
            // 이미 로그인됨 -> 대시보드 로드
            document.getElementById('loginOverlay').classList.remove('active');
            loadScripts();
        }
    } catch (error) {
        console.error('Init error:', error);
    }
});

// 3. 스크립트 불러오기 (수정된 버전)
async function loadScripts() {
    try {
        const res = await fetch('/api/scripts', {
            credentials: 'same-origin', // 세션 쿠키 전송
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
        
        const scripts = await res.json();
        // ... 기존 렌더링 로직 ...
    } catch (error) {
        console.error('Error:', error);
    }
}

// 4. 저장 및 삭제 시에도 헤더 추가 필수
// async function saveScript() {
//     const res = await fetch('/api/scripts', {
//         method: 'POST',
//         credentials: 'same-origin',
//         headers: { 
//             'Content-Type': 'application/json',
//             'X-Requested-With': 'XMLHttpRequest' // 필수!
//         },
//         body: JSON.stringify({ name, content })
//     });
//     // ... 에러 핸들링 (401, 403, 429, 500 구분) ...
// }
