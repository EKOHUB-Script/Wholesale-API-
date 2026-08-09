from flask import Flask, render_template, jsonify, request, Response
import os

app = Flask(__name__)

# 스크립트가 저장될 폴더 경로
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'scripts')
os.makedirs(SCRIPTS_DIR, exist_ok=True)

# --- 웹 UI 라우트 ---
@app.route("/")
def index():
    """스크립트 관리 대시보드 UI"""
    return render_template("index.html")

# --- API 라우트 ---
@app.route("/api/scripts", methods=['GET'])
def get_scripts():
    """저장된 모든 스크립트 목록 반환"""
    scripts = []
    for filename in os.listdir(SCRIPTS_DIR):
        if filename.endswith('.lua'):
            name = filename[:-4] # .lua 확장자 제거
            with open(os.path.join(SCRIPTS_DIR, filename), 'r', encoding='utf-8') as f:
                content = f.read()
            scripts.append({
                'name': name,
                'content': content,
                'url': f"https://script.ekohub.xyz/{name}"
            })
    return jsonify(scripts)

@app.route("/api/scripts", methods=['POST'])
def save_script():
    """스크립트 저장 또는 수정"""
    data = request.json
    name = data.get('name', '').strip().lower()
    content = data.get('content', '')
    
    # 파일명 유효성 검사 (영문, 숫자, _, - 만 허용)
    if not name or not all(c.isalnum() or c in ('_', '-') for c in name):
        return jsonify({'error': '스크립트 이름은 영문, 숫자, _, - 만 사용할 수 있습니다.'}), 400
    
    filepath = os.path.join(SCRIPTS_DIR, f"{name}.lua")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return jsonify({'success': True, 'message': f'{name} 스크립트가 저장되었습니다.'})

@app.route("/api/scripts/<name>", methods=['DELETE'])
def delete_script(name):
    """스크립트 삭제"""
    safe_name = "".join(c for c in name if c.isalnum() or c in ('_', '-')).lower()
    filepath = os.path.join(SCRIPTS_DIR, f"{safe_name}.lua")
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'success': True, 'message': f'{safe_name} 스크립트가 삭제되었습니다.'})
    return jsonify({'error': '스크립트를 찾을 수 없습니다.'}), 404

# --- 로블록스 스크립트 호스팅 라우트 ---
@app.route("/<script_name>")
def serve_script(script_name):
    """로블록스에서 loadstring으로 불러올 스크립트 반환"""
    # 보안을 위해 파일명 필터링
    safe_name = "".join(c for c in script_name if c.isalnum() or c in ('_', '-')).lower()
    filepath = os.path.join(SCRIPTS_DIR, f"{safe_name}.lua")
    
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # ★ 핵심: HTML이 아닌 텍스트로 반환해야 로블록스가 인식함
        return Response(content, mimetype='text/plain')
    
    return Response("-- Script not found", status=404, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
