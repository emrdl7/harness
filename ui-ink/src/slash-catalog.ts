// 슬래시 명령 카탈로그 — D-06 정적 하드코딩 (INPT-09, INPT-10)
// 런타임에 서버로부터 불러오지 않음. 명령 목록 변경 시 이 파일을 직접 편집.

export interface SlashCommand {
  name: string         // '/' 제외 (예: 'help')
  summary: string      // 한 줄 설명 (한국어)
  usage?: string       // 인자 포맷 힌트 (예: '<path>')
}

export const SLASH_CATALOG: readonly SlashCommand[] = Object.freeze([
  {name: 'help',    summary: '명령 목록 표시'},
  {name: 'clear',   summary: '대화 초기화'},
  {name: 'quit',    summary: '세션 종료'},
  {name: 'exit',    summary: '세션 종료 (quit alias)'},
  {name: 'cd',      summary: '작업 디렉터리 변경', usage: '<path>'},
  {name: 'pwd',     summary: '현재 작업 디렉터리 표시'},
  {name: 'model',   summary: '모델 변경', usage: '<name>'},
  {name: 'mode',    summary: '모드 변경 (agent/plan/...)', usage: '<name>'},
  {name: 'save',    summary: '세션 저장', usage: '[name]'},
  {name: 'load',    summary: '세션 불러오기', usage: '<name>'},
  {name: 'history', summary: '명령 히스토리 표시'},
  {name: 'reset',   summary: '컨텍스트 초기화'},
  {name: 'status',  summary: '현재 상태 요약'},
])

export function filterSlash(query: string): readonly SlashCommand[] {
  const q = query.replace(/^\//, '').toLowerCase()
  if (!q) return SLASH_CATALOG
  return SLASH_CATALOG.filter((c) => c.name.toLowerCase().startsWith(q))
}
