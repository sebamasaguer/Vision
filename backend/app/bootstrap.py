import time
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.access import Permission, Role, User
from app.models.safety import PPEType
from app.models.organization import Organization
from app.models.ml import MLDataset

PERMISSIONS = {
    "organization.create": "Crear organizaciones/clientes",
    "organization.read": "Consultar organizaciones/clientes",
    "structure.manage": "Administrar establecimientos, plantas y sectores",
    "structure.read": "Consultar estructura organizacional",
    "user.manage": "Administrar usuarios y roles",
    "user.read": "Consultar usuarios",
    "audit.read": "Consultar auditoría",
    "system.read": "Consultar estado del sistema",
    "camera.read": "Consultar cámaras y video",
    "camera.manage": "Administrar cámaras y fuentes RTSP",
    "ppe.read": "Consultar catálogo de EPP",
    "ppe.manage": "Administrar catálogo de EPP",
    "zone.read": "Consultar zonas y reglas EPP",
    "zone.manage": "Administrar zonas y reglas EPP",
    "vision.read": "Consultar detecciones y tracking de vision artificial",
    "vision.manage": "Configurar motor de vision por camara",
    "safety_event.read": "Consultar eventos preventivos y evaluaciones de cumplimiento",
    "safety_event.manage": "Gestionar alertas, responsables, revisión humana y observaciones",
    "monitoring.read": "Consultar bandeja de monitoreo, SLA, escalamiento y notificaciones",
    "monitoring.manage": "Configurar SLA, canales de notificación y operación de monitoreo",
    "analytics.read": "Consultar dashboard ejecutivo, KPIs, analítica y heatmaps",
    "analytics.export": "Exportar reportes y datos analíticos",
    "ml.read": "Consultar datasets, modelos, training runs y shadow deployment",
    "ml.manage": "Administrar model registry y despliegues IA",
    "ml.train": "Crear y ejecutar entrenamientos HYS",
}
ROLE_MATRIX = {
    "SUPERADMIN": ("Superadministrador", "system", list(PERMISSIONS)),
    "ADMIN_EMPRESA": ("Administrador de empresa", "organization", ["organization.read","structure.manage","structure.read","user.manage","user.read","audit.read","system.read","camera.read","camera.manage","ppe.read","zone.read","zone.manage","vision.read","vision.manage","safety_event.read","safety_event.manage","monitoring.read","monitoring.manage","analytics.read","analytics.export","ml.read","ml.manage","ml.train"]),
    "RESPONSABLE_HYS": ("Responsable Higiene y Seguridad", "organization", ["organization.read","structure.read","user.read","audit.read","system.read","camera.read","camera.manage","ppe.read","zone.read","zone.manage","vision.read","vision.manage","safety_event.read","safety_event.manage","monitoring.read","monitoring.manage","analytics.read","analytics.export","ml.read","ml.manage","ml.train"]),
    "OPERADOR_MONITOREO": ("Operador centro de monitoreo", "organization", ["organization.read","structure.read","system.read","camera.read","ppe.read","zone.read","vision.read","safety_event.read","safety_event.manage","monitoring.read","monitoring.manage","analytics.read","analytics.export","ml.read"]),
    "AUDITOR": ("Auditor", "organization", ["organization.read","structure.read","audit.read","system.read","camera.read","ppe.read","zone.read","vision.read","safety_event.read","monitoring.read","analytics.read","ml.read"]),
    "CONSULTA": ("Consulta", "organization", ["organization.read","structure.read","system.read","camera.read","ppe.read","zone.read","vision.read","safety_event.read","monitoring.read","analytics.read","ml.read"]),
}

def seed_access_control(db: Session):
    permissions = {}
    for code, description in PERMISSIONS.items():
        item = db.scalar(select(Permission).where(Permission.code == code))
        if not item:
            item = Permission(code=code, description=description); db.add(item); db.flush()
        permissions[code] = item
    for code, (name, scope, permission_list) in ROLE_MATRIX.items():
        role = db.scalar(select(Role).where(Role.code == code))
        if not role:
            role = Role(code=code, name=name, scope=scope); db.add(role); db.flush()
        role.name = name; role.scope = scope; role.permissions = [permissions[p] for p in permission_list]
    db.commit()

