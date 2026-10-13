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

## Function Calling과 MCP 도구

채팅 서비스는 `get_weekly_interest_data` Function Calling 도구를 제공합니다. 입력은 `keyword`, `start_date`, `end_date` 세 필수 값으로 제한합니다. 키워드는 `퍼스널브랜딩`, `이미지메이킹`, `스피치`만 허용하고 날짜는 ISO 형식 및 최대 5년 범위인지 서버에서 다시 검증합니다. JSON Schema의 열거형과 필수 필드로 모델의 입력을 안내하고, 서버의 검증을 최종 경계로 둡니다. 도구는 읽기 전용이며 상대 검색 관심도 지수와 주간 값만 돌려줍니다.

`/api/chat`은 기존 대화와 통계를 포함해 모델에 요청합니다. 모델이 도구 호출을 반환하면 서버가 이름과 인자를 검증하고 Firestore에서 해당 키워드·날짜 범위만 읽습니다. 결과를 도구 응답 메시지로 모델에 전달해 최종 답변을 생성한 후, 기존과 동일하게 사용자 질문과 최종 답변만 대화 기록에 저장합니다. 한 번의 답변에서 도구 호출은 최대 3회입니다. 입력 오류나 조회 오류는 안전한 도구 오류 결과로 전달하고 비밀값이나 원본 예외를 로그에 남기지 않습니다. 프론트엔드의 `/api/chat` 요청·응답 형식은 바뀌지 않습니다.

### 로컬 stdio MCP 서버

MCP 서버는 공식 MCP Python SDK를 사용하며 Function Calling과 같은 `get_weekly_interest_data` 조회 함수를 재사용합니다. 별도 HTTP 포트나 유료 외부 서비스 없이 MCP 호스트가 로컬 프로세스를 stdio로 실행합니다. 프로젝트 루트에서 실행합니다.

```powershell
python -m pip install -r backend/requirements.txt
python -m backend.app.mcp_server
```

stdio 서버는 프로토콜 응답 외의 문장을 표준 출력에 쓰지 않으므로, 위 실행 명령은 MCP 클라이언트가 관리해야 합니다. 독립 실행 확인은 MCP Inspector에서 프로젝트 Python 환경으로 `backend.app.mcp_server` 모듈을 stdio transport로 실행하고 `query_weekly_interest` 도구를 호출하면 됩니다. 실제 Firestore 조회에는 기존 `FIREBASE_PROJECT_ID`와 `FIREBASE_SERVICE_ACCOUNT_JSON` 또는 `FIREBASE_SERVICE_ACCOUNT_PATH` 설정이 필요합니다. 로컬에서는 프로젝트 루트의 무시 처리된 `.env`를 사용할 수 있습니다.

Claude Desktop의 `claude_desktop_config.json` 예시(경로를 로컬 저장소 위치에 맞게 바꾸세요):

```json
{
  "mcpServers": {
    "branding-trend": {
      "command": "C:\\path\\to\\branding-trend-ai-assistant\\backend\\.venv\\Scripts\\python.exe",
      "args": ["-m", "backend.app.mcp_server"],
      "env": {
        "PYTHONPATH": "C:\\path\\to\\branding-trend-ai-assistant"
      }
    }
  }
}
```

MCP 호스트가 서버 프로세스에 Firebase 환경변수를 전달하도록 호스트의 안전한 환경변수 설정을 사용하세요. MCP 설정 파일에 실제 키나 서비스 계정 JSON을 직접 넣으면 파일에 평문으로 남을 수 있습니다. 자격증명을 저장소, 채팅 메시지, 도구 인자, 로그에 복사하지 마세요. MCP 도구는 데이터 조회만 제공하며 Firebase 인증 설정은 FastAPI와 같은 기존 `backend.app.database.get_firestore_client()` 경로를 사용합니다.

### 검증 범위

Function Calling은 유료 AI 호출 없이 모의 OpenAI 응답으로 도구 스키마 전달, 호출 실행, 오류 처리, 호출 제한을 테스트합니다. MCP는 서버의 도구 목록과 호출을 가짜 Firestore로 검사하고, 공식 SDK 클라이언트가 별도 stdio 프로세스에 연결해 도구 목록과 입력 오류를 확인합니다. 백엔드 전체 테스트는 `python -m unittest discover -s backend/tests -v`로 실행합니다. Claude Desktop 등 실제 MCP 호스트 UI와 실 Firestore·AI 제공자 호출은 사용자별 자격증명 및 클라이언트 환경이 필요하므로 검증에 포함하지 않습니다. 배포된 AI 제공자와 모델이 Chat Completions Function Calling을 지원하는지도 실제 키를 이용해 확인해야 합니다.
