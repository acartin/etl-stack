
-- 1. Agregar columna 'category' si no existe (default: knowledge_base)
ALTER TABLE ai_knowledge_documents 
ADD COLUMN IF NOT EXISTS category VARCHAR(100) DEFAULT 'knowledge_base';

-- 2. Actualizar registros antiguos que queden en NULL
UPDATE ai_knowledge_documents 
SET category = 'knowledge_base' 
WHERE category IS NULL;
