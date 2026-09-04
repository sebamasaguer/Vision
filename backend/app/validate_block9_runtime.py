from pathlib import Path
from sqlalchemy import inspect, select
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models.access import Permission
from app.models.vision import VisionModelVersion
from app.models.ml import MLDataset, MLTrainingRun, MLModelDeployment, MLShadowObservation
from app.services.ml_registry import model_available, file_sha256


def main():
    i=inspect(engine); tables=set(i.get_table_names())
    required={'ml_datasets','ml_dataset_versions','ml_training_runs','ml_model_deployments','ml_shadow_observations'}
    missing=required-tables
    if missing: raise SystemExit('BLOCK9_SCHEMA_FAIL '+','.join(sorted(missing)))
    cols={c['name'] for c in i.get_columns('vision_model_versions')}
    need={'artifact_uri','artifact_sha256','framework','model_stage','input_width','input_height','class_map','metrics_json','approved_at','approved_by_user_id'}
    if not need<=cols: raise SystemExit('BLOCK9_MODEL_COLUMNS_FAIL '+','.join(sorted(need-cols)))
    with SessionLocal() as db:
        perms={x.code for x in db.scalars(select(Permission).where(Permission.code.in_(['ml.read','ml.manage','ml.train'])))}
        if perms!={'ml.read','ml.manage','ml.train'}: raise SystemExit('BLOCK9_RBAC_FAIL')
        intel=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code=='INTEL_WORKER_SAFETY_BOOTSTRAP'))
        if not intel: raise SystemExit('BLOCK9_INTEL_SEED_FAIL')
        meta=intel.model_metadata or {}
        if intel.license_name!='MIT' or meta.get('detection_output_label_map')!={'1':'HELMET','2':'VEST'}: raise SystemExit('BLOCK9_INTEL_METADATA_FAIL')
        print(f'BLOCK9_SCHEMA_OK {",".join(sorted(required))}')
        print('BLOCK9_MODEL_COLUMNS_OK '+str(len(need)))
        print('BLOCK9_RBAC_OK ml.read,ml.manage,ml.train')
        print(f'BLOCK9_INTEL_OK active={intel.active} available={model_available(intel)} artifact={intel.artifact_uri}')
        print(f'BLOCK9_ML_COUNTS datasets={db.query(MLDataset).count()} runs={db.query(MLTrainingRun).count()} deployments={db.query(MLModelDeployment).count()} shadow={db.query(MLShadowObservation).count()}')

if __name__=='__main__': main()
