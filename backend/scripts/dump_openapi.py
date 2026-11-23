"""APIのOpenAPI（JSON）を、標準出力に書き出す。

フロントエンドの型を生成するときに使う（`frontend` で `npm run gen:api`）。
アプリの起動（DBの作成や、暗号化の鍵の検証）は行わないので、鍵がなくても動く。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402  パスを通してから読み込む

print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))
