"""Initial migration

Revision ID: 001_initial
Revises:
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create cameras table
    op.create_table(
        'cameras',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_url', sa.String(length=500), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False, server_default='rtsp'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('fps', sa.Float(), nullable=True),
        sa.Column('resolution_width', sa.Integer(), nullable=True),
        sa.Column('resolution_height', sa.Integer(), nullable=True),
        sa.Column('zones_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_cameras_is_active', 'cameras', ['is_active'])
    op.create_index('ix_cameras_source_type', 'cameras', ['source_type'])

    # Create frame_metadata table
    op.create_table(
        'frame_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('camera_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('frame_number', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('s3_key', sa.String(length=500), nullable=True),
        sa.Column('s3_bucket', sa.String(length=100), nullable=True),
        sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('format', sa.String(length=20), nullable=False, server_default='jpeg'),
        sa.Column('processing_time_ms', sa.Float(), nullable=False),
        sa.Column('inference_time_ms', sa.Float(), nullable=False),
        sa.Column('detection_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('anomaly_score', sa.Float(), nullable=True),
        sa.Column('is_anomaly', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_frame_metadata_camera_time', 'frame_metadata', ['camera_id', 'timestamp'])
    op.create_index('ix_frame_metadata_anomaly', 'frame_metadata', ['is_anomaly', 'timestamp'])
    op.create_index('ix_frame_metadata_frame_num', 'frame_metadata', ['camera_id', 'frame_number'])

    # Create detection_events table
    op.create_table(
        'detection_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('camera_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('frame_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('x_min', sa.Float(), nullable=False),
        sa.Column('y_min', sa.Float(), nullable=False),
        sa.Column('x_max', sa.Float(), nullable=False),
        sa.Column('y_max', sa.Float(), nullable=False),
        sa.Column('class_id', sa.Integer(), nullable=False),
        sa.Column('class_name', sa.String(length=100), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('inference_time_ms', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['frame_id'], ['frame_metadata.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_detection_events_camera_time', 'detection_events', ['camera_id', 'created_at'])
    op.create_index('ix_detection_events_class_conf', 'detection_events', ['class_id', 'confidence'])
    op.create_index('ix_detection_events_frame', 'detection_events', ['frame_id'])

    # Create audio_analysis table
    op.create_table(
        'audio_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('frame_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mfcc_features', sa.JSON(), nullable=True),
        sa.Column('spectral_centroid', sa.Float(), nullable=True),
        sa.Column('spectral_rolloff', sa.Float(), nullable=True),
        sa.Column('zero_crossing_rate', sa.Float(), nullable=True),
        sa.Column('rms_energy', sa.Float(), nullable=True),
        sa.Column('anomaly_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('is_anomaly', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('inference_time_ms', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['frame_id'], ['frame_metadata.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('frame_id'),
    )
    op.create_index('ix_audio_analysis_anomaly', 'audio_analysis', ['is_anomaly', 'anomaly_score'])

    # Create system_telemetry table
    op.create_table(
        'system_telemetry',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('component', sa.String(length=100), nullable=False),
        sa.Column('instance_id', sa.String(length=100), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('metric_unit', sa.String(length=50), nullable=False),
        sa.Column('labels', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_telemetry_component_metric_time', 'system_telemetry', ['component', 'metric_name', 'timestamp'])
    op.create_index('ix_telemetry_instance_time', 'system_telemetry', ['instance_id', 'timestamp'])

    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('camera_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('frame_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('is_acknowledged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('acknowledged_by', sa.String(length=100), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_by', sa.String(length=100), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['frame_id'], ['frame_metadata.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_alerts_camera_severity_time', 'alerts', ['camera_id', 'severity', 'created_at'])
    op.create_index('ix_alerts_state_time', 'alerts', ['is_acknowledged', 'is_resolved', 'created_at'])


def downgrade() -> None:
    op.drop_table('alerts')
    op.drop_table('system_telemetry')
    op.drop_table('audio_analysis')
    op.drop_table('detection_events')
    op.drop_table('frame_metadata')
    op.drop_table('cameras')