# harness 클라이언트 세팅 가이드

AI가 이 문서를 읽고 클라이언트 환경을 자동 세팅하기 위한 절차 문서.

## 전제 조건

- 서버 담당자로부터 다음 3가지를 받아야 함:
  - 서버 고정 IP (예: `123.456.789.0`)
  - 포트 (기본값: `7891`)
  - 접속 토큰 문자열 (서버 담당자가 `openssl rand -hex 32`로 생성한 값)

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

### 4-1. (선택) 공유 룸 합류

여러 사용자가 같은 세션(messages·working_dir 공유)을 함께 보고 싶다면
같은 룸 이름으로 접속:

```bash
node index.js --room team        # CLI 인자
HARNESS_ROOM=team node index.js  # 환경변수도 지원
```

룸 안에서:
- agent/claude 출력은 모든 멤버에게 broadcast
- 한 명이 입력 중이면 나머지는 `room_busy`로 즉시 거부
- `confirm_write`/`confirm_bash` 승인은 입력자만 가능
- `/who` 슬래시로 현재 멤버·busy 상태 조회

룸 이름을 안 주면 매 연결마다 격리된 솔로 룸이 부여됩니다.

### 5. (선택) 편의를 위한 alias 등록

⚠️ **토큰을 `~/.zshrc`에 직접 적지 마세요.** 셸 RC 파일은 기본적으로
타인에게 읽힐 수 있고, 클라우드 백업·도트파일 동기화로 노출됩니다.
토큰은 원격 셸 권한에 해당하므로 누설 시 임의 명령 실행이 가능합니다.

**권장 방식 — 0600 권한의 별도 비밀 파일을 source 합니다:**

```bash
# 1) 비밀 파일 생성 (한 번만)
cat > ~/.harness.env <<'ENV'
export HARNESS_HOST=서버IP
export HARNESS_PORT=7891
export HARNESS_TOKEN=토큰문자열
ENV
chmod 600 ~/.harness.env

# 2) ~/.zshrc 또는 ~/.bashrc 에 alias만 추가 (토큰 미포함)
alias harness='. ~/.harness.env && node ~/harness/ui/index.js'
```

**macOS 사용자**라면 keychain을 쓰는 것이 더 안전합니다:

```bash
# 토큰 저장
security add-generic-password -a "$USER" -s harness-token -w "토큰문자열"

# alias
alias harness='HARNESS_HOST=서버IP HARNESS_PORT=7891 \
  HARNESS_TOKEN="$(security find-generic-password -a "$USER" -s harness-token -w)" \
  node ~/harness/ui/index.js'
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
