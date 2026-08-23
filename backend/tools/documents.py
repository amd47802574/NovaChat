"""文档列表查询工具"""
from typing import Optional

try:
    from langchain_core.tools import tool
except ImportError:
    from langchain_core.tools import tool

from backend.infra.database import SessionLocal
from backend.db.models import ParentChunk
from sqlalchemy import func


@tool("list_documents")
def list_documents(detailed: bool = False) -> str:
    """
    列出知识库中的所有文档及其片段数量。
    当用户希望了解知识库中有哪些可用文档时使用此工具。

    Args:
        detailed: 若为 True，则包含每个文档的文件类型和最后更新时间。

    Returns:
        包含文档名称和片段数量的格式化字符串。
    """
    try:
        with SessionLocal() as session:
            # Query document statistics grouped by filename
            query = session.query(
                ParentChunk.filename,
                ParentChunk.file_type,
                func.count(ParentChunk.chunk_id).label('chunk_count'),
                func.max(ParentChunk.updated_at).label('last_updated')
            ).group_by(
                ParentChunk.filename,
                ParentChunk.file_type
            ).order_by(ParentChunk.filename)
            
            results = query.all()
            
            if not results:
                return "知识库中暂无文档。请先上传文档后再查询。"
            
            # Format output
            total_chunks = sum(r.chunk_count for r in results)
            output_lines = [f"知识库中共有 {len(results)} 个文档，{total_chunks} 个片段：\n"]
            
            for i, doc in enumerate(results, 1):
                if detailed:
                    output_lines.append(
                        f"{i}. {doc.filename}\n"
                        f"   - 片段数：{doc.chunk_count}\n"
                        f"   - 文件类型：{doc.file_type or '未知'}\n"
                        f"   - 最后更新：{doc.last_updated.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                else:
                    output_lines.append(f"{i}. {doc.filename} ({doc.chunk_count} 个片段)")
            
            return "\n".join(output_lines)
            
    except Exception as e:
        return f"查询文档列表失败：{str(e)}"