# 브랜딩 트렌드 AI 비서 — 미션 2 최종 결과 보고서

작성 기준일: 2026-10-17
프로젝트: `branding-trend-ai-assistant`

## 요약

미션 1의 브랜딩 키워드 시계열 분석 결과를 웹 대시보드와 AI 채팅에서 활용하도록 애플리케이션을 구현했습니다. 운영 데이터 558건을 확인했고, AI 채팅·대화 저장·새로고침 후 불러오기, Function Calling, Claude Code 외부 MCP 클라이언트를 통한 Firestore 조회, 그래프·JSON 다운로드·다크 모드, Render·Vercel·Swagger 접속을 실환경에서 확인했습니다.

자동화 테스트는 백엔드 83개와 프론트엔드 20개, 총 103개가 통과했습니다. Claude Code 외부 MCP 클라이언트에서 서버 연결과 도구 호출을 확인했고, 요청한 읽기 전용 조회에서 Firestore 데이터 13건을 반환받았습니다. 채팅·그래프·JSON 화면 증빙과 운영 CRUD 화면 증빙도 확보했습니다.

## 1. 개발 목적과 미션 1과의 연계

미션 1의 브랜딩 키워드 시계열 분석 결과를 쉽게 확인하고 AI와 함께 해석할 수 있도록 미션 2 웹 애플리케이션을 만들었습니다. 데이터 변환 스크립트는 네이버 데이터랩의 주간 상대 검색 관심도 자료를 날짜·키워드·값 레코드로 정리해 Firestore에 적재하도록 구성돼 있습니다.

변환 스크립트와 테스트가 뒷받침하는 규모는 186주 × 3개 키워드, 총 558개 레코드입니다. 미션 1 원본 Excel은 저장소에 없어 원본 파일을 다시 읽어 확인한 값은 아닙니다. 별도로 운영 화면에서 실제 데이터 558건을 확인했습니다.

상대 검색 관심도는 실제 검색량이 아니라 같은 조건에서 키워드 간 관심도 변화를 비교하는 지표입니다. 대시보드와 AI 응답 맥락에서 이 점을 안내합니다.

## 2. 시스템 구성 및 주요 기능

| 구성 요소 | 구현 | 역할 |
| --- | --- | --- |
| 프론트엔드 | HTML, CSS, JavaScript ES modules(기능별 JavaScript 파일) | 통계·그래프, 데이터 관리, 대화 화면 |
| 백엔드 | FastAPI(Python 웹 API 프레임워크), Pydantic(요청 자료 검증 도구) | 데이터·대화·채팅 API와 입력 검증 |
| 데이터베이스 | Firebase Firestore(클라우드 데이터베이스) | 주간 데이터와 대화 기록 저장 |
| AI | GPT API와 Function Calling(AI가 정해진 도구를 호출하는 기능) | 통계 문맥 기반 대화 및 제한된 데이터 조회 |
| MCP 서버 | MCP(Model Context Protocol, AI 도구 연결 규격) Python SDK | 같은 읽기 전용 조회 기능 제공 |
| 배포 | Render 백엔드, Vercel 프론트엔드 | API와 정적 웹 서비스 |

주요 기능은 키워드별 요약·순위, 주간 그래프, 데이터 관리, AI 대화 기록, Function Calling, 그래프 기간·이동평균·키워드 표시, JSON 다운로드, 다크 모드입니다.

백엔드 요약은 **최신 관측값 4개의 평균**입니다. 데이터가 연속된 주간 관측값일 때 최근 4주 평균에 해당합니다. 프론트엔드 그래프의 4주 이동평균은 별도 계산이며 연속된 주간 관측값 4개가 있는 구간에 표시됩니다.

## 3. 공식 미션 요구사항 대응표

다음은 제출자가 제공한 공식 요구사항에 구현과 확인 결과를 대조한 표입니다.