DEFAULT_PPE = [
    ("HELMET", "Casco de seguridad", "hard-hat", "ALTA", "#4FE2B6", "helmet", 0.70),
    ("VEST", "Chaleco reflectivo", "vest", "ALTA", "#E5B85C", "vest", 0.70),
    ("SAFETY_SHOES", "Calzado de seguridad", "footprints", "ALTA", "#79A9FF", "safety_shoes", 0.70),
    ("GOGGLES", "Gafas de protección", "glasses", "ALTA", "#65D9E8", "goggles", 0.70),
    ("FACE_SHIELD", "Protector facial", "scan-face", "ALTA", "#B38CFF", "face_shield", 0.70),
    ("GLOVES", "Guantes", "hand", "ADVERTENCIA", "#B6C96A", "gloves", 0.70),
    ("EAR_PROTECTION", "Protección auditiva", "headphones", "ALTA", "#E5A45C", "ear_protection", 0.70),
    ("HARNESS", "Arnés", "shield-check", "CRITICA", "#EF7777", "harness", 0.75),
    ("MASK", "Mascarilla", "mask", "ADVERTENCIA", "#8BC7D1", "mask", 0.70),
    ("RESPIRATOR", "Respirador", "wind", "ALTA", "#C391E8", "respirator", 0.75),
    ("HIGH_VISIBILITY_CLOTHING", "Ropa de alta visibilidad", "shirt", "ALTA", "#D9E85C", "high_visibility_clothing", 0.70),
    ("WORK_CLOTHING", "Ropa de trabajo", "shirt", "ADVERTENCIA", "#8CA4AA", "work_clothing", 0.70),
]

def seed_ppe_catalog(db: Session):
    for code, name, icon, criticality, color, detector_class, confidence in DEFAULT_PPE:
        item = db.scalar(select(PPEType).where(PPEType.code == code))
        if not item:
            item = PPEType(code=code, name=name, icon=icon, criticality=criticality, color=color, detector_class=detector_class, min_confidence=confidence)
            db.add(item)
    db.commit()

def seed_admin(db: Session):
    admin = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.lower()))
    super_role = db.scalar(select(Role).where(Role.code == "SUPERADMIN"))
    if not admin:
        admin = User(email=settings.bootstrap_admin_email.lower(), full_name="Administrador HYS Vision", password_hash=hash_password(settings.bootstrap_admin_password), organization_id=None)
        admin.roles = [super_role]
        db.add(admin)
        db.commit()
    elif super_role not in admin.roles:
        admin.roles.append(super_role); db.commit()

def ensure_minio_bucket(retries: int = 10, delay_seconds: float = 3.0):
    # Reintenta ante fallas transitorias de red/DNS al arrancar (p.ej. el DNS
    # interno de Docker Compose todavia no propago el alias del servicio
    # "minio" a este contenedor en el primer intento). Sin esto, una unica
    # falla transitoria aca tumba todo el arranque del backend (bootstrap
    # corre antes de uvicorn).
    from minio import Minio
    client = Minio(settings.minio_endpoint, access_key=settings.minio_access_key, secret_key=settings.minio_secret_key, secure=settings.minio_secure)
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if not client.bucket_exists(settings.minio_bucket_evidence):
                client.make_bucket(settings.minio_bucket_evidence)
            return
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                print(f"ensure_minio_bucket: intento {attempt}/{retries} fallo ({exc}); reintentando en {delay_seconds}s")
                time.sleep(delay_seconds)
    raise last_error

