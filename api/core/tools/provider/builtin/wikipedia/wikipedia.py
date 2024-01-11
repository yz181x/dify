from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController
from core.tools.errors import ToolProviderCredentialValidationError

from core.tools.provider.builtin.wikipedia.tools.wikipedia_search import WikiPediaSearchTool

from typing import Any, Dict, List

class WikiPediaProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict) -> None:
        try:
            WikiPediaSearchTool().fork_processing_tool(
                meta={
                    "credentials": credentials,
                }
            ).invoke(
                user_id='',
                tool_paramters={
                    "query": "misaka mikoto",
                },
            )
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))