| 요구사항 | 판정 | 근거 및 남은 범위 |
| --- | --- | --- |
| FastAPI | 충족 | 백엔드 구현, 테스트 83개 통과 |
| Firestore | 충족 | 연동 구현, 운영 데이터 558건 확인 |
| GPT API | 충족 | 실환경 AI 채팅 응답 성공 |
| 시계열 데이터 100개 이상 | 충족 | 운영 화면에서 558건 확인 |
| 데이터 CRUD 및 요약 | 충족 | 운영 UI에서 테스트 레코드 1건 생성·조회·수정·삭제 확인. 원본 558건은 유지하고 삭제 후 총 558건 확인 |
| AI 채팅 및 데이터 문맥 주입 | 충족 | 코드·테스트와 실환경 채팅 확인 |
| 대화 저장·조회·삭제·불러오기 | 충족 | API 테스트 및 합성 테스트 대화의 실환경 저장·불러오기·삭제 확인 |
| HTML/CSS/JS 프론트엔드 | 충족 | Vercel 화면 및 주요 기능 확인 |
| Render/Vercel 배포 | 충족 | 두 주소 접속 확인, Render Live 커밋 `86a71b6` |
| Swagger | 충족 | Render `/docs` 접속 확인 |
| README 및 기능별 증빙 | 충족 | README와 보고서에 정상 스크린샷 10장 연결. 채팅·그래프·JSON·CRUD 화면 증빙 포함 |
| 보너스 1: Function Calling, MCP 또는 GPT Actions 및 흐름 문서화 | 충족 | Function Calling 실환경 성공 및 흐름 설명. Claude Code MCP 연결·도구 호출 성공, Firestore 조회 13건 반환 |
| 보너스 2: 추가 통계, 그래프, CSV 또는 JSON, 다크 모드 | 충족 | 그래프·JSON 다운로드·다크 모드 실환경 확인 및 정상 화면 증빙 확보 |

주간 시계열 데이터 전체를 대상으로 한 변경 검증이 아니라, 기존 레코드를 건드리지 않고 별도 테스트 레코드 1건의 CRUD를 확인했습니다.

## 4. 실환경 기능 검증

| 항목 | 결과 | 확인 내용 |
| --- | --- | --- |
| 운영 시계열 데이터 | 성공 | 558건 표시 확인 |
| AI 채팅·대화 저장 | 성공 | 테스트 대화의 채팅 HTTP 200, 사용자·AI 메시지 2건 저장 |
| 새로고침 후 불러오기 | 성공 | 목록 재조회, 같은 대화 선택, 상세 조회 HTTP 200, 메시지 2건 표시 |
| 테스트 대화 삭제 | 성공 | 응답에서 확보한 테스트 대화 ID의 대화만 삭제 |
| Function Calling | 성공 | 도구 1회 호출, 주간 데이터 5건 반환 |
| 외부 MCP 클라이언트 | 성공 | Claude Code 서버 `Connected`, `query_weekly_interest` 호출 성공. `퍼스널브랜딩`, 2026-01-01~2026-03-31 읽기 전용 조회 1회, Firestore 13건 반환, 오류 없음 |
| 운영 시계열 데이터 CRUD | 성공 | 테스트 레코드 `2026-10-12`, `퍼스널브랜딩`, 관심도 25 생성 후 목록 확인. 새로고침 후 재조회, 25에서 30으로 수정 확인, 해당 레코드 삭제 후 목록에서 사라짐 확인. 원본 558건을 유지했고 삭제 후 총 558건 확인 |
| 그래프·JSON 다운로드·다크 모드 | 성공 | 배포 화면에서 기능 확인, 정상 화면 캡처 확보 |
| Swagger 및 Render·Vercel 접속 | 성공 | Swagger 문서와 두 배포 주소 접속 |
| 채팅 증빙 | 확보 | 저장된 대화 화면 캡처 |
| CRUD 증빙 | 확보 | 생성·조회·수정·삭제 화면 캡처 |

Function Calling 실환경 검증 로그:

```text
function_calling_response tool_call_count=1 tool_names=get_weekly_interest_data
trend_tool_success tool_name=get_weekly_interest_data returned_count=5
```

진단 로그에는 질문·대화 내용, 개인정보, API 키 또는 도구 인자가 포함되지 않습니다.

## 5. Function Calling과 MCP 검증 범위

Function Calling 도구 `get_weekly_interest_data`는 허용된 키워드와 날짜 범위에 대해 주간 데이터를 읽습니다. 실환경에서 모델의 호출 및 반환 건수를 확인했으며, 이는 모든 질문 유형의 응답 품질 평가를 의미하지 않습니다.

MCP 검증은 다음을 완료했습니다.

- **가짜 Firestore 테스트:** 서버 도구 등록과 호출, 반환 형태 확인
- **공식 SDK stdio 연결:** 별도 MCP 서버 프로세스에 연결해 도구 목록과 잘못된 입력 처리 확인
- **Claude Code 외부 클라이언트 실환경:** 등록 서버 `Connected` 및 `query_weekly_interest` 도구 표시 확인. 키워드 `퍼스널브랜딩`, 기간 `2026-01-01`~`2026-03-31` 조건으로 읽기 전용 조회 1회 수행, Firestore 데이터 13건 반환, 오류 없음

