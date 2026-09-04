import argparse
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.access import User
from app.models.organization import Organization
from app.services.pilot_cleanup import cleanup_pilot

def main():
 p=argparse.ArgumentParser();p.add_argument('--organization-code',default='DEMO-HYS');p.add_argument('--actor-email',default='admin@hysvision.app');p.add_argument('--reason',default='Limpieza controlada QA antes de Bloque 8');a=p.parse_args()
 with SessionLocal() as db:
  org=db.scalar(select(Organization).where(Organization.code==a.organization_code));
  if not org: raise SystemExit(f'Organización {a.organization_code} inexistente')
  actor=db.scalar(select(User).where(User.email==a.actor_email.lower()))
  r=cleanup_pilot(db,org,actor,a.reason)
  print(f'PILOT_CLEANUP_OK run={r.id} archived={r.archived_events} closed={r.closed_technical_events} resolved={r.resolved_operational_events} compliance_disabled={r.disabled_compliance_cameras} sla_restored={r.restored_sla_policies} evidence_preserved={r.preserved_evidence} actions_preserved={r.preserved_actions}')
if __name__=='__main__':main()
