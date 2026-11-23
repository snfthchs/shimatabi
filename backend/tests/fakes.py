"""テスト用の部品。"""

import datetime
from dataclasses import dataclass


@dataclass
class FakeClock:
    """時刻を固定して、テストの中で進められる時計。`app.deps.get_now` の代わりに使う。"""

    now: datetime.datetime
