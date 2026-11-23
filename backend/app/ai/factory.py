"""環境変数 `AI_PROVIDER` から、AIプロバイダーを選ぶ。"""

from app.ai.mock_provider import MockProvider
from app.ai.provider import ConciergeProvider
from app.crypto import ConfigurationError


def get_provider(name: str) -> ConciergeProvider:
    """`mock`（ルールベースのモック）を返す。`llm`（LLM API）は、まだ実装されていない。

    未実装の値や、知らない値は、起動のときに原因の分かるエラーにする（`app.main`）。
    値そのものは、エラーのメッセージに含めない。
    """
    if name == "mock":
        return MockProvider()
    if name == "llm":
        raise ConfigurationError(
            "AI_PROVIDER=llm（LLM API）は、まだ実装されていません。"
            "`mock` にするか、空のまま（既定は mock）にしてください。"
        )
    raise ConfigurationError("AI_PROVIDER の値が正しくありません。`mock` を指定してください。")
