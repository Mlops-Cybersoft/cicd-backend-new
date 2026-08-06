-- Defense-in-depth policies. Apply with a migration role after validating your
-- background-worker role and connection-pool transaction context.
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY documents_department_access ON documents
FOR SELECT
USING (
    current_setting('app.current_user_role', true) = 'admin'
    OR owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
    OR visibility = 'company'
    OR (
        current_setting('app.current_user_role', true) = 'manager'
        AND department_id = NULLIF(
            current_setting('app.current_department_id', true), ''
        )::uuid
    )
    OR (
        department_id = NULLIF(
            current_setting('app.current_department_id', true), ''
        )::uuid
        AND visibility IN ('department', 'shared')
    )
    OR EXISTS (
        SELECT 1
        FROM document_permissions permission
        WHERE permission.document_id = documents.id
          AND permission.permission IN ('read', 'manage')
          AND (
              (
                  permission.grantee_type = 'user'
                  AND permission.grantee_id = NULLIF(
                      current_setting('app.current_user_id', true), ''
                  )::uuid
              )
              OR (
                  permission.grantee_type = 'department'
                  AND permission.grantee_id = NULLIF(
                      current_setting('app.current_department_id', true), ''
                  )::uuid
              )
          )
    )
);

CREATE POLICY chunks_follow_document_access ON document_chunks
FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM documents WHERE documents.id = document_chunks.document_id
    )
);
