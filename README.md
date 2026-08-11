# Shortly

개인용 Flask URL 단축 서비스입니다. 단일 관리자 로그인, URL 생성·목록·삭제, 리디렉션 조회수 집계를 지원합니다. HTTP(S)뿐 아니라 `obsidian://`, `mailto:`, `tel:` 등 커스텀 프로토콜도 사용할 수 있습니다. 보안을 위해 `javascript:`, `data:`, `vbscript:` 스킴은 허용하지 않습니다.

## 실행

Python 3.10 이상에서 다음 명령을 실행합니다.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:URL_SHORTENER_USERNAME="admin"
$env:URL_SHORTENER_PASSWORD="원하는-비밀번호"
$env:URL_SHORTENER_SECRET_KEY="길고-무작위인-문자열"
flask --app app run
```

브라우저에서 `http://127.0.0.1:5000`을 엽니다. 데이터는 자동으로 생성되는 `instance/urls.sqlite3`에 저장됩니다.

## Docker로 실행

먼저 환경변수 파일을 준비하고 관리자 비밀번호와 비밀키를 안전한 값으로 변경합니다.

```bash
cp .env.example .env
```

그다음 이미지를 빌드하고 컨테이너를 실행합니다.

```bash
docker compose up --build -d
```

브라우저에서 `http://127.0.0.1:5000`을 엽니다. SQLite 데이터와 자동 생성 비밀키는 `shortly-data` Docker 볼륨에 보존됩니다.
포트 5000이 이미 사용 중이면 `.env`의 `URL_SHORTENER_PORT`를 다른 포트로 변경하세요.

로그 확인과 종료에는 다음 명령을 사용합니다.

```bash
docker compose logs -f shortly
docker compose down
```

`docker compose down`은 데이터 볼륨을 삭제하지 않습니다. 데이터까지 삭제하려는 경우에만 `docker compose down --volumes`를 사용하세요.

운영 환경에서는 환경변수를 반드시 설정하고, 개발 서버 대신 다음처럼 실행하세요.

```powershell
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

> Gunicorn은 Linux/macOS용입니다. Windows에서는 Waitress 등의 WSGI 서버를 사용할 수 있습니다.

## 비밀번호 해시 사용 (선택)

평문 비밀번호 환경변수 대신 Werkzeug 형식의 해시를 `URL_SHORTENER_PASSWORD_HASH`에 지정할 수 있습니다. 이 값이 있으면 `URL_SHORTENER_PASSWORD`보다 우선합니다.

## 테스트

```powershell
pip install pytest
pytest
```
