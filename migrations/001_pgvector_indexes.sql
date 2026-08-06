-- Run after the SQLAlchemy tables have been created and representative data exists.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
ON document_chunks
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS ix_documents_department_status
ON documents (department_id, status);

CREATE INDEX IF NOT EXISTS ix_document_chunks_department
ON document_chunks (department_id);
