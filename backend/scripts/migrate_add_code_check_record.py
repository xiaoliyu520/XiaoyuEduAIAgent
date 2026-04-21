"""
创建代码检查记录表

执行方式：
cd backend
python -m scripts.migrate_add_code_check_record
"""

import asyncio
from sqlalchemy import text
from app.core.database import async_engine


async def migrate():
    async with async_engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS code_check_records (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                code TEXT NOT NULL,
                language VARCHAR(50) DEFAULT 'python',
                code_hash VARCHAR(64) DEFAULT '',
                execution_status VARCHAR(50) DEFAULT '',
                execution_result TEXT DEFAULT '',
                analysis_result TEXT DEFAULT '',
                final_report TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_code_check_records_user_id ON code_check_records(user_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_code_check_records_code_hash ON code_check_records(code_hash);
        """))
        
        print("✅ code_check_records 表创建成功")


if __name__ == "__main__":
    asyncio.run(migrate())
