import threading
from typing import Optional

from flask import Flask, current_app
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from core.callback_handler.index_tool_callback_handler import DatasetIndexToolCallbackHandler
from core.embedding.cached_embedding import CacheEmbedding
from core.errors.error import LLMBadRequestError, ProviderTokenNotInitError
from core.index.keyword_table_index.keyword_table_index import KeywordTableConfig, KeywordTableIndex
from core.model_manager import ModelManager
from core.model_runtime.entities.model_entities import ModelType
from core.rerank.rerank import RerankRunner
from extensions.ext_database import db
from models.dataset import Dataset, Document, DocumentSegment
from services.retrieval_service import RetrievalService

default_retrieval_model = {
    'search_method': 'semantic_search',
    'reranking_enable': False,
    'reranking_model': {
        'reranking_provider_name': '',
        'reranking_model_name': ''
    },
    'top_k': 2,
    'score_threshold_enabled': False
}


class DatasetMultiRetrieverToolInput(BaseModel):
    query: str = Field(..., description="dataset multi retriever and rerank")


class DatasetMultiRetrieverTool(BaseTool):
    """Tool for querying multi dataset."""
    name: str = "dataset-"
    args_schema: type[BaseModel] = DatasetMultiRetrieverToolInput
    description: str = "dataset multi retriever and rerank. "
    tenant_id: str
    dataset_ids: list[str]
    top_k: int = 2
    score_threshold: Optional[float] = None
    reranking_provider_name: str
    reranking_model_name: str
    return_resource: bool
    retriever_from: str
    hit_callbacks: list[DatasetIndexToolCallbackHandler] = []

    @classmethod
    def from_dataset(cls, dataset_ids: list[str], tenant_id: str, **kwargs):
        return cls(
            name=f'dataset-{tenant_id}',
            tenant_id=tenant_id,
            dataset_ids=dataset_ids,
            **kwargs
        )

    def _run(self, query: str) -> str:
        threads = []
        all_documents = []
        for dataset_id in self.dataset_ids:
            retrieval_thread = threading.Thread(target=self._retriever, kwargs={
                'flask_app': current_app._get_current_object(),
                'dataset_id': dataset_id,
                'query': query,
                'all_documents': all_documents,
                'hit_callbacks': self.hit_callbacks
            })
            threads.append(retrieval_thread)
            retrieval_thread.start()
        for thread in threads:
            thread.join()
        # do rerank for searched documents
        model_manager = ModelManager()
        rerank_model_instance = model_manager.get_model_instance(
            tenant_id=self.tenant_id,
            provider=self.reranking_provider_name,
            model_type=ModelType.RERANK,
            model=self.reranking_model_name
        )

        rerank_runner = RerankRunner(rerank_model_instance)
        all_documents = rerank_runner.run(query, all_documents, self.score_threshold, self.top_k)

        for hit_callback in self.hit_callbacks:
            hit_callback.on_tool_end(all_documents)

        document_score_list = {}
        for item in all_documents:
            if 'score' in item.metadata and item.metadata['score']:
                document_score_list[item.metadata['doc_id']] = item.metadata['score']

        document_context_list = []
        index_node_ids = [document.metadata['doc_id'] for document in all_documents]
        segments = DocumentSegment.query.filter(
            DocumentSegment.dataset_id.in_(self.dataset_ids),
            DocumentSegment.completed_at.isnot(None),
            DocumentSegment.status == 'completed',
            DocumentSegment.enabled == True,
            DocumentSegment.index_node_id.in_(index_node_ids)
        ).all()

        if segments:
            index_node_id_to_position = {id: position for position, id in enumerate(index_node_ids)}
            sorted_segments = sorted(segments,
                                     key=lambda segment: index_node_id_to_position.get(segment.index_node_id,
                                                                                       float('inf')))
            for segment in sorted_segments:
                if segment.answer:
                    document_context_list.append(f'question:{segment.content} answer:{segment.answer}')
                else:
                    document_context_list.append(segment.content)
            if self.return_resource:
                context_list = []
                resource_number = 1
                for segment in sorted_segments:
                    dataset = Dataset.query.filter_by(
                        id=segment.dataset_id
                    ).first()
                    document = Document.query.filter(Document.id == segment.document_id,
                                                     Document.enabled == True,
                                                     Document.archived == False,
                                                     ).first()
                    if dataset and document:
                        source = {
                            'position': resource_number,
                            'dataset_id': dataset.id,
                            'dataset_name': dataset.name,
                            'document_id': document.id,
                            'document_name': document.name,
                            'data_source_type': document.data_source_type,
                            'segment_id': segment.id,
                            'retriever_from': self.retriever_from,
                            'score': document_score_list.get(segment.index_node_id, None)
                        }

                        if self.retriever_from == 'dev':
                            source['hit_count'] = segment.hit_count
                            source['word_count'] = segment.word_count
                            source['segment_position'] = segment.position
                            source['index_node_hash'] = segment.index_node_hash
                        if segment.answer:
                            source['content'] = f'question:{segment.content} \nanswer:{segment.answer}'
                        else:
                            source['content'] = segment.content
                        context_list.append(source)
                    resource_number += 1

                for hit_callback in self.hit_callbacks:
                    hit_callback.return_retriever_resource_info(context_list)

            return str("\n".join(document_context_list))

    async def _arun(self, tool_input: str) -> str:
        raise NotImplementedError()

    def _retriever(self, flask_app: Flask, dataset_id: str, query: str, all_documents: list,
                   hit_callbacks: list[DatasetIndexToolCallbackHandler]):
        with flask_app.app_context():
            dataset = db.session.query(Dataset).filter(
                Dataset.tenant_id == self.tenant_id,
                Dataset.id == dataset_id
            ).first()

            if not dataset:
                return []

            for hit_callback in hit_callbacks:
                hit_callback.on_query(query, dataset.id)

            # get retrieval model , if the model is not setting , using default
            retrieval_model = dataset.retrieval_model if dataset.retrieval_model else default_retrieval_model

            if dataset.indexing_technique == "economy":
                # use keyword table query
                kw_table_index = KeywordTableIndex(
                    dataset=dataset,
                    config=KeywordTableConfig(
                        max_keywords_per_chunk=5
                    )
                )

                documents = kw_table_index.search(query, search_kwargs={'k': self.top_k})
                if documents:
                    all_documents.extend(documents)
            else:

                try:
                    model_manager = ModelManager()
                    embedding_model = model_manager.get_model_instance(
                        tenant_id=dataset.tenant_id,
                        provider=dataset.embedding_model_provider,
                        model_type=ModelType.TEXT_EMBEDDING,
                        model=dataset.embedding_model
                    )
                except LLMBadRequestError:
                    return []
                except ProviderTokenNotInitError:
                    return []

                embeddings = CacheEmbedding(embedding_model)

                documents = []
                threads = []
                if self.top_k > 0:
                    # retrieval_model source with semantic
                    if retrieval_model['search_method'] == 'semantic_search' or retrieval_model[
                        'search_method'] == 'hybrid_search':
                        embedding_thread = threading.Thread(target=RetrievalService.embedding_search, kwargs={
                            'flask_app': current_app._get_current_object(),
                            'dataset_id': str(dataset.id),
                            'query': query,
                            'top_k': self.top_k,
                            'score_threshold': self.score_threshold,
                            'reranking_model': None,
                            'all_documents': documents,
                            'search_method': 'hybrid_search',
                            'embeddings': embeddings
                        })
                        threads.append(embedding_thread)
                        embedding_thread.start()

                    # retrieval_model source with full text
                    if retrieval_model['search_method'] == 'full_text_search' or retrieval_model[
                        'search_method'] == 'hybrid_search':
                        full_text_index_thread = threading.Thread(target=RetrievalService.full_text_index_search,
                                                                  kwargs={
                                                                      'flask_app': current_app._get_current_object(),
                                                                      'dataset_id': str(dataset.id),
                                                                      'query': query,
                                                                      'search_method': 'hybrid_search',
                                                                      'embeddings': embeddings,
                                                                      'score_threshold': retrieval_model[
                                                                          'score_threshold'] if retrieval_model[
                                                                          'score_threshold_enabled'] else None,
                                                                      'top_k': self.top_k,
                                                                      'reranking_model': retrieval_model[
                                                                          'reranking_model'] if retrieval_model[
                                                                          'reranking_enable'] else None,
                                                                      'all_documents': documents
                                                                  })
                        threads.append(full_text_index_thread)
                        full_text_index_thread.start()

                    for thread in threads:
                        thread.join()

                    all_documents.extend(documents)