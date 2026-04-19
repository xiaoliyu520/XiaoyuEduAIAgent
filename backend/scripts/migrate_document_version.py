#!/usr/bin/env python3
"""
数据库迁移脚本：为知识库文档添加版本管理功能
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.core.database import engine


async def migrate():
    async with engine.begin() as conn:
        print("开始数据库迁移...")

        print("1. 为 knowledge_documents 表添加新字段...")
        try:
            await conn.execute(text("""
                ALTER TABLE knowledge_documents
                ADD COLUMN IF NOT EXISTS file_size INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64) DEFAULT '',
                ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """))
            print("   - 字段添加成功")
        except Exception as e:
            print(f"   - 字段已存在或添加失败: {e}")

        print("2. 创建 document_versions 表...")
        try:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS document_versions (
                    id SERIAL PRIMARY KEY,
                    doc_id INTEGER NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                    version INTEGER NOT NULL,
                    file_path VARCHAR(500) NOT NULL,
                    content_hash VARCHAR(64) DEFAULT '',
                    chunk_count INTEGER DEFAULT 0,
                    change_type VARCHAR(20) DEFAULT 'created',
                    change_summary TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("   - 表创建成功")
        except Exception as e:
            print(f"   - 表已存在或创建失败: {e}")

        print("3. 为 document_versions 表添加索引...")
        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_document_versions_doc_id
                ON document_versions(doc_id)
            """))
            print("   - 索引创建成功")
        except Exception as e:
            print(f"   - 索引创建失败: {e}")

        print("\n迁移完成！")


if __name__ == "__main__":
    asyncio.run(migrate())
