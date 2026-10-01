import sys
from pathlib import Path

# permite "from conciliacao import ..." ao rodar pytest na raiz do projeto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
