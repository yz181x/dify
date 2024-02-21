import logging

from langchain.document_loaders.base import BaseLoader
from langchain.schema import Document

logger = logging.getLogger(__name__)


class UnstructuredXmlLoader(BaseLoader):
    """Load msg files.


    Args:
        file_path: Path to the file to load.
    """

    def __init__(
        self,
        file_path: str,
        api_url: str
    ):
        """Initialize with file path."""
        self._file_path = file_path
        self._api_url = api_url

    def load(self) -> list[Document]:
        from unstructured.partition.xml import partition_xml

        elements = partition_xml(filename=self._file_path, xml_keep_tags=True, api_url=self._api_url)
        from unstructured.chunking.title import chunk_by_title
        chunks = chunk_by_title(elements, max_characters=2000, combine_text_under_n_chars=0)
        documents = []
        for chunk in chunks:
            text = chunk.text.strip()
            documents.append(Document(page_content=text))

        return documents
