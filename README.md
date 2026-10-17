# 브랜딩 트렌드 AI 비서

네이버 데이터랩의 주간 상대 검색 관심도 데이터를 Firestore에 저장하고, 통계·그래프와 AI 채팅으로 확인하는 웹 애플리케이션입니다. AI는 데이터 요약을 문맥으로 활용하며, 필요하면 Function Calling으로 허용된 기간의 데이터를 조회합니다.

## 배포 및 현재 검증 상태

| 구성 요소 | 주소 | 확인 결과 |
| --- | --- | --- |
| 백엔드 (Render) | <https://branding-trend-ai-assistant.onrender.com> | 접속 및 Swagger 확인. 최신 Live 커밋 `86a71b6` |
| 프론트엔드 (Vercel) | <https://branding-trend-ai-assistant-fronten.vercel.app> | HTTP 접속 및 Render API 설정 확인 |

운영 시계열 데이터 558건을 확인했습니다. AI 채팅·대화 저장·새로고침 후 불러오기, Function Calling, 외부 MCP 클라이언트(Claude Code)를 통한 Firestore 조회, 그래프·JSON 다운로드·다크 모드의 실환경 동작을 확인했습니다. 운영 UI에서 `2026-10-12` 퍼스널브랜딩 테스트 데이터 1건을 관심도 25로 생성·조회하고, 30으로 수정한 뒤 삭제했습니다. 원본 558건을 유지했고 삭제 후 총 558건을 확인했습니다.

## 공식 미션 요구사항 대응

상태는 제출자가 제공한 공식 요구사항과 구현 및 확인 결과를 대조한 것입니다.

| 요구사항 | 상태 | 근거·범위 |
| --- | --- | --- |
| FastAPI | 충족 | 백엔드 구현 및 테스트 |
| Firestore | 충족 | Firestore 연동, 운영 데이터 558건 확인 |
| GPT API | 충족 | 실환경 AI 채팅 응답 |
| 시계열 데이터 100개 이상 | 충족 | 운영 데이터 558건 확인 |
| 데이터 CRUD 및 요약 | 충족 | 운영 UI에서 테스트 레코드 1건 CRUD 수행, 원본 558건 유지 및 삭제 후 총 558건 확인 |
| AI 채팅 및 데이터 문맥 주입 | 충족 | 코드·테스트와 실환경 채팅 확인 |
| 대화 저장·조회·삭제·불러오기 | 충족 | API 테스트와 합성 테스트 대화의 실환경 저장·불러오기·삭제 확인 |
| HTML/CSS/JS 프론트엔드 | 충족 | Vercel 화면과 주요 기능 확인 |
| Render/Vercel 배포 | 충족 | 두 서비스 접속 확인, Render Live 커밋 `86a71b6` |
| Swagger | 충족 | Render `/docs` 접속 확인 |
| README 및 기능별 증빙 | 충족 | 보고서와 README에 존재 확인된 정상 화면 스크린샷 10장 연결 |
| 보너스 1: Function Calling, MCP 또는 GPT Actions 및 흐름 문서화 | 충족 | Function Calling 실환경 성공 및 흐름 설명. Claude Code 외부 MCP 클라이언트 연결·도구 호출과 Firestore 데이터 13건 반환 확인 |
| 보너스 2: 추가 통계, 그래프, CSV 또는 JSON, 다크 모드 | 충족 | 그래프·JSON 다운로드·다크 모드 실환경 확인 및 증빙 확보 |

## 주요 기능과 통계 기준

- 키워드별 통계 및 주간 상대 검색 관심도 그래프
- Firestore 데이터 조회·추가·수정·삭제 UI와 API
- AI 채팅 및 대화 기록 저장·조회·관리
- Function Calling을 통한 주간 데이터 조회
- 그래프 기간, 주간/4주 이동평균, 키워드 표시 제어
- JSON 다운로드 및 다크 모드

백엔드 요약은 키워드별 **최신 관측값 4개의 평균**을 계산합니다. 주간 데이터가 연속일 때 최근 4주 평균에 해당합니다. 프론트엔드의 4주 이동평균은 별도 계산이며, 연속된 주간 관측값 4개가 있는 구간에 표시됩니다. 상대 검색 관심도는 실제 검색량이 아니라 같은 조건에서 키워드 간 관심도 변화를 비교하는 지표입니다.

## Function Calling 및 MCP

실환경 Function Calling에서 도구 호출과 조회 결과를 확인했습니다.

```text
function_calling_response tool_call_count=1 tool_names=get_weekly_interest_data
trend_tool_success tool_name=get_weekly_interest_data returned_count=5
```

MCP 서버는 같은 읽기 전용 조회 기능을 제공합니다. 가짜 Firestore 기반 테스트와 공식 SDK의 stdio(표준 입력·출력) 연결 테스트에 더해, Claude Code 외부 MCP 클라이언트에서 서버 `Connected` 상태와 `query_weekly_interest` 도구를 확인했습니다. 실환경에서 `퍼스널브랜딩` 키워드의 2026-01-01~2026-03-31 기간을 읽기 전용으로 한 번 조회해 Firestore 레코드 13건을 반환받았습니다. 오류는 없었습니다.

## 자동화 테스트 및 브라우저 검증

| 대상 | 테스트 수 | 결과 |
| --- | ---: | --- |
| 백엔드 | 83 | 모두 통과 |
| 프론트엔드 | 20 | 모두 통과 |
| 합계 | 103 | 모두 통과 |

백엔드는 `python -m unittest discover -s backend/tests -v`, 프론트엔드는 `node --test frontend/tests/*.test.mjs`로 실행했습니다. 프론트엔드 테스트에는 가짜 응답으로 대화 목록·선택·상세 조회·메시지 복원을 검사하는 테스트 7개가 포함됩니다. 자동화 테스트는 주로 가짜 Firestore와 모의 응답을 사용하므로 실환경 브라우저 검증과 구분합니다. 실환경 CRUD는 기존 558건과 별도로 테스트 레코드 1건만 대상으로 확인했습니다.

## 제출용 증빙

제출용 정상 화면 스크린샷 (모두 `evidence/`에 존재 확인):

- [실제 데이터가 표시된 대시보드](evidence/readonly_01_dashboard.png)
- [다크 모드 대시보드](evidence/readonly_05_dark_mode.png)
- [Render Swagger](evidence/readonly_06_render_swagger.png)
- [저장된 AI 채팅](evidence/submission_chat_saved.png)
- [3개월 그래프](evidence/submission_graph_3m.png)
- [JSON 다운로드](evidence/submission_json_download.png)
- [테스트 레코드 조회](evidence/submission_crud_read.png)
- [테스트 레코드 생성](evidence/submission_crud_create.png)
- [테스트 레코드 수정](evidence/submission_crud_update.png)
- [테스트 레코드 삭제](evidence/submission_crud_delete.png)

## 로컬 실행

프로젝트 루트에서 백엔드 의존성을 설치하고 실행합니다.

```powershell
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

별도 터미널에서 프론트엔드를 실행합니다.

```powershell
python -m http.server 5500 --directory frontend
```

브라우저에서 `http://localhost:5500`을 엽니다. 로컬 프론트엔드는 `http://127.0.0.1:8000` 백엔드에 연결합니다. Firebase 및 AI 자격증명은 비밀 환경 변수로 관리하고 저장소나 로그에 기록하지 마세요.