## 6. 자동화 테스트 결과

| 대상 | 테스트 수 | 결과 | 주요 범위 |
| --- | ---: | --- | --- |
| 백엔드 | 83 | 모두 통과 | 설정·보안 입력, 데이터 API, 요약, 채팅·대화, Function Calling, MCP SDK, 데이터 변환 |
| 프론트엔드 | 20 | 모두 통과 | 그래프, 이동평균, JSON 직렬화, 다크 모드, 대화 흐름 |
| 합계 | 103 | 모두 통과 | 저장소 자동화 테스트 |

실행 명령은 백엔드 `python -m unittest discover -s backend/tests -v`, 프론트엔드 `node --test frontend/tests/*.test.mjs`입니다. 프론트엔드 대화 흐름 테스트 7개는 가짜 응답으로 목록 조회·선택·상세 조회·메시지 복원과 오류 상태를 확인합니다. 외부 AI 및 Firestore 운영 동작은 자동화 테스트에서 주로 모의 객체로 대체했습니다.

## 7. 배포 및 제출 증빙

| 서비스 | 주소 | 결과 |
| --- | --- | --- |
| Render 백엔드 | <https://branding-trend-ai-assistant.onrender.com> | 접속·Swagger 확인, 최신 Live 커밋 `86a71b6` |
| Vercel 프론트엔드 | <https://branding-trend-ai-assistant-fronten.vercel.app> | 접속 및 Render API 설정 확인 |

제출 증빙 이미지 (모두 `evidence/`에 존재 확인):

- [운영 데이터가 표시된 대시보드](evidence/readonly_01_dashboard.png)
- [다크 모드 대시보드](evidence/readonly_05_dark_mode.png)
- [Render Swagger](evidence/readonly_06_render_swagger.png)
- [저장된 AI 채팅](evidence/submission_chat_saved.png)
- [3개월 그래프](evidence/submission_graph_3m.png)
- [JSON 다운로드](evidence/submission_json_download.png)
- [테스트 레코드 조회](evidence/submission_crud_read.png)
- [테스트 레코드 생성](evidence/submission_crud_create.png)
- [테스트 레코드 수정](evidence/submission_crud_update.png)
- [테스트 레코드 삭제](evidence/submission_crud_delete.png)

채팅, 그래프, JSON 다운로드와 CRUD 각 단계를 보여주는 정상 화면 증빙을 확보했습니다.

## 8. 개발 과정의 문제와 해결

| 문제 | 원인 | 해결 및 결과 |
| --- | --- | --- |
| Render에서 Function Calling INFO 로그가 보이지 않음 | Uvicorn 기본 설정이 앱 INFO 로그를 출력하지 않음 | 요청·오류 로그를 유지하며 앱 INFO 출력을 설정하고 관련 테스트 추가 |
| 성공 로그에 도구 인자가 포함될 가능성 | 기존 로그가 키워드와 조회 날짜를 기록 | 도구 이름·반환 개수만 남기고 테스트로 확인 |
| 채팅 실환경 검증에서 POST 차단 | 자동화가 테스트 대화를 선택하지 않아 POST에 테스트 ID 누락 | 대화 선택·상세 조회 뒤 질문을 보내도록 수정, 이후 채팅 HTTP 200 성공 |
| 초기 채팅 캡처 이미지 검증 실패 | 자동화 캡처의 PNG 검증 실패 | 검증된 채팅 화면 캡처를 별도로 확보 |

## 9. 한계와 개선 방향

- 자동화 테스트가 외부 AI와 Firestore의 모든 운영 동작을 대신하지 않습니다.

## 10. 결론 및 학습 성과

시계열 자료를 저장·요약하고 그래프와 AI 채팅에서 활용하는 흐름을 구현했습니다. Function Calling과 MCP가 같은 읽기 전용 조회 기능을 재사용하도록 구성했으며, Function Calling 실환경 성공과 Claude Code 외부 MCP 클라이언트의 Firestore 조회 성공을 확인했습니다. 로그에서 민감한 질문·대화·도구 인자를 제외하는 진단 방식을 적용했습니다.

제출 시에는 요구사항 대응표의 추가 확인 범위와 증빙 목록을 함께 검토할 수 있습니다.
