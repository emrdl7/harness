# harness 클라이언트 세팅 가이드

AI가 이 문서를 읽고 클라이언트 환경을 자동 세팅하기 위한 절차 문서.

## 전제 조건

- 서버 담당자로부터 다음 3가지를 받아야 함:
  - 서버 고정 IP (예: `123.456.789.0`)
  - 포트 (기본값: `7891`)
  - 접속 토큰 문자열

## 세팅 절차

### 1. Node.js 확인

```bash
node --version  # v18 이상 필요
```

없으면 설치:
```bash
brew install node   # macOS
# 또는 https://nodejs.org 에서 LTS 버전 설치
```

### 2. harness 클론

```bash
git clone https://github.com/emrdl7/harness
cd harness/ui
```

### 3. 의존성 설치

```bash
npm install
```

### 4. 접속 실행

```bash
HARNESS_HOST=서버IP \
HARNESS_PORT=7891 \
HARNESS_TOKEN=토큰문자열 \
node index.js
```

### 5. (선택) 편의를 위한 alias 등록

`~/.zshrc` 또는 `~/.bashrc`에 추가:

```bash
alias harness='HARNESS_HOST=서버IP HARNESS_PORT=7891 HARNESS_TOKEN=토큰문자열 node ~/harness/ui/index.js'
```

적용:
```bash
source ~/.zshrc
```

이후 `harness` 명령어만으로 접속 가능.

## 업데이트

```bash
cd ~/harness
git pull
cd ui && npm install
```

## 연결 확인

접속 성공 시 터미널에 다음과 같이 출력됨:
```
● qwen3-coder:30b
…/작업디렉토리 ❯ [0]
```

연결 실패 시 `harness server 연결 실패` 메시지 출력 → IP/포트/토큰 재확인.

## 환경변수 정리

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `HARNESS_HOST` | 서버 IP 또는 도메인 | `localhost` |
| `HARNESS_PORT` | 서버 포트 | `7891` |
| `HARNESS_TOKEN` | 인증 토큰 | (없음) |
