"""Compare final project files with the verified pre-edit inventory."""
from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).resolve().parents[1]
SKIP={'.git','.venv','__pycache__','.pytest_cache','tmp'}
def main():
    original={x['path'].replace('\\','/'):x for x in json.loads((R/'docs/initial_inventory.json').read_text())}
    candidates=set(subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=R).decode('utf-8').split('\0'))
    current={name:R/name for name in candidates if name and (R/name).is_file() and not (set(Path(name).parts)&SKIP) and Path(name).name!='FINAL_GIT_STATE.txt'}
    final_paths=set(current)|{'docs/file_changes.json','docs/FINAL_TREE.txt'}
    manifest={
        'basis':'Verified initial inventory, including pre-existing uncommitted/untracked user work',
        'added':sorted(final_paths-set(original)),
        'modified':sorted(k for k in set(current)&set(original) if hashlib.sha256(current[k].read_bytes()).hexdigest()!=original[k]['sha256']),
        'absent_from_original_location':sorted(set(original)-set(current)),
        'disposition_reference':'docs/CLEANUP_AUDIT.md; most absent paths are preserved moves to archive or the canonical Orange folder',
    }
    (R/'docs/file_changes.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    tree='Healthcare-Intelligence-Platform/\n'+'\n'.join('  '+k for k in sorted(final_paths) if not k.startswith('archive/'))+'\n  archive/ [local historical recovery copies, ignored by Git]\n'
    (R/'docs/FINAL_TREE.txt').write_text(tree,encoding='utf-8')
    print({k:len(manifest[k]) for k in ['added','modified','absent_from_original_location']})
if __name__=='__main__': main()
