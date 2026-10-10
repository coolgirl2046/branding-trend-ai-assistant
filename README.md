# 브랜딩 트렌드 AI 비서

Firestore에 저장된 네이버 데이터랩 상대 검색 관심도 데이터를 요약하고, 해당 데이터에 근거한 AI 채팅과 대화 기록을 제공합니다.

## 로컬 실행

1. 프로젝트 루트의 `.env.example`을 참고해 `.env`를 만들고 Firebase 및 사용하려는 AI 제공자 설정을 입력합니다. 비밀값은 저장소에 커밋하지 마세요.
2. 프로젝트 루트에서 백엔드를 실행합니다.

   ```powershell
   python -m pip install -r backend/requirements.txt
   python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```

3. 별도 터미널에서 프론트엔드를 실행합니다.

   ```powershell
   python -m http.server 5500 --directory frontend
   ```

4. `http://localhost:5500`을 엽니다. 로컬 프론트엔드는 `http://127.0.0.1:8000` 백엔드에 연결됩니다.

`.env`는 로컬 비밀 설정 파일이며 Git에서 제외됩니다. `.env.example`은 비밀값 없이 변수 이름과 안전한 예시만 담는 공유 템플릿이라 Git에 포함할 수 있습니다. Firebase 서비스 계정 JSON 파일은 파일명에 `service_account`, `service-account` 또는 `serviceAccount`가 들어가면 Git에서 제외됩니다. 서비스 계정 JSON은 가능하면 파일 대신 배포 플랫폼의 비밀 환경변수에 등록하세요.

## Render 백엔드

저장소 루트의 `render.yaml`은 Render Blueprint 설정입니다. 빌드 명령은 `pip install -r backend/requirements.txt`, 시작 명령은 `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`입니다. 헬스 체크 경로는 `/health`입니다.

Render 서비스의 Root Directory는 `render.yaml`과 백엔드 패키지 경로가 저장소 루트를 기준으로 하므로 저장소 루트(`/`)로 설정하세요.

Render 서비스의 환경변수:

| 변수 | 용도 |
| --- | --- |
| `FIREBASE_PROJECT_ID` | Firebase 프로젝트 ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firebase Admin 서비스 계정 JSON 전체를 담는 비밀 환경변수 |
| `CORS_ORIGINS` | 쉼표로 구분한 허용 프론트엔드 출처 목록. 예: `https://<실제-vercel-도메인>` |
| `AI_PROVIDER` | `openai` 또는 `gemini` |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | `AI_PROVIDER=openai`일 때 필요한 제공자 설정 |
| `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_MODEL` | `AI_PROVIDER=gemini`일 때 필요한 제공자 설정 |

Firebase JSON은 Render 대시보드의 비밀 환경변수에 직접 입력하세요. JSON 파일을 저장소에 추가하거나 로그에 출력하지 마세요. `FIREBASE_SERVICE_ACCOUNT_PATH`는 Render에 JSON 파일을 따로 배포하지 않는 구성에서는 사용하지 않습니다. 기존 설정 코드에서는 JSON 환경변수가 파일 경로보다 우선합니다.

`CORS_ORIGINS`가 비어 있으면 로컬 개발 출처만 허용합니다. 배포할 때는 Vercel이 발급한 실제 도메인을 입력하세요. 로컬 주소와 함께 허용하려면 쉼표로 구분합니다.

## Vercel 프론트엔드

Vercel 프로젝트의 Root Directory를 `frontend`로 설정합니다. 이 폴더의 `vercel.json`은 정적 파일의 깔끔한 URL 사용을 설정하며 별도 빌드 단계는 필요하지 않습니다.

Render가 실제 서비스 주소를 발급한 뒤 `frontend/js/config.js`의 `deployedApiBaseUrl`에 해당 백엔드 URL을 입력해 프론트엔드 변경사항을 배포하세요. 이 주소는 아직 설정되어 있지 않습니다. 로컬 주소 자동 설정은 그대로 유지됩니다.

## 테스트

기존 자동 테스트는 다음 명령으로 실행합니다.

```powershell
python -m unittest discover -s backend/tests -v
```
