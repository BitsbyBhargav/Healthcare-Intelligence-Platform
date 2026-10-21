"""Audit publication candidates without exposing potential credential values.

Run before git add, and again after staging. The report covers common patterns,
not every possible secret format. Local ignored runtime files are excluded.
"""
from pathlib import Path
import base64,hashlib,ipaddress,json,re,subprocess,zipfile
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'github_token':rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
    'openai_key':rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}',
    'aws_access_key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'credential_assignment':rb'(?i)(?:api[_-]?key|client[_-]?secret|password|access[_-]?token)\s*[:=]\s*[\x22\x27][^\x22\x27\r\n]{8,}[\x22\x27]',
}
REQUIRED=[
    'README.md','requirements-lock.txt','requirements.txt','requirements-dev.txt',
    'jury_1_dw/etl_and_olap.py','jury_1_dw/sql.py','jury_1_dw/dashboard.py',
    'data/diabetes_130_us.csv','data/healthcare_dw.db',
    'jury_2_dw/app.py','jury_2_dw/benchmark_models.py','jury_2_dw/jury2_features.py',
    'jury_2_dw/mine_associations.py','jury_2_dw/clinical_profiling.py',
    'jury_2_dw/outputs/best_model.joblib','jury_2_dw/outputs/best_model_report.json',
    'jury_2_dw/orange_demo/jury2_classification.ows','jury_2_dw/orange_demo/jury2_association.ows',
    'jury_2_dw/orange_demo/orange_classification.tab','jury_2_dw/orange_demo/orange_associations.tab',
    'tests/test_platform.py','tests/verify_orange.py','tests/browser_evidence.py',
    'docs/TECHNICAL_HANDOVER.md','docs/JURY_VIVA_PREPARATION.md','docs/VALIDATION.md',
    'deliverables/Jury2_Three_Dashboard_Evidence.pdf',
    'deliverables/Jury2_Healthcare_Intelligence_Implementation_Report.pdf',
]
IGNORE_PROBES=['.env','.env.local','.streamlit/secrets.toml','credentials.prod.json',
               '.venv/example','venv/example','__pycache__/example.pyc',
               '.pytest_cache/example','tmp/example.tmp','archive/old-model.pkl',
               'jury_2_dw/outputs/experimental.joblib','deliverables/logs/streamlit.log']

def scan(name,data,findings):
    for kind,pattern in PATTERNS.items():
        for m in re.finditer(pattern,data):
            findings.append({'file':name,'line':data[:m.start()].count(b'\n')+1,'kind':kind})
    for m in re.finditer(rb'\b(?:\d{1,3}\.){3}\d{1,3}\b',data):
        try:address=ipaddress.ip_address(m.group().decode())
        except ValueError:continue
        if not address.is_loopback and not address.is_unspecified:
            findings.append({'file':name,'line':data[:m.start()].count(b'\n')+1,'kind':'non_loopback_ipv4'})

def main():
    names=set(subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0'))
    names=sorted(name for name in names if name and (ROOT/name).is_file())
    findings=[];sizes=[];suspect=[];documents=0
    for name in names:
        path=ROOT/name;data=path.read_bytes()
        sizes.append({'file':name,'bytes':len(data),'MiB':round(len(data)/1024**2,2)})
        if re.search(r'(?i)(^|/)(\.env(?:\..*)?|id_rsa|id_ed25519|credentials(?:\..*)?|.*\.(?:pem|p12|pfx|key))$',name) and not name.endswith(('.example','.sample')):
            suspect.append(name)
        if path.suffix=='.pdf':
            scan(name,('\n'.join(page.extract_text() or '' for page in PdfReader(path).pages)).encode(),findings)
            documents+=1
        elif path.suffix=='.pbix' and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                for member in z.infolist():
                    if member.file_size<=5*1024**2 and ('connection' in member.filename.lower() or member.filename.lower().endswith(('.json','.xml')) or member.filename in ['Metadata','Report/Layout']):
                        blob=z.read(member)
                        if b'\0' not in blob[:8192]:scan(name+'!'+member.filename,blob,findings)
        elif b'\0' not in data[:8192]:
            scan(name,data,findings)
            if path.suffix=='.ows':
                from xml.etree import ElementTree as ET
                for prop in ET.fromstring(data).findall('./node_properties/properties'):
                    if prop.attrib.get('format')=='pickle':scan(name+'!settings',base64.b64decode(prop.text),findings)
    ignored={name:subprocess.run(['git','check-ignore','--no-index','-q',name],cwd=ROOT).returncode==0 for name in IGNORE_PROBES}
    required_missing=[name for name in REQUIRED if name not in names]
    large=[item for item in sizes if item['bytes']>100*1024**2]
    source=ROOT/'data/diabetes_130_us.csv'
    assert hashlib.sha256(source.read_bytes()).hexdigest()=='cbe830d669653c59c6ccb66c98b3c6f8084ff38da94e7c6a1660b2609ac98964'
    for item in json.loads((ROOT/'deliverables/logs/pdf_validation.json').read_text()):
        assert hashlib.sha256((ROOT/'deliverables'/item['file']).read_bytes()).hexdigest()==item['sha256']
    report={'candidate_files':len(names),'credential_or_network_findings':findings,'suspect_file_names':suspect,
            'missing_required_assets':required_missing,'ignore_probes':ignored,'over_100_MiB':large,
            'over_50_MiB':[item for item in sizes if item['bytes']>50*1024**2],
            'largest_files':sorted(sizes,key=lambda x:x['bytes'],reverse=True)[:8],
            'pdf_documents_scanned':documents,'source_and_pdf_hashes_verified':True,
            'scope':'Working publication candidates: text, PDF extracted text, readable BI metadata and decoded workflow settings. Pattern scan, not a guarantee of all possible secret formats.'}
    assert not findings and not suspect and not required_missing and not large,report
    assert all(ignored.values()),ignored
    (ROOT/'deliverables/logs/prepublish_audit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['scope','ignore_probes','largest_files']},indent=2))
if __name__=='__main__':main()
