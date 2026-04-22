'''pytest 공통 설정.

프로젝트 루트를 sys.path에 추가해 `import agent`, `import tools` 등이 동작하도록.
'''
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
