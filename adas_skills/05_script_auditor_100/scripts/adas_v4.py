#!/usr/bin/env python3
"""ADAS V4.0 deterministic validation/controller CLI; stdlib except optional Pillow rendering.

Mechanical gates do not establish narrative quality, originality or visual accuracy.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

V = '4.0.0'
PARTS = ('A','B','C')
PART_RANGES = {'A':(13334,16000),'B':(13334,17000),'C':(13334,17000)}
TOTAL_RANGE = (40001,50000)
RUBRIC = {'A':8,'B':18,'C':10,'D':10,'E':10,'F':8,'G':10,'H':8,'I':7,'J':5,'K':3,'L':3}
REQUIRED_GATES = {'B':16,'C':8,'D':8,'E':8,'I':5}
FATAL_CAPS = {'fatal_causal_contradiction':69,'knowledge_without_path':69,'title_promise_unpaid':74,
 'fatal_timeline_impossibility':79,'unseeded_deus_ex_machina':79,
 'impossible_essential_authority':74,'narrator_objective_contradiction':69}
METADATA_RULES = [
 ('META_TITLE',r'^\s*(?:\[)?(?:LOCKED_TITLE|SELECTED_TITLE|WINNING_TITLE|FINAL_TITLE|DRAFT_TITLE|TITLE_PROMISE)\s*(?:\])?\s*[:：=]'),
 ('META_PART',r'^\s*(?:P\d+\s*[—–-]\s*)?(?:STEP\s*[2-7]|BUILD\s+PART\s*[ABC]|PART\s*[ABC]\s*[—–:-]\s*(?:日本語|SCRIPT|ナレーション))'),
 ('META_CONTROL',r'^\s*(?:CONTINUITY|HANDOFF(?:_LEDGER)?|ENDING|NEXT_ACTION|PURE_CHARACTER_COUNT|PART_PURE_CHARACTER_COUNT|READY_FOR_AUDIT|TOTAL_LENGTH_GATE|PART_LENGTH_GATE|PATCH_CHANGELOG|LOCK_MANIFEST|SCENE_PLAN)\s*[:：=]'),
 ('META_WRAPPER',r'^\s*(?:</?(?:CodeBlock|WritingBlock|text|box)\b|```|<\/?)'),
]

def now(): return datetime.now(timezone.utc).isoformat()
def sha_bytes(data:bytes): return hashlib.sha256(data).hexdigest()
def sha_path(p): return sha_bytes(Path(p).read_bytes())
def read_utf8(p): return Path(p).read_text(encoding='utf-8',errors='strict')
def save_json(p, data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');tmp.replace(p)
def load_json(p): return json.loads(read_utf8(p))
def pure_count(text): return sum(unicodedata.category(c)[0] in ('L','N') for c in unicodedata.normalize('NFC',text))
def err(code,**kwargs): return {'code':code,**kwargs}
def result(errors,**data): return {'version':V,'status':'PASS' if not errors else 'FAIL','errors':errors,**data}
def output(data): print(json.dumps(data,ensure_ascii=False,indent=2));return 0 if data.get('status')=='PASS' else 2

def script_issues(text, strict=True):
 out=[]
 for n,line in enumerate(text.splitlines(),1):
  for key,pattern in METADATA_RULES:
   if re.search(pattern,line,re.I): out.append(err(key,line=n,excerpt=line[:110]));break
 if '\ufffd' in text: out.append(err('REPLACEMENT_CHAR'))
 if '\x00' in text: out.append(err('NUL_BYTE'))
 if strict and not text.strip(): out.append(err('EMPTY_SCRIPT'))
 return out

def part_check(files):
 errors=[];counts={};digests={}
 for part in PARTS:
  p=Path(files[part]);
  try: txt=read_utf8(p)
  except (UnicodeError,OSError) as ex:
   errors.append(err('READ_FAILED',part=part,reason=str(ex)));counts[part]=None;continue
  c=pure_count(txt);counts[part]=c;digests[part]=sha_path(p)
  lo,hi=PART_RANGES[part]
  if not lo<=c<=hi:errors.append(err('PART_LENGTH_FAIL',part=part,count=c,minimum=lo,maximum=hi))
  errors.extend([{**e,'part':part} for e in script_issues(txt)])
 if all(isinstance(x,int) for x in counts.values()):
  total=sum(counts.values())
  if not TOTAL_RANGE[0]<=total<=TOTAL_RANGE[1]:errors.append(err('TOTAL_LENGTH_FAIL',count=total))
 else:total=None
 return result(errors,counts=counts,total=total,sha256=digests,ready_for_audit=not errors)

def cmd_count(a):
 try: txt=read_utf8(a.file)
 except (OSError,UnicodeError) as ex:return output(result([err('READ_FAILED',reason=str(ex))]))
 c=pure_count(txt);scope=a.part.upper() if a.part else 'TOTAL'; lo,hi=PART_RANGES.get(scope,TOTAL_RANGE)
 errors=[]
 if not lo<=c<=hi:errors.append(err('LENGTH_FAIL',count=c,minimum=lo,maximum=hi))
 errors.extend(script_issues(txt))
 return output(result(errors,count=c,scope=scope,sha256=sha_path(a.file)))
def cmd_parts(a): return output(part_check(dict(zip(PARTS,(a.a,a.b,a.c)))))

def clean_script(txt):
 """Conservative writer-side extraction: strip only whole-line metadata, flag for inspection."""
 removed=[];lines=[]
 for n,line in enumerate(txt.splitlines(keepends=True),1):
  matches=[key for key,patt in METADATA_RULES if re.search(patt,line,re.I)]
  if matches:removed.append({'line':n,'rule':matches[0],'excerpt':line.rstrip()[:160]})
  else:lines.append(line)
 return ''.join(lines),removed

def cmd_clean(a):
 try:before=read_utf8(a.source)
 except (OSError,UnicodeError) as ex:return output(result([err('READ_FAILED',reason=str(ex))]))
 after,removed=clean_script(before)
 if not a.dest or Path(a.dest).resolve()==Path(a.source).resolve():return output(result([err('DEST_REQUIRED_DIFFERENT_SOURCE')]))
 Path(a.dest).write_text(after,encoding='utf-8')
 report={'source':str(a.source),'output':str(a.dest),'removed':removed,
 'clean_pure_chars':pure_count(after),'manual_review_required':bool(removed),
 'warning':'If a multiline leaked title exists, inspect adjacent narration manually; extraction is not a semantic sanitizer.'}
 save_json(str(a.dest)+'.clean_report.json',report)
 return output(result(script_issues(after),**report))

FINGERPRINT_KEYS=('relation','setting','trigger','evidence','mechanism','reveal','payoff','consequence')
def norm(s):return re.sub(r'[\s\W_]+','',unicodedata.normalize('NFKC',str(s)).lower(),flags=re.UNICODE)
def grams(s,n=3):
 s=norm(s)
 return {s[i:i+n] for i in range(len(s)-n+1)} if len(s)>=n else ({s} if s else set())
def sim(a,b):
 x=grams(a);y=grams(b)
 return round(len(x&y)/len(x|y),3) if x and y else 0.0

def cmd_originality(a):
 item=load_json(a.idea);errors=[]
 for k in ('title','title_promise','premise','fingerprint','primary_dna','hook_dna','longform_capacity'):
  if not item.get(k):errors.append(err('IDEA_REQUIRED',field=k))
 if item.get('longform_capacity')!='PASS':errors.append(err('LONGFORM_CAPACITY_NOT_PASS'))
 fp=item.get('fingerprint',{})
 for k in ('mechanism','payoff','evidence','relation','setting','trigger'):
  if not fp.get(k):errors.append(err('FINGERPRINT_REQUIRED',field=k))
 library=[]
 for fname in a.history or []:
  try:raw=load_json(fname)
  except (OSError,ValueError) as ex:errors.append(err('HISTORY_READ_FAILED',file=fname,reason=str(ex)));continue
  library.extend(raw if isinstance(raw,list) else raw.get('items',[]))
 hits=[]
 for old in library:
  oldfp=old.get('fingerprint',{})
  matches=[k for k in FINGERPRINT_KEYS if norm(fp.get(k,'')) and norm(fp.get(k,''))==norm(oldfp.get(k,''))]
  title_sim=sim(item.get('title',''),old.get('title',''))
  same_core='mechanism' in matches and 'payoff' in matches
  level='RED' if same_core or title_sim>=0.73 else ('YELLOW' if len(matches)>=3 or title_sim>=0.42 else 'GREEN')
  hits.append({'id':old.get('project_id') or old.get('id') or old.get('ref','unknown'),
   'risk':level,'matching_fields':matches,'title_3gram_similarity':title_sim,'core_reuse':same_core})
 hits.sort(key=lambda x:({'RED':2,'YELLOW':1,'GREEN':0}[x['risk']],x['title_3gram_similarity']),reverse=True)
 if hits and hits[0]['risk']=='RED':errors.append(err('ORIGINALITY_RED',comparison=hits[0]['id']))
 if any(x['risk']=='YELLOW' for x in hits):errors.append(err('ORIGINALITY_YELLOW_MANUAL_REVIEW'))
 return output(result(errors,checks=len(hits),top_matches=hits[:12],note='Heuristic comparison only. Reference titles alone cannot establish semantic originality.'))

SCENE_FIELDS=('id','part','purpose','new_info','action','conflict','state_change','evidence','knowledge_transfer','target_chars')
REQUIRED_BLUEPRINT=('locked_title','title_promise','central_question','narrative_spine','primary_dna','secondary_dna','hook_dna','emotional_arc','reversal_mechanism','proof_chain','characters','timeline','setup_payoff','reveals','scenes','part_contracts')
def blueprint_check(obj):
 e=[]
 if obj.get('template_only'):e.append(err('BLUEPRINT_TEMPLATE_NOT_FILLED'))
 for key in REQUIRED_BLUEPRINT:
  if not obj.get(key):e.append(err('BLUEPRINT_MISSING',field=key))
 scenes=obj.get('scenes',[])
 if not isinstance(scenes,list):scenes=[];e.append(err('SCENES_INVALID'))
 if not 20<=len(scenes)<=24:e.append(err('SCENE_COUNT',count=len(scenes),allowed='20..24'))
 ids=set();part_totals=dict.fromkeys(PARTS,0);part_scenes=dict.fromkeys(PARTS,0)
 for ix,s in enumerate(scenes):
  if not isinstance(s,dict):e.append(err('SCENE_INVALID',index=ix));continue
  sid=s.get('id')
  if sid in ids or not sid:e.append(err('SCENE_ID_DUPLICATE_OR_EMPTY',index=ix))
  ids.add(sid)
  for k in SCENE_FIELDS:
   if s.get(k) is None or s.get(k)=='':e.append(err('SCENE_FIELD_MISSING',scene=sid,field=k))
  part=s.get('part');target=s.get('target_chars')
  if part not in PARTS:e.append(err('SCENE_PART_INVALID',scene=sid));continue
  part_scenes[part]+=1
  if not isinstance(target,int) or target<=0:e.append(err('SCENE_BUDGET_INVALID',scene=sid));continue
  part_totals[part]+=target
  if s.get('state_change') in ('none','NONE','なし','không','no'):e.append(err('SCENE_NO_STATE_CHANGE',scene=sid))
 for p in PARTS:
  lo,hi=PART_RANGES[p]
  if not lo<=part_totals[p]<=hi:e.append(err('BLUEPRINT_PART_BUDGET',part=p,count=part_totals[p]))
  if not 6<=part_scenes[p]<=9:e.append(err('BLUEPRINT_PART_SCENES',part=p,count=part_scenes[p]))
 total=sum(part_totals.values())
 if not TOTAL_RANGE[0]<=total<=TOTAL_RANGE[1]:e.append(err('BLUEPRINT_TOTAL_BUDGET',count=total))
 contracts=obj.get('part_contracts',{})
 for p in PARTS:
  ct=contracts.get(p,{})
  for f in ('entry_state','exit_state','open_loops','next_scene'):
   if f not in ct:e.append(err('PART_CONTRACT_MISSING',part=p,field=f))
  if p=='C' and not ct.get('title_promise_payoff_id'):e.append(err('TITLE_PAYOFF_ID_MISSING'))
 proofs=obj.get('proof_chain',[])
 for proof in proofs if isinstance(proofs,list) else []:
  for f in ('id','created_by','stored_at','accessed_by','access_path','first_seen_scene'):
   if not proof.get(f):e.append(err('PROOF_PROVENANCE_MISSING',proof=proof.get('id'),field=f))
 reveals=obj.get('reveals',[])
 if not isinstance(reveals,list) or len(reveals)<3:e.append(err('REVEALS_BELOW_THREE'))
 else:
  for r in reveals:
   if len(r.get('seed_ids',[]))<2:e.append(err('REVEAL_UNSEEDED',reveal=r.get('id')))
 setups={x.get('id') for x in obj.get('setup_payoff',[]) if isinstance(x,dict)}
 for r in reveals if isinstance(reveals,list) else []:
  for sid in r.get('seed_ids',[]):
   if sid not in setups:e.append(err('REVEAL_SEED_UNDEFINED',reveal=r.get('id'),seed=sid))
 return result(e,scene_count=len(scenes),part_scenes=part_scenes,planned_counts=part_totals,planned_total=total,
  note='Mechanical blueprint validation; timeline, character knowledge, motive and legal realism require human/AI semantic audit.')
def cmd_blueprint(a):return output(blueprint_check(load_json(a.file)))

def audit_check(audit, parts_report=None, lock_title=None):
 e=[]
 if audit.get('template_only'):e.append(err('AUDIT_TEMPLATE_NOT_FILLED'))
 if not isinstance(audit.get('p0_count'),int) or isinstance(audit.get('p0_count'),bool) or audit.get('p0_count',0)<0:e.append(err('P0_COUNT_INVALID'))
 scores=audit.get('scores',{})
 for key,maxscore in RUBRIC.items():
  v=scores.get(key)
  if not isinstance(v,int) or isinstance(v,bool) or not 0<=v<=maxscore:
   e.append(err('SCORE_INVALID',category=key,max=maxscore))
 total=sum(v for key,v in scores.items() if key in RUBRIC and isinstance(v,int) and not isinstance(v,bool))
 if set(scores)!=set(RUBRIC):e.append(err('RUBRIC_CATEGORIES_INVALID'))
 if audit.get('total_score')!=total:e.append(err('SCORE_SUM_MISMATCH',calculated=total,reported=audit.get('total_score')))
 flags=audit.get('fatal_flags',[])
 for f in flags:
  if f not in FATAL_CAPS:e.append(err('UNKNOWN_FATAL_FLAG',flag=f))
 cap=min((FATAL_CAPS[f] for f in flags if f in FATAL_CAPS),default=100)
 if total>cap and flags:e.append(err('FATAL_SCORE_CAP_VIOLATED',score=total,cap=cap))
 if lock_title is not None and audit.get('locked_title')!=lock_title:e.append(err('TITLE_LOCK_MISMATCH'))
 parts=audit.get('part_status',{})
 for p in PARTS:
  if parts.get(p) not in ('PASS_LOCKED','PATCH_REQUIRED','REPLAN_REQUIRED'):
   e.append(err('PART_STATUS_INVALID',part=p))
  cov=audit.get('coverage',{}).get(p,{})
  if cov.get('reviewed_full') is not True or not cov.get('evidence_notes'):
   e.append(err('COVERAGE_ATTESTATION_MISSING',part=p))
  if parts_report and cov.get('source_sha256')!=parts_report['sha256'].get(p):
   e.append(err('AUDIT_SOURCE_STALE',part=p))
 if parts_report and parts_report['status']!='PASS':e.append(err('AUDIT_NOT_STARTED_MECHANICAL_GATE'))
 tickets=audit.get('tickets',[])
 if any(parts.get(p)!='PASS_LOCKED' for p in PARTS) and not tickets:
  e.append(err('REPAIR_TICKETS_REQUIRED'))
 for t in tickets:
  for f in ('id','part','priority','location','root_cause','allowed_scope','acceptance'):
   if not t.get(f):e.append(err('TICKET_FIELD_REQUIRED',ticket=t.get('id'),field=f))
  if t.get('part') not in PARTS:e.append(err('TICKET_PART_INVALID',ticket=t.get('id')))
  if t.get('priority') not in ('P0','P1','P2'):e.append(err('TICKET_PRIORITY_INVALID',ticket=t.get('id')))
  if not isinstance(t.get('allowed_scope'),dict) or not isinstance(t.get('allowed_scope',{}).get('start_line'),int) or not isinstance(t.get('allowed_scope',{}).get('end_line'),int):
   e.append(err('TICKET_SCOPE_INVALID',ticket=t.get('id')))
 if audit.get('mode') not in ('BASELINE','VERIFY'):e.append(err('AUDIT_MODE_INVALID'))
 if not audit.get('logical_audit') or not audit.get('holistic_audit'):
  e.append(err('TWO_PASS_AUDIT_DOCUMENTATION_MISSING'))
 if any(x.get('priority')=='P0' for x in tickets) and audit.get('p0_count',0)==0:
  e.append(err('P0_COUNT_INCONSISTENT'))
 publish=total>=95 and not flags and audit.get('p0_count')==0 and all(
  isinstance(scores.get(k),int) and scores[k]>=v for k,v in REQUIRED_GATES.items()) and all(parts.get(p)=='PASS_LOCKED' for p in PARTS) and not tickets and not e
 if not publish:
  e.append(err('PUBLISH_HARD_GATE_NOT_MET',minimum=95,score=total))
 return result(e,total_score=total,hard_cap=cap,publish_ready=publish,
  note='Scores, coverage and findings remain reviewer assertions, not independently proven by this validator.')

def cmd_audit(a):
 try:report=part_check(dict(zip(PARTS,(a.a,a.b,a.c)))) if a.a and a.b and a.c else None
 except Exception as ex:return output(result([err('PART_INPUT_ERROR',reason=str(ex))]))
 return output(audit_check(load_json(a.audit),report,a.title))

def check_patch(original, candidate, tickets,part,cycle=1,locked_hash=None):
 errors=[]
 if cycle>3 or cycle<1:errors.append(err('REPAIR_CYCLE_LIMIT',cycle=cycle))
 raw0=Path(original).read_bytes();raw1=Path(candidate).read_bytes()
 if locked_hash and sha_bytes(raw0)!=locked_hash:errors.append(err('BASELINE_LOCK_HASH_MISMATCH'))
 try:old=raw0.decode('utf-8');new=raw1.decode('utf-8')
 except UnicodeError: return result(errors+[err('PATCH_UTF8_INVALID')])
 ranges=[]
 for t in tickets:
  if t.get('part')!=part:continue
  span=t.get('allowed_scope',{})
  x,y=span.get('start_line'),span.get('end_line')
  if not isinstance(x,int) or not isinstance(y,int) or x<1 or y<x:
   errors.append(err('PATCH_SCOPE_INVALID',ticket=t.get('id')))
  else:ranges.append((x-1,y,t.get('id')))
 if not ranges:errors.append(err('NO_SCOPED_TICKET_FOR_PART',part=part))
 origlines=old.splitlines(keepends=True);newlines=new.splitlines(keepends=True)
 edits=[]
 if len(origlines)==len(newlines):
  # Position-locked line replacements: unambiguous even when many Japanese lines are identical.
  changes=[('replace',i,i+1,i,i+1) for i,(x,y) in enumerate(zip(origlines,newlines)) if x!=y]
 else:
  changes=[(tag,i1,i2,j1,j2) for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(a=origlines,b=newlines,autojunk=False).get_opcodes() if tag!='equal']
 for tag,i1,i2,j1,j2 in changes:
  # insert at index i1 can only touch boundary inside a permit; replacement/deletion must be entirely inside one.
  authorized=any((lo<=i1 and i2<=hi) if tag!='insert' else (lo<=i1<=hi) for lo,hi,_ in ranges)
  edits.append({'operation':tag,'source_lines':[i1+1,i2],'candidate_lines':[j1+1,j2],'allowed':authorized})
  if not authorized:errors.append(err('PATCH_OUTSIDE_SCOPE',operation=tag,source_start=i1+1,source_end=i2))
 errors.extend(script_issues(new))
 c=pure_count(new);lo,hi=PART_RANGES[part]
 if not lo<=c<=hi:errors.append(err('PATCH_PART_LENGTH_FAIL',part=part,count=c))
 return result(errors,part=part,cycle=cycle,source_sha256=sha_bytes(raw0),candidate_sha256=sha_bytes(raw1),
  before_count=pure_count(old),after_count=c,edits=edits,locked_other_parts='NOT_CHECKED; provide hashes with full gate')
def cmd_patch(a):
 tickets=load_json(a.tickets)
 if isinstance(tickets,dict):tickets=tickets.get('tickets',[])
 return output(check_patch(a.before,a.after,tickets,a.part.upper(),a.cycle,a.original_sha))

COLORS={'L1':'yellow','L2':'white','L3':'magenta','L4':'yellow','L5':'cyan'}
def thumb_check(spec,imagefile=None):
 e=[]
 if spec.get('template_only'):e.append(err('THUMB_TEMPLATE_NOT_FILLED'))
 for k,color in COLORS.items():
  row=spec.get(k,{})
  if not isinstance(row,dict) or not str(row.get('text','')).strip():e.append(err('THUMB_ROW_MISSING',line=k));continue
  if row.get('color')!=color:e.append(err('THUMB_COLOR_INVALID',line=k,expected=color))
  if '\n' in row.get('text','') or '\r' in row.get('text',''):e.append(err('THUMB_MULTILINE',line=k))
 l6=spec.get('L6',{});spans=l6.get('spans',[]) if isinstance(l6,dict) else []
 if len(spans)!=2 or any(not s.get('text','').strip() for s in spans):e.append(err('THUMB_L6_TWO_SPANS_REQUIRED'))
 elif [s.get('color') for s in spans]!=['cyan','magenta']:e.append(err('THUMB_L6_COLORS_INVALID'))
 if len(spans)==2 and any('\n' in s['text'] or '\r' in s['text'] for s in spans):e.append(err('THUMB_L6_WRAPS'))
 if isinstance(l6,dict) and l6.get('same_baseline') is not True:e.append(err('THUMB_L6_BASELINE_UNCONFIRMED'))
 actual_keys=[k for k in spec if re.fullmatch(r'L\d+',str(k))]
 if sorted(actual_keys)!=['L1','L2','L3','L4','L5','L6']:e.append(err('THUMB_LINE_KEYS_INVALID',keys=actual_keys))
 if spec.get('title')!=spec.get('locked_title') or not spec.get('locked_title'):e.append(err('THUMB_TITLE_LOCK_MISMATCH'))
 if not 0.35<=spec.get('right_face_fraction',0)<=0.40:e.append(err('THUMB_FACE_FRACTION_INVALID'))
 info=None
 if imagefile:
  try:
   from PIL import Image
   with Image.open(imagefile) as im:
    w,h=im.size;info={'width':w,'height':h}
    if w*9!=h*16:e.append(err('THUMB_NOT_16_9',width=w,height=h))
    if w<1280 or h<720:e.append(err('THUMB_RESOLUTION_LOW',width=w,height=h))
  except Exception as ex:e.append(err('THUMB_IMAGE_READ_FAILED',reason=str(ex)))
  visual=spec.get('visual_qa',{})
  for k in ('detected_lines','l6_same_baseline','no_extra_text','face_position_verified','text_readability_confirmed'):
   if k not in visual:e.append(err('VISUAL_QA_MISSING',field=k))
  if visual.get('detected_lines')!=6 or visual.get('l6_same_baseline') is not True or visual.get('no_extra_text') is not True or visual.get('face_position_verified') is not True or visual.get('text_readability_confirmed') is not True:
   e.append(err('VISUAL_QA_FAILED_OR_PENDING'))
 return result(e,image=info,review_note='Image text count and face occupancy require visual or layer review; image dimensions alone are not sufficient.')

def cmd_thumbnail(a):return output(thumb_check(load_json(a.spec),a.image))

def resolve_font(path):
 if path and Path(path).is_file():return path
 for p in ('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc','/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc','C:/Windows/Fonts/meiryob.ttc','C:/Windows/Fonts/YuGothB.ttc','C:/Windows/Fonts/BIZ-UDGothicB.ttc','C:/Windows/Fonts/msgothic.ttc'):
  if Path(p).is_file():return p
 raise FileNotFoundError('Japanese font not found. Provide --font path to a locally installed Japanese bold TTF/TTC. No font is bundled.')

def render_thumb(spec,background,out,fontpath=None):
 from PIL import Image, ImageDraw, ImageFont
 e=thumb_check(spec)['errors']
 if e:raise ValueError('Invalid thumbnail specification: '+json.dumps(e,ensure_ascii=False))
 fontpath=resolve_font(fontpath)
 with Image.open(background) as bg:im=bg.convert('RGB')
 w,h=1280,720
 # center crop to final 16:9 without stretching
 bw,bh=im.size;scale=max(w/bw,h/bh);nw,nh=round(bw*scale),round(bh*scale)
 im=im.resize((nw,nh),Image.Resampling.LANCZOS).crop(((nw-w)//2,(nh-h)//2,(nw+w)//2,(nh+h)//2)).convert('RGBA')
 veil=Image.new('RGBA',(w,h),(0,0,0,0));d=ImageDraw.Draw(veil)
 for x in range(round(w*0.79)):
  alpha=round(185*(1-x/(w*.84))**1.5)
  d.line((x,0,x,h),fill=(7,9,14,max(0,alpha)))
 im=Image.alpha_composite(im,veil);d=ImageDraw.Draw(im)
 palette={'yellow':'#FFE457','white':'#FFFFFF','magenta':'#FF56B9','cyan':'#57F5FF'}
 texts=[[(spec[f'L{i}']['text'],spec[f'L{i}']['color'])] for i in range(1,6)] + [[(s['text'],s['color']) for s in spec['L6']['spans']]]
 heights=[87,87,87,87,87,120];y=24
 placed=[]
 for idx,runs in enumerate(texts):
  max_width=1085 if idx==5 else 960
  base_font=65 if idx==5 else 54
  size=base_font
  while size>=18:
   font=ImageFont.truetype(fontpath,size)
   widths=[d.textbbox((0,0),tx,font=font,stroke_width=4)[2] for tx,_ in runs]
   if sum(widths)+10*(len(runs)-1)<=max_width:break
   size-=1
  if size<18:raise ValueError(f'Thumbnail line {idx+1} too long for single-line fit; shorten Japanese copy')
  line_w=sum(widths)+10*(len(runs)-1)
  xx=29 if idx!=5 else 35
  baseline_y=y+(heights[idx]-size)//3
  for (tx,color),ww in zip(runs,widths):
   d.text((xx+3,baseline_y+4),tx,font=font,fill='#000000',stroke_width=7,stroke_fill='#000000')
   d.text((xx,baseline_y),tx,font=font,fill=palette[color],stroke_width=4,stroke_fill='#0A0A0A')
   xx+=ww+10
  placed.append({'line':f'L{idx+1}','font_size':size,'x':35 if idx==5 else 29,'y':baseline_y,'width_px':line_w,'same_baseline':True})
  y+=heights[idx]+5
 Path(out).parent.mkdir(parents=True,exist_ok=True);im.convert('RGB').save(out,quality=94)
 return result([],file=str(out),dimensions=[w,h],lines_rendered=placed,guarantee='Only six overlay text rows from supplied spec; background may contain other text and must be checked separately.')
def cmd_render(a):
 try:return output(render_thumb(load_json(a.spec),a.background,a.out,a.font))
 except Exception as ex:return output(result([err('THUMB_RENDER_FAILED',reason=str(ex))]))

STATES=('CREATED','TITLE_LOCKED','OUTLINE_APPROVED','A_READY','B_READY','C_READY','AUDIT_IN_PROGRESS','PUBLISH_READY','EXPORTED')
STATE_NEXT={'CREATED':['TITLE_LOCKED'],'TITLE_LOCKED':['OUTLINE_APPROVED'],
 'OUTLINE_APPROVED':['A_READY'],'A_READY':['B_READY'],'B_READY':['C_READY'],
 'C_READY':['AUDIT_IN_PROGRESS'],'AUDIT_IN_PROGRESS':['PUBLISH_READY'],
 'PUBLISH_READY':['EXPORTED']}

def cmd_init(a):
 path=Path(a.dir);statefile=path/'project_state.json'
 if statefile.exists() and not a.force:return output(result([err('PROJECT_EXISTS')]))
 path.mkdir(parents=True,exist_ok=True)
 obj={'schema_version':V,'project_id':a.id,'seed':a.seed,'status':'CREATED','locked_title':'',
  'title_sha256':None,'created_at':now(),'repair_cycles':{'A':0,'B':0,'C':0},
  'part_sha256':{},'audit_sha256':None,'history':[]}
 save_json(statefile,obj)
 for folder in ('script','plans','qa','publish'):(path/folder).mkdir(exist_ok=True)
 return output(result([],file=str(statefile),state='CREATED'))

def project_gate(statepath,target,title=None,blueprint=None,partfiles=None,auditfile=None,specfile=None,imagefile=None):
 e=[];sp=Path(statepath);project=sp.parent;state=load_json(sp);current=state['status']
 if target not in STATE_NEXT.get(current,[]):return result([err('ILLEGAL_STATE_TRANSITION',from_state=current,to_state=target)])
 if target=='TITLE_LOCKED':
  if not title or not title.strip():e.append(err('TITLE_REQUIRED'))
  else:state['locked_title']=title;state['title_sha256']=sha_bytes(title.encode('utf-8'))
 if target=='OUTLINE_APPROVED':
  if not blueprint:e.append(err('BLUEPRINT_REQUIRED'))
  else:
   obj=load_json(blueprint);r=blueprint_check(obj);e.extend(r['errors'])
   if obj.get('locked_title')!=state['locked_title']:e.append(err('TITLE_LOCK_MISMATCH'))
   if not e:state['blueprint_sha256']=sha_path(blueprint)
 if target in ('A_READY','B_READY','C_READY','AUDIT_IN_PROGRESS','PUBLISH_READY','EXPORTED'):
  files={p:project/'script'/f'{p}.txt' for p in PARTS} if not partfiles else dict(zip(PARTS,partfiles))
  required=['A'] if target=='A_READY' else ['A','B'] if target=='B_READY' else list(PARTS)
  for p in required:
   if not Path(files[p]).exists():e.append(err('MISSING_PART_FILE',part=p));continue
   txt=read_utf8(files[p]);count=pure_count(txt);lo,hi=PART_RANGES[p]
   if not lo<=count<=hi:e.append(err('PART_LENGTH_FAIL',part=p,count=count))
   e.extend([{**q,'part':p} for q in script_issues(txt)])
   existing=state.get('part_sha256',{}).get(p)
   if existing and existing!=sha_path(files[p]):e.append(err('PART_HASH_CHANGED_OUTSIDE_VERIFIED_PATCH',part=p))
   state.setdefault('part_sha256',{})[p]=sha_path(files[p])
   # For the currently completed part, require a sidecar continuity handoff and compare with prior part.
   if target==f'{p}_READY':
    side=project/'script'/f'{p}_HANDOFF.json'
    if not side.exists():e.append(err('HANDOFF_REQUIRED',part=p))
    else:
     previous=project/'script'/f'{PARTS[PARTS.index(p)-1]}_HANDOFF.json' if p!='A' else None
     if previous and not previous.exists():e.append(err('PREVIOUS_HANDOFF_MISSING',part=p))
     else:e.extend(handoff_check(load_json(side),p,files[p],load_json(previous) if previous else None)['errors'])
  if required==list(PARTS) and all(Path(files[p]).exists() for p in PARTS):
   r=part_check(files);e.extend(r['errors'])
 if target=='PUBLISH_READY':
  ap=auditfile or project/'qa'/'audit.json'
  if not Path(ap).exists():e.append(err('AUDIT_FILE_REQUIRED'))
  else:
   rep=part_check(files);r=audit_check(load_json(ap),rep,state['locked_title']);e.extend(r['errors'])
   if not e:state['audit_sha256']=sha_path(ap)
 if target=='EXPORTED':
  ap=auditfile or project/'qa'/'audit.json'
  if not Path(ap).exists() or sha_path(ap)!=state.get('audit_sha256'):e.append(err('AUDIT_CHANGED_AFTER_PASS'))
  sf=specfile or project/'publish'/'thumbnail_spec.json'
  if not Path(sf).exists():e.append(err('THUMB_SPEC_REQUIRED'))
  else:
   obj=load_json(sf)
   if obj.get('locked_title')!=state['locked_title']:e.append(err('TITLE_LOCK_MISMATCH'))
   e.extend(thumb_check(obj,imagefile)['errors'])
 if e:return result(e,from_state=current,to_state=target)
 state['status']=target;state['history'].append({'at':now(),'from':current,'to':target});save_json(sp,state)
 return result([],state=target,file=str(sp))

def cmd_gate(a):
 if a.target=='REPAIR':
  sp=Path(a.dir)/'project_state.json';state=load_json(sp);p=a.part.upper() if a.part else ''
  if state['status']!='AUDIT_IN_PROGRESS' or p not in PARTS:return output(result([err('REPAIR_STATE_OR_PART_INVALID')]))
  auditfile=Path(a.dir)/'qa'/'audit.json'
  if not auditfile.is_file():return output(result([err('REPAIR_AUDIT_REQUIRED')]))
  audit=load_json(auditfile)
  if audit.get('part_status',{}).get(p)!='PATCH_REQUIRED':return output(result([err('PART_NOT_PATCH_REQUIRED',part=p)]))
  if any(audit.get('coverage',{}).get(x,{}).get('source_sha256')!=state.get('part_sha256',{}).get(x) for x in PARTS):return output(result([err('AUDIT_STALE_FOR_CURRENT_SCRIPTS')]))
  if state['repair_cycles'][p]>=3:return output(result([err('REPAIR_CYCLE_LIMIT',part=p)]))
  state['repair_cycles'][p]+=1;save_json(sp,state)
  return output(result([],part=p,cycle=state['repair_cycles'][p],note='Permission to attempt scoped patch only; does not approve a changed part.'))
 return output(project_gate(Path(a.dir)/'project_state.json',a.target,a.title,a.blueprint,
  (a.a,a.b,a.c) if a.a and a.b and a.c else None,a.audit,a.spec,a.image))

def cmd_corpus(a):
 directory=Path(a.directory);files=sorted(directory.glob('ref_*.txt'))
 manifest=[]
 for p in files:manifest.append({'name':p.name,'bytes':p.stat().st_size,'sha256':sha_path(p)})
 data={'schema_version':V,'type':'PACKAGED_REFERENCE_CORPUS','count':len(manifest),'files':manifest,
  'warning':'Original manifest filenames/hashes refer to a different source representation; do not misidentify these bundled files as matching the source SHA.'}
 if a.out:save_json(a.out,data)
 return output(result([] if len(files)==35 else [err('CORPUS_COUNT_NOT_35',count=len(files))],manifest=data))

def cmd_validate_corpus(a):
 m=load_json(a.manifest);errors=[];folder=Path(a.directory)
 for item in m['files']:
  p=folder/item['name']
  if not p.is_file() or p.stat().st_size!=item['bytes'] or sha_path(p)!=item['sha256']:
   errors.append(err('CORPUS_FILE_MISMATCH',file=item['name']))
 if len(m['files'])!=35:errors.append(err('CORPUS_MANIFEST_SIZE_INVALID',count=len(m['files'])))
 return output(result(errors,checked=len(m['files'])))



def handoff_check(obj,part,script,previous=None):
 e=[]
 if obj.get('part')!=part:e.append(err('HANDOFF_PART_MISMATCH'))
 if obj.get('script_sha256')!=sha_path(script):e.append(err('HANDOFF_SCRIPT_SHA_MISMATCH',part=part))
 for key in ('end_time','end_location','next_scene','characters','documents','open_loops','seed_ids','forbidden_contradictions'):
  if key not in obj or obj[key] is None or (key in ('end_time','end_location','next_scene') and not str(obj[key]).strip()):
   e.append(err('HANDOFF_FIELD_MISSING',field=key))
 for name,data in (obj.get('characters',{}) or {}).items():
  if not isinstance(data,dict) or not isinstance(data.get('knowledge_ids'),list):e.append(err('HANDOFF_CHARACTER_KNOWLEDGE_INVALID',character=name))
 if previous:
  prevpart=PARTS[PARTS.index(part)-1] if part!='A' else None
  if previous.get('part')!=prevpart:e.append(err('HANDOFF_PREVIOUS_PART_MISMATCH'))
  prevo=set(previous.get('open_loops',[]));nowo=set(obj.get('open_loops',[]));closed=set(obj.get('closed_loops',[]))
  for x in sorted(prevo-nowo-closed):e.append(err('HANDOFF_LOOP_DISAPPEARED',loop=x))
  for name,char in (previous.get('characters',{}) or {}).items():
   if name not in (obj.get('characters',{}) or {}):e.append(err('HANDOFF_CHARACTER_DISAPPEARED',character=name));continue
   before=set(char.get('knowledge_ids',[]));after=set(obj['characters'][name].get('knowledge_ids',[]))
   corrections=set(obj.get('knowledge_corrections',{}).get(name,[]))
   for x in sorted(before-after-corrections):e.append(err('HANDOFF_KNOWLEDGE_LOST_UNEXPLAINED',character=name,fact=x))
 return result(e,part=part,script_sha256=sha_path(script))

def cmd_handoff(a):
 obj=load_json(a.handoff);previous=load_json(a.previous) if a.previous else None
 return output(handoff_check(obj,a.part,a.script,previous))

def cmd_commit_patch(a):
 project=Path(a.dir);sp=project/'project_state.json';state=load_json(sp);part=a.part
 errors=[]
 if state.get('status')!='AUDIT_IN_PROGRESS':errors.append(err('NOT_IN_AUDIT_STATE'))
 cycle=state.get('repair_cycles',{}).get(part,0)
 if not 1<=cycle<=3:errors.append(err('PATCH_CYCLE_NOT_AUTHORIZED',cycle=cycle))
 audit_path=project/'qa'/'audit.json'
 if not audit_path.exists():errors.append(err('REPAIR_AUDIT_REQUIRED'))
 else:
  audit=load_json(audit_path)
  if audit.get('part_status',{}).get(part)!='PATCH_REQUIRED':errors.append(err('PART_NOT_PATCH_REQUIRED',part=part))
  if any(audit.get('coverage',{}).get(x,{}).get('source_sha256')!=state.get('part_sha256',{}).get(x) for x in PARTS):errors.append(err('AUDIT_STALE_FOR_CURRENT_SCRIPTS'))
  ids={t.get('id') for t in audit.get('tickets',[]) if t.get('part')==part}
  supplied=load_json(a.tickets);supplied=supplied if isinstance(supplied,list) else supplied.get('tickets',[])
  if not supplied or not all(t.get('id') in ids for t in supplied):errors.append(err('UNAUTHORIZED_PATCH_TICKETS'))
 src=project/'script'/f'{part}.txt'
 if not src.exists():errors.append(err('SOURCE_PART_MISSING'))
 elif sha_path(src)!=state.get('part_sha256',{}).get(part):errors.append(err('SOURCE_VERSION_MISMATCH'))
 for other in PARTS:
  if other==part:continue
  f=project/'script'/f'{other}.txt'
  if not f.exists() or sha_path(f)!=state.get('part_sha256',{}).get(other):errors.append(err('OTHER_PART_HASH_MISMATCH',part=other))
 if errors:return output(result(errors))
 check=check_patch(src,a.candidate,supplied,part,cycle,state['part_sha256'][part])
 if check['errors']:return output(check)
 total=check['after_count']+sum(pure_count(read_utf8(project/'script'/f'{other}.txt')) for other in PARTS if other!=part)
 if not TOTAL_RANGE[0]<=total<=TOTAL_RANGE[1]:return output(result([err('PATCH_TOTAL_LENGTH_FAIL',total=total)]))
 old_hash=sha_path(src);src.write_bytes(Path(a.candidate).read_bytes());state['part_sha256'][part]=sha_path(src)
 state['audit_sha256']=None;state['history'].append({'at':now(),'event':'PATCH_COMMITTED','part':part,'cycle':cycle,'old_sha256':old_hash,'new_sha256':sha_path(src)})
 save_json(sp,state)
 return output(result([],part=part,total=total,cycle=cycle,new_sha256=sha_path(src),
  note='Changes committed after scoped mechanical validation. STEP 5 must re-audit entire A/B/C.'))

def cmd_verify_state(a):
 project=Path(a.dir);state=load_json(project/'project_state.json');e=[]
 if state.get('locked_title') and sha_bytes(state['locked_title'].encode('utf-8'))!=state.get('title_sha256'):
  e.append(err('TITLE_LOCK_HASH_INCONSISTENT'))
 for part,digest in state.get('part_sha256',{}).items():
  f=project/'script'/f'{part}.txt'
  if not f.exists() or sha_path(f)!=digest:e.append(err('STATE_PART_SHA_MISMATCH',part=part))
 if state.get('status') in ('PUBLISH_READY','EXPORTED'):
  f=project/'qa'/'audit.json'
  if not f.exists() or sha_path(f)!=state.get('audit_sha256'):e.append(err('STATE_AUDIT_SHA_MISMATCH'))
 return output(result(e,project_id=state.get('project_id'),state=state['status'],part_hashes=state.get('part_sha256',{})))

def cmd_archive(a):
 p=Path(a.dir);state=load_json(p/'project_state.json');e=[]
 if state['status']!='EXPORTED':e.append(err('PROJECT_NOT_EXPORTED'))
 idea_path=p/'plans'/'idea.json'
 if not idea_path.exists():e.append(err('IDEA_JSON_REQUIRED_FOR_HISTORY'))
 if e:return output(result(e))
 idea=load_json(idea_path)
 record={'project_id':state['project_id'],'title':state['locked_title'],
   'fingerprint':idea.get('fingerprint',{}),'primary_dna':idea.get('primary_dna'),
   'hook_dna':idea.get('hook_dna'),'exported_at':now()}
 hp=Path(a.history)
 data=load_json(hp) if hp.exists() else {'schema_version':V,'items':[]}
 items=data.get('items',[])
 if any(item.get('project_id')==record['project_id'] for item in items):return output(result([err('PROJECT_ALREADY_ARCHIVED')]))
 items.append(record);data['items']=items;save_json(hp,data)
 return output(result([],history_file=str(hp),total_projects=len(items)))

def parser():
 ap=argparse.ArgumentParser(description='ADAS V4 controller and deterministic validators')
 sub=ap.add_subparsers(dest='command',required=True)
 def add(name,fn):p=sub.add_parser(name);p.set_defaults(fn=fn);return p
 p=add('count',cmd_count);p.add_argument('file');p.add_argument('--part',choices=['A','B','C'])
 p=add('parts',cmd_parts);[p.add_argument(x) for x in ('a','b','c')]
 p=add('clean-script',cmd_clean);p.add_argument('source');p.add_argument('--dest',required=True)
 p=add('originality',cmd_originality);p.add_argument('idea');p.add_argument('--history',nargs='*')
 p=add('blueprint',cmd_blueprint);p.add_argument('file')
 p=add('audit',cmd_audit);p.add_argument('audit');[p.add_argument('--'+x) for x in ('a','b','c','title')]
 p=add('patch',cmd_patch);p.add_argument('--before',required=True);p.add_argument('--after',required=True);p.add_argument('--tickets',required=True);p.add_argument('--part',choices=PARTS,required=True);p.add_argument('--cycle',type=int,default=1);p.add_argument('--original-sha')
 p=add('thumbnail',cmd_thumbnail);p.add_argument('spec');p.add_argument('--image')
 p=add('render-thumbnail',cmd_render);p.add_argument('spec');p.add_argument('--background',required=True);p.add_argument('--out',required=True);p.add_argument('--font')
 p=add('init',cmd_init);p.add_argument('--dir',required=True);p.add_argument('--id',required=True);p.add_argument('--seed',required=True);p.add_argument('--force',action='store_true')
 p=add('gate',cmd_gate);p.add_argument('--dir',required=True);p.add_argument('--target',required=True,choices=list(STATES[1:])+['REPAIR']);p.add_argument('--part');p.add_argument('--title');p.add_argument('--blueprint');[p.add_argument('--'+x) for x in ('a','b','c','audit','spec','image')]
 p=add('handoff',cmd_handoff);p.add_argument('handoff');p.add_argument('--part',choices=PARTS,required=True);p.add_argument('--script',required=True);p.add_argument('--previous')
 p=add('commit-patch',cmd_commit_patch);p.add_argument('--dir',required=True);p.add_argument('--part',choices=PARTS,required=True);p.add_argument('--candidate',required=True);p.add_argument('--tickets',required=True)
 p=add('verify-state',cmd_verify_state);p.add_argument('--dir',required=True)
 p=add('archive',cmd_archive);p.add_argument('--dir',required=True);p.add_argument('--history',required=True)
 p=add('corpus-manifest',cmd_corpus);p.add_argument('directory');p.add_argument('--out')
 p=add('verify-corpus',cmd_validate_corpus);p.add_argument('directory');p.add_argument('manifest')
 return ap

if __name__=='__main__':
 try:
  ap=parser()
  args=ap.parse_args()
  sys.exit(args.fn(args))
 except (ValueError,KeyError,TypeError,UnicodeError,OSError) as ex:sys.exit(output(result([err('INPUT_ERROR',reason=str(ex))])))
