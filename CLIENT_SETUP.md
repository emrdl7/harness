# CLIENT_SETUP

## 사전 준비

서버 담당자로부터 받아야 하는 정보:
- `HARNESS_URL` — 서버 WebSocket 주소 (예: `ws://123.45.67.89:7891`)
- `HARNESS_TOKEN` — 인증 토큰
- `HARNESS_ROOM` — 공유 룸 이름 (선택)

## 필수 조건

- [Bun](https://bun.sh) >= 1.2.19
- macOS 또는 Linux (Windows: WSL2)

## 설치

```bash
git clone https://github.com/emrdl7/harness
cd harness/ui-ink
bun install --frozen-lockfile
```

## 실행

```bash
HARNESS_URL=ws://서버IP:7891 \
HARNESS_TOKEN=토큰문자열 \
bun start
```

공유 룸 참여 시:
```bash
HARNESS_URL=ws://서버IP:7891 \
HARNESS_TOKEN=토큰문자열 \
HARNESS_ROOM=팀룸이름 \
bun start
```

## 업데이트

```bash
git pull
cd ui-ink && bun install --frozen-lockfile
```

## 문제 해결

**bun: command not found**
```bash
curl -fsSL https://bun.sh/install | bash
```

**native dependency 설치 실패**
```bash
bun install --frozen-lockfile --ignore-scripts
```

**연결 실패 (ECONNREFUSED)**
- `HARNESS_URL` 주소/포트 확인
- 서버에서 7891 포트 개방 여부 확인

**macOS 한국어 입력 (IME)**
- Shift+Enter 대신 Ctrl+J 로 개행