def seed_vision_models(db: Session):
    from app.models.camera import Camera
    from app.models.vision import VisionModelVersion, CameraVisionSetting
    now = datetime.now(timezone.utc)
    model = db.scalar(select(VisionModelVersion).where(VisionModelVersion.code == "OPENCV_HOG_PERSON_BASELINE"))
    if not model:
        model = VisionModelVersion(
            code="OPENCV_HOG_PERSON_BASELINE", name="OpenCV HOG Person Baseline", provider="OpenCV",
            backend="opencv_hog", detector_type="PERSON", version="4.13-HOG-SVM-HARDENED-0.4.1",
            license_name="Apache-2.0", license_url="https://opencv.org/about/", commercial_use=True,
            active=True, is_default=True,
            notes="Detector real CPU de línea base endurecido en v0.4.1 con filtros geométricos, NMS y confirmación temporal. Arquitectura reemplazable por ONNX/TensorRT/DeepStream.",
            model_metadata={"classes":["PERSON"],"weights":"OpenCV built-in default people detector","hardening":"0.4.1"}, created_at=now,
        )
        db.add(model); db.flush()
    model.version = "4.13-HOG-SVM-HARDENED-0.4.1"
    model.notes = "Detector real CPU de línea base endurecido en v0.4.1 con filtros geométricos, NMS y confirmación temporal. Arquitectura reemplazable por ONNX/TensorRT/DeepStream."
    metadata = dict(model.model_metadata or {})
    metadata["hardening"] = "0.4.1"
    model.model_metadata = metadata
    cameras = list(db.scalars(select(Camera)))
    for cam in cameras:
        cfg = db.scalar(select(CameraVisionSetting).where(CameraVisionSetting.camera_id == cam.id))
        if not cfg:
            db.add(CameraVisionSetting(organization_id=cam.organization_id,camera_id=cam.id,model_version_id=model.id,enabled=bool(cam.ai_enabled),inference_fps=1.0,min_confidence=0.62,nms_iou_threshold=0.35,tracker_iou_threshold=0.25,tracker_max_missed_frames=4,tracker_min_hits_to_confirm=3,min_box_area_ratio=0.015,max_box_area_ratio=0.18,min_height_ratio=0.18,min_aspect_ratio=0.28,max_aspect_ratio=0.95,top_band_reject_y_ratio=0.15,top_band_reject_bottom_ratio=0.62,created_at=now,updated_at=now))
    # Bloque 4: baseline ML EPP propio, sin pesos de terceros.
    ppe_model = db.scalar(select(VisionModelVersion).where(VisionModelVersion.code == 'PPE_REGION_SVM_BASELINE'))
    if not ppe_model:
        ppe_model = VisionModelVersion(
            code='PPE_REGION_SVM_BASELINE', name='PPE Region SVM Baseline', provider='HYS Vision IA',
            backend='opencv_svm_regions', detector_type='PPE', version='1.0-SYNTHETIC-BASELINE-0.5.0',
            license_name='PROJECT-MIT', license_url=None, commercial_use=True, active=True, is_default=False,
            notes='Baseline ML de puesta en marcha. SVM entrenado con muestras sintéticas generadas dentro del proyecto; requiere validación con dataset/cámaras del cliente antes de producción.',
            model_metadata={'classes':['HELMET','VEST','SAFETY_SHOES'],'training':'project-generated synthetic','association':'anatomical regions bound to confirmed TRACK','production_certified':False}, created_at=now,
        ); db.add(ppe_model); db.flush()
    for cam in cameras:
        cfg = db.scalar(select(CameraVisionSetting).where(CameraVisionSetting.camera_id == cam.id))
        if cfg and not cfg.ppe_model_version_id:
            cfg.ppe_model_version_id = ppe_model.id

    # Bloque 9: bootstrap real y permisivo para casco + chaleco. El artifact se descarga
    # desde Intel Edge AI Resources mediante script separado; si no existe, el modelo se
    # mantiene registrado pero inactivo y el baseline anterior sigue operativo.
    intel = db.scalar(select(VisionModelVersion).where(VisionModelVersion.code == 'INTEL_WORKER_SAFETY_BOOTSTRAP'))
    intel_rel = 'bootstrap/intel-worker-safety/model.xml'
    intel_path = Path(settings.hys_model_root) / intel_rel
    if not intel:
        intel = VisionModelVersion(
            code='INTEL_WORKER_SAFETY_BOOTSTRAP', name='Intel Worker Safety Gear Bootstrap', provider='Intel',
            backend='openvino_ir_ppe', detector_type='PPE', version='FP32-2026',
            license_name='MIT', license_url='https://huggingface.co/Intel/worker-safety-detection', commercial_use=True,
            active=bool(intel_path.exists()), is_default=False,
            notes='Bootstrap real para video: safety_helmet + safety_jacket. Se usa para puesta en marcha y SHADOW; no sustituye el modelo HYS entrenado para SAFETY_SHOES.',
            model_metadata={
                'classes':['HELMET','VEST'], 'input_size':[640,640], 'default_threshold':0.35,
                'helmet_threshold':0.57, 'vest_threshold':0.525,
                'detection_output_label_map':{'1':'HELMET','2':'VEST'},
                'source':'Intel Worker Safety Detection', 'production_certified_for_hys':False,
            },
            artifact_uri=intel_rel, framework='OpenVINO Runtime CPU', model_stage='REGISTERED',
            class_map={'1':'HELMET','2':'VEST'}, created_at=now,
        ); db.add(intel); db.flush()
    else:
        intel.active = bool(intel_path.exists())
        intel.artifact_uri = intel.artifact_uri or intel_rel
        intel.framework = 'OpenVINO Runtime CPU'
        imeta=dict(intel.model_metadata or {}); imeta['input_size']=[640,640]; intel.model_metadata=imeta
        intel.model_stage = intel.model_stage or 'REGISTERED'
    db.commit()



def seed_block10_demo_dataset(db: Session):
    org=db.scalar(select(Organization).where(Organization.code=='DEMO-HYS'))
    if not org: return
    item=db.scalar(select(MLDataset).where(MLDataset.organization_id==org.id,MLDataset.code=='HYS-PPE-REAL'))
    if not item:
        db.add(MLDataset(organization_id=org.id,code='HYS-PPE-REAL',name='Dataset HYS PPE Real',description='Dataset visual propio para frames de cámaras/videos reales.',license_name='PROPRIETARY-HYS',active=True))
        db.commit()

def main():
    with SessionLocal() as db:
        seed_access_control(db)
        seed_ppe_catalog(db)
        seed_admin(db)
        seed_vision_models(db)
        seed_block10_demo_dataset(db)
        from app.services.alerting import seed_alerting_for_existing_organizations
        seed_alerting_for_existing_organizations(db)
    ensure_minio_bucket()
    print("Bootstrap RBAC + MinIO: OK")

if __name__ == "__main__":
    main()

