"""add_clip_embedding

Revision ID: a1b2c3d4e5f6
Revises: eb7ce1bf9db5
Create Date: 2024-05-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'eb7ce1bf9db5'  # 이전 리비전 ID (환경에 맞춰 수정 필요)
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. CLIP Embedding 컬럼 추가 (512차원)
    op.add_column('products', sa.Column('embedding_clip', Vector(512), nullable=True))
    
    # 2. HNSW 인덱스 생성 (속도 최적화)
    # vector_cosine_ops 사용 (Cosine Distance 기반)
    op.create_index(
        'ix_product_embedding_clip_hnsw',
        'products',
        ['embedding_clip'],
        postgresql_using='hnsw',
        postgresql_with={'m': 16, 'ef_construction': 64},
        postgresql_ops={'embedding_clip': 'vector_cosine_ops'}
    )

def downgrade() -> None:
    op.drop_index('ix_product_embedding_clip_hnsw', table_name='products')
    op.drop_column('products', 'embedding_clip')