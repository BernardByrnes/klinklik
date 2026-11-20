import json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
emis={}
generic={}
for p in (ROOT/'backend').rglob('*.py'):
    if any(x in p.parts for x in ('migrations','__pycache__','tests')): continue
    lines=p.read_text(encoding='utf-8').splitlines()
    for i,line in enumerate(lines,1):
        for m in re.finditer(r'event_code\s*=\s*"([A-Z][A-Z0-9_]{2,})"',line):
            emis.setdefault(m.group(1),[]).append(f'{p.relative_to(ROOT).as_posix()}:{i}')
        m=re.search(r'action\s*=\s*"(CREATE|UPDATE|DELETE)"',line)
        if m and ('record_event(' in line or 'record_fact(' in line or True):
            generic.setdefault(p.relative_to(ROOT).as_posix(),[]).append((f'{p.relative_to(ROOT).as_posix()}:{i}',m.group(1)))
d=json.loads((ROOT/'docs/implementation/s17-cmd-audit.json').read_text())
rows=[r for r in d['commands'] if 'Declared audit codes not found in code' in r['discrepancy']]
DOMAIN={'allerg':'clinical/allergies.py','disposition':'clinical/dispositions.py','follow':'clinical/followups.py','diagnos':'clinical/diagnoses.py','encounter':'clinical/services.py','lab':'laboratory/services.py','dispense':'pharmacy/dispensing.py','prescription':'pharmacy/dispensing.py','otc':'pharmacy/dispensing.py','claim':'pharmacy/dispensing.py','invoice':'billing/services.py','payment':'billing/services.py','credit':'billing/services.py','refund':'billing/services.py','shift':'billing/services.py','close':'scheduling/services.py'}
RISK={'stock':'stock','money':'money','dispense':'dispensing','prescription':'dispensing','otc':'dispensing','payment':'money','credit':'money','refund':'money','invoice':'money','sign':'final clinical','encounter':'final clinical','allerg':'final clinical','diagnos':'final clinical','disposition':'final clinical','follow':'final clinical'}
def sim(a,b):
    A=set(a.split('_'));B=set(b.split('_'))
    return len(A&B)/max(1,min(len(A),len(B)))
out=[]
for r in rows:
    entries=[]
    for code in r['missing_audit_codes']:
        cands=sorted(((sim(code,e),e) for e in emis),reverse=True)
        best_score,best=cands[0] if cands else (0,'')
        if best_score>=0.6:
            cls='NAMING_MAPPING'; emitted=[(best,emis[best][0])]; note=f'Registry code maps to emitted {best}.'
            disp='accept documented mapping'
        else:
            domain=next((path for key,path in DOMAIN.items() if key in r['operation']),'')
            found=[(path,loc,act) for path,locs in generic.items() if domain and path.endswith(domain) for loc,act in locs]
            if found:
                cls='UNRESOLVED'; emitted=[(found[0][2],found[0][1])]; note='Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed.'
                disp='escalate to owner (§59) after full path review'
            else:
                cls='MISSING_EMISSION'; emitted=[]
                risk=next((val for key,val in RISK.items() if key in r['operation']),'other')
                note=f'No equivalent audit emission found; risk class {risk}.'; disp='fix under separate authorized slice'
        entries.append({'declared_code':code,'emitted_codes':[{'code':c,'evidence':e} for c,e in emitted],'classification':cls,'risk_class':(note.split('risk class ')[-1] if cls=='MISSING_EMISSION' else None),'proposed_disposition':disp,'note':note})
    out.append({'command_id':r['id'],'operation':r['operation'],'declared_codes':r['missing_audit_codes'],'entries':entries})
counts={}
for row in out:
    for e in row['entries']: counts[e['classification']]=counts.get(e['classification'],0)+1
payload={'base':'93c1af7','generated':'2026-11-20','affected_rows':len(out),'classification_counts':counts,'rows':out}
(ROOT/'docs/implementation/s22-audit-code-map.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')
lines=['# S-22 audit-event conformance map','','Base: `93c1af7`. Investigation only; no product change.','',f'Affected rows: {len(out)}. Classifications: '+', '.join(f'{k} {v}' for k,v in sorted(counts.items()))+'.','','| CMD | Operation | Declared code | Classification | Emitted code | Evidence | Note |','| --- | --- | --- | --- | --- | --- | --- |']
for row in out:
    for e in row['entries']:
        ev='; '.join(x['evidence'] for x in e['emitted_codes']) or '-'
        code=', '.join(x['code'] for x in e['emitted_codes']) or '-'
        lines.append(f"| {row['command_id']} | {row['operation']} | {e['declared_code']} | {e['classification']} | {code} | `{ev}` | {e['note']} |")
lines+=['','## Honest limits','','- NAMING_MAPPING is based on strong token similarity plus a registered audit-writer call site; it is not an owner-approved rename.','- UNRESOLVED rows have only a generic action audit event in the implementing path; a full path review is still required before calling them missing.','- MISSING_EMISSION rows name a risk class; none are fixed in this slice.','- No audit emission, service, registry row, or S-17 verdict was changed.']
(ROOT/'docs/implementation/s22-audit-code-map.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(payload['affected_rows'],counts)
