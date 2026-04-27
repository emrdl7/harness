import os

# 추론 백엔드 — 'ollama' (기본) | 'mlx' (mlx_lm.server OpenAI 호환)
BACKEND         = os.environ.get('HARNESS_BACKEND',     'ollama')
OLLAMA_BASE_URL = os.environ.get('HARNESS_OLLAMA_URL', 'http://localhost:11434')
MLX_BASE_URL    = os.environ.get('HARNESS_MLX_URL',    'http://localhost:8080')
# MLX Qwen3.6 thinking 모드 — 기본 off (켜면 reasoning 필드로만 출력되어 툴콜 무력화)
MLX_THINKING    = os.environ.get('HARNESS_MLX_THINKING', '0').lower() in ('1', 'true', 'yes')
MODEL           = os.environ.get('HARNESS_MODEL',      'qwen3-coder:30b')
MAX_RETRIES     = 3

# 승인 모드: suggest(제안만) | auto-edit(파일 쓸 때마다 확인) | full-auto(모두자동)
# 기본 full-auto — 혼자 쓰는 로컬 CLI 특성상 매번 y/n 물어보면 번거롭다.
# 안전하게 쓰려면 HARNESS_APPROVAL=auto-edit 환경변수나 /mode auto-edit 로 전환.
# full-auto 에서도 agent.py 가 fs.set_sandbox(working_dir) 로 작업 디렉토리
# 밖 쓰기 차단, run_python 은 항상 confirm 강제.
APPROVAL_MODE   = os.environ.get('HARNESS_APPROVAL', 'full-auto')
CONTEXT_WINDOW  = int(os.environ.get('HARNESS_CTX',  '32768'))

# Ollama 생성 파라미터 — 환경변수로 오버라이드 가능
OLLAMA_OPTIONS = {
    'temperature':    float(os.environ.get('HARNESS_TEMP',    '0.2')),
    'top_p':          0.9,
    'repeat_penalty': 1.1,
    'num_ctx':        CONTEXT_WINDOW,
    'num_predict':    int(os.environ.get('HARNESS_PREDICT', '4096')),
}

# 자동 컨텍스트 검색 설정
RETRIEVAL_TOP_K = 8           # 유사 청크 몇 개 가져올지
RETRIEVAL_MIN_SCORE = 0.4     # 유사도 임계값 (낮을수록 관대)

# 반성 루프 설정
REFLECTION_THRESHOLD = 2      # 연속 실패 몇 번 후 반성 유도
MAX_ITERATIONS = 30           # 툴 루프 최대 반복
AGENT_TIMEOUT  = int(os.environ.get('HARNESS_AGENT_TIMEOUT', '600'))  # 전체 에이전트 제한 (초)


def runtime_override(profile: dict) -> None:
    '''profile.load() 결과로 모델 설정을 런타임에 오버라이드.
    main() 시작 시 profile 로드 직후 호출해야 함.
    .harness.toml의 backend/mlx_url/mlx_thinking/model/ollama_url/temperature/num_ctx/num_predict/approval_mode 키를 읽음.'''
    global MODEL, OLLAMA_BASE_URL, CONTEXT_WINDOW, OLLAMA_OPTIONS, APPROVAL_MODE
    global BACKEND, MLX_BASE_URL, MLX_THINKING
    if profile.get('backend'):
        BACKEND = profile['backend']
    if profile.get('mlx_url'):
        MLX_BASE_URL = profile['mlx_url']
    if 'mlx_thinking' in profile:
        MLX_THINKING = bool(profile['mlx_thinking'])
    if profile.get('model'):
        MODEL = profile['model']
    if profile.get('ollama_url'):
        OLLAMA_BASE_URL = profile['ollama_url']
    opts = dict(OLLAMA_OPTIONS)
    temp = profile.get('temperature', -1)
    if isinstance(temp, (int, float)) and temp >= 0:
        opts['temperature'] = float(temp)
    ctx = profile.get('num_ctx', 0)
    if ctx and ctx > 0:
        CONTEXT_WINDOW = ctx
        opts['num_ctx'] = ctx
    pred = profile.get('num_predict', 0)
    if pred and pred > 0:
        opts['num_predict'] = pred
    OLLAMA_OPTIONS = opts
    if profile.get('approval_mode'):
        APPROVAL_MODE = profile['approval_mode']
