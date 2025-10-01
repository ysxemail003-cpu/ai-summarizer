import os
import sys
import importlib.util

# 将项目根目录加入 sys.path，保证可导入 aipart
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from aipart.services.stt import get_stt_engine

spec = importlib.util.find_spec('faster_whisper')
e = get_stt_engine()
print('faster_whisper_installed =', bool(spec))
print('engine_available        =', e.available)
print('engine_name             =', e.name)
