import importlib.util,json,tempfile,unittest,sys,copy
from pathlib import Path
from PIL import Image
SRC=Path(__file__).resolve().parents[1]/'scripts'/'adas_v4.py'
spec=importlib.util.spec_from_file_location('adas_v4',SRC);v4=importlib.util.module_from_spec(spec);spec.loader.exec_module(v4)

class V4Tests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.dir=Path(self.t.name)
 def files(self):
  d=self.dir/'script';d.mkdir(exist_ok=True)
  files={}
  for p,chars in [('A',14500),('B',15000),('C',16000)]:
   # 50 lines per part, deterministic but this is ONLY a synthetic mechanical fixture
   n=chars//50;txt=''.join(('あ' if p=='A' else 'い' if p=='B' else 'う')*n+'\n' for _ in range(50))
   path=d/f'{p}.txt';path.write_text(txt,encoding='utf8');files[p]=path
  return files
 def blueprint(self):
  scenes=[]
  for part,target in [('A',2000),('B',2100),('C',2200)]:
   for i in range(1,8):
    scenes.append({'id':f'{part}{i:02}','part':part,'purpose':'a genuine scene','new_info':'new data',
     'action':'decision','conflict':'relational pressure','state_change':'new state',
     'evidence':'evidence or witnessed event','knowledge_transfer':'who learns and how','target_chars':target})
  bp={'locked_title':'テストの親子物語','title_promise':'payoff','central_question':'Who did what and why?',
  'narrative_spine':'misunderstanding→discovery→earned correction','primary_dna':'evidence detective','secondary_dna':['moral reversal'],
  'hook_dna':'concrete injustice','emotional_arc':'anger→regret→repair','reversal_mechanism':'a verifiable letter',
  'proof_chain':[{'id':'E01','created_by':'mother','stored_at':'locked drawer','accessed_by':'son','access_path':'explicit permission','first_seen_scene':'A02'}],
  'characters':[{'name':'mother','motive':'protect family'}], 'timeline':[{'scene':'A01','date':'2026-01-01'}],
  'setup_payoff':[{'id':'S1','scene':'A01'},{'id':'S2','scene':'A02'}],
  'reveals':[{'id':f'R{i}','seed_ids':['S1','S2']} for i in range(1,4)],'scenes':scenes,
  'part_contracts':{p:{'entry_state':'entry','exit_state':'exit','open_loops':['loop'],'next_scene':'next',
                   **({'title_promise_payoff_id':'R3'} if p=='C' else {})} for p in 'ABC'}}
  return bp
 def audit(self,files):
  return {'mode':'BASELINE','locked_title':'テストの親子物語','scores':dict(v4.RUBRIC),
   'total_score':100,'fatal_flags':[],'p0_count':0,'tickets':[],
   'part_status':{p:'PASS_LOCKED' for p in 'ABC'},
   'coverage':{p:{'reviewed_full':True,'evidence_notes':'Causal chain checked; manual reviewer assertion','source_sha256':v4.sha_path(files[p])} for p in 'ABC'},
   'logical_audit':'mechanisms, dates, information paths reviewed','holistic_audit':'retention, emotion, spoken Japanese reviewed'}
 def thumb(self):
  obj={'locked_title':'テストの親子物語','title':'テストの親子物語','right_face_fraction':0.37,
   'L6':{'spans':[{'text':'息子は','color':'cyan'},{'text':'絶句した','color':'magenta'}],'same_baseline':True}}
  for i,c in enumerate(['yellow','white','magenta','yellow','cyan'],1):obj[f'L{i}']={'text':f'親子の事実{i}','color':c}
  return obj
 def test_pure_count_nfc_and_reject_invalid_utf8(self):
  self.assertEqual(v4.pure_count('Aé e\u0301 １２ ！\n'),5)
  x=self.dir/'bad.txt';x.write_bytes(b'\xff')
  with self.assertRaises(UnicodeError):v4.read_utf8(x)
 def test_parts_and_metadata_gate(self):
  files=self.files();self.assertEqual(v4.part_check(files)['status'],'PASS')
  files['A'].write_text(files['A'].read_text(encoding='utf8')+'LOCKED_TITLE: hello\n',encoding='utf8')
  r=v4.part_check(files);self.assertEqual(r['status'],'FAIL');self.assertIn('META_TITLE',{e['code'] for e in r['errors']})
 def test_blueprint_good_bad(self):
  bp=self.blueprint();self.assertEqual(v4.blueprint_check(bp)['status'],'PASS')
  bp['reveals'][1]['seed_ids']=['S1'];self.assertEqual(v4.blueprint_check(bp)['status'],'FAIL')
 def test_originality_core_reuse(self):
  obj={'title':'別名','title_promise':'promise','premise':'plot','primary_dna':'x','hook_dna':'x','longform_capacity':'PASS',
   'fingerprint':{'relation':'母子','setting':'家','trigger':'夫の発言','evidence':'手紙','mechanism':'本人が書いた報告書','reveal':'中盤で発見','payoff':'母の無罪が判明','consequence':'謝罪'}}
  old=copy.deepcopy(obj);old['title']='まったく別の題名';old['fingerprint']['relation']='父娘';old['fingerprint']['setting']='会社'
  self.assertTrue(all(old['fingerprint'][f]==obj['fingerprint'][f] for f in ('mechanism','payoff')))
  self.assertGreaterEqual(len(v4.grams(obj['title'])),1)
  d=self.dir/'idea.json';v4.save_json(d,obj);h=self.dir/'hist.json';v4.save_json(h,{'items':[old]})
  from argparse import Namespace
  # Suppress report while testing return code
  import contextlib,io
  with contextlib.redirect_stdout(io.StringIO()) as buf:code=v4.cmd_originality(Namespace(idea=str(d),history=[str(h)]))
  self.assertEqual(code,2);self.assertIn('ORIGINALITY_RED',buf.getvalue())
 def test_patch_scoped_and_unauthorized(self):
  files=self.files();src=files['C'];parts=src.read_text(encoding='utf8').splitlines(keepends=True)
  modified=parts.copy();modified[13]='え'*len(modified[13].strip())+'\n'
  after=self.dir/'after.txt';after.write_text(''.join(modified),encoding='utf8')
  tickets=[{'id':'T01','part':'C','allowed_scope':{'start_line':14,'end_line':14}}]
  self.assertEqual(v4.check_patch(src,after,tickets,'C',1)['status'],'PASS')
  self.assertEqual(v4.check_patch(src,after,tickets,'C',4)['status'],'FAIL')
  changed=modified.copy();changed[1]='え'*len(changed[1].strip())+'\n'
  after.write_text(''.join(changed),encoding='utf8')
  self.assertIn('PATCH_OUTSIDE_SCOPE',{e['code'] for e in v4.check_patch(src,after,tickets,'C',1)['errors']})
 def test_audit_p0_score_and_stale_content(self):
  files=self.files();r=v4.part_check(files)
  self.assertEqual(v4.audit_check(self.audit(files),r,'テストの親子物語')['status'],'PASS')
  audit=self.audit(files);audit['fatal_flags']=['fatal_causal_contradiction'];audit['p0_count']=1
  bad=v4.audit_check(audit,r,'テストの親子物語')
  self.assertEqual(bad['status'],'FAIL');self.assertFalse(bad['publish_ready'])
  audit=self.audit(files);audit['coverage']['A']['source_sha256']='bad'
  self.assertIn('AUDIT_SOURCE_STALE',{e['code'] for e in v4.audit_check(audit,r,'テストの親子物語')['errors']})
 def test_thumb_renderer_and_visual_pending(self):
  obj=self.thumb();self.assertEqual(v4.thumb_check(obj)['status'],'PASS')
  bg=self.dir/'bg.png';Image.new('RGB',(1536,1024),'#6c7d84').save(bg)
  out=self.dir/'out.jpg';self.assertEqual(v4.render_thumb(obj,bg,out)['status'],'PASS')
  with Image.open(out) as im:self.assertEqual(im.size,(1280,720))
  pending=v4.thumb_check(obj,out);self.assertIn('VISUAL_QA_MISSING',{e['code'] for e in pending['errors']})
  obj['visual_qa']={'detected_lines':6,'l6_same_baseline':True,'no_extra_text':True,
    'face_position_verified':True,'text_readability_confirmed':True}
  self.assertEqual(v4.thumb_check(obj,out)['status'],'PASS')
  obj['L6']['same_baseline']=False;self.assertEqual(v4.thumb_check(obj,out)['status'],'FAIL')
 def test_state_machine_end_to_end(self):
  from argparse import Namespace
  import contextlib,io
  p=self.dir/'P001';p.mkdir();state=p/'project_state.json'
  with contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(v4.cmd_init(Namespace(dir=str(p),id='P001',seed='a family misunderstanding',force=False)),0)
  def go(target,**kwargs):
   return v4.project_gate(state,target,**kwargs)
  self.assertEqual(go('TITLE_LOCKED',title='テストの親子物語')['status'],'PASS')
  bp=p/'plans'/'blueprint.json';v4.save_json(bp,self.blueprint())
  self.assertEqual(go('OUTLINE_APPROVED',blueprint=bp)['status'],'PASS')
  files=self.files()
  for part in 'ABC':
   (p/'script'/f'{part}.txt').write_bytes(files[part].read_bytes())
  for part in 'ABC':
   handoff={'part':part,'script_sha256':v4.sha_path(p/'script'/f'{part}.txt'),
    'end_time':f'2026-01-0{1+"ABC".index(part)}','end_location':'Tokyo',
    'next_scene':f'{part}_NEXT','characters':{'mother':{'knowledge_ids':['E01']}},
    'documents':[],'open_loops':['L1'],'closed_loops':[],
    'seed_ids':['S1'],'forbidden_contradictions':[]}
   v4.save_json(p/'script'/f'{part}_HANDOFF.json',handoff)
  for target in ['A_READY','B_READY','C_READY','AUDIT_IN_PROGRESS']:
   self.assertEqual(go(target)['status'],'PASS',target)
  q=p/'qa'/'audit.json';v4.save_json(q,self.audit({x:p/'script'/f'{x}.txt' for x in 'ABC'}))
  self.assertEqual(go('PUBLISH_READY',auditfile=q)['status'],'PASS')
  thumb=p/'publish'/'thumbnail_spec.json';v4.save_json(thumb,self.thumb())
  bg=p/'publish'/'bg.jpg';Image.new('RGB',(1536,1024),'#6f8080').save(bg)
  img=p/'publish'/'final.jpg';v4.render_thumb(self.thumb(),bg,img)
  obj=self.thumb();obj['visual_qa']={'detected_lines':6,'l6_same_baseline':True,'no_extra_text':True,
    'face_position_verified':True,'text_readability_confirmed':True}
  v4.save_json(thumb,obj)
  self.assertEqual(go('EXPORTED',specfile=thumb,imagefile=img)['status'],'PASS')
  state_data=v4.load_json(state)
  self.assertEqual(state_data['status'],'EXPORTED');self.assertTrue(state_data['audit_sha256'])
  self.assertEqual(go('TITLE_LOCKED',title='changed')['status'],'FAIL')

 def test_two_real_patch_cycles_with_state_and_lock(self):
  from argparse import Namespace
  import contextlib,io
  p=self.dir/'P002';p.mkdir();statefile=p/'project_state.json'
  with contextlib.redirect_stdout(io.StringIO()):v4.cmd_init(Namespace(dir=str(p),id='P002',seed='seed',force=False))
  files=self.files();v4.project_gate(statefile,'TITLE_LOCKED',title='テストの親子物語')
  bp=p/'plans'/'blueprint.json';v4.save_json(bp,self.blueprint());v4.project_gate(statefile,'OUTLINE_APPROVED',blueprint=bp)
  for part in 'ABC':
   src=p/'script'/f'{part}.txt';src.write_bytes(files[part].read_bytes())
   handoff={'part':part,'script_sha256':v4.sha_path(src),'end_time':'2026-01-01','end_location':'Tokyo',
    'next_scene':'next','characters':{'mother':{'knowledge_ids':['E01']}},
    'documents':[],'open_loops':['L1'],'closed_loops':[],'seed_ids':[],'forbidden_contradictions':[]}
   v4.save_json(p/'script'/f'{part}_HANDOFF.json',handoff)
  for state in ('A_READY','B_READY','C_READY','AUDIT_IN_PROGRESS'):
   self.assertEqual(v4.project_gate(statefile,state)['status'],'PASS')
  digests=v4.load_json(statefile)['part_sha256'].copy()
  q=p/'qa'/'audit.json';scriptfiles={x:p/'script'/f'{x}.txt' for x in 'ABC'}
  for cycle,line in ((1,14),(2,18)):
   audit=self.audit(scriptfiles);audit['scores']['G']=2;audit['total_score']=92
   audit['part_status']['C']='PATCH_REQUIRED'
   audit['tickets']=[{'id':f'T{cycle}','part':'C','priority':'P1','location':f'C line {line}',
     'root_cause':'unmotivated choice','allowed_scope':{'start_line':line,'end_line':line},
     'acceptance':'choice and consequence explained'}]
   v4.save_json(q,audit)
   with contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(v4.cmd_gate(Namespace(dir=str(p),target='REPAIR',part='C')),0)
   before=scriptfiles['C'].read_text(encoding='utf8').splitlines(keepends=True)
   before[line-1]='え'*len(before[line-1].strip())+'\n'
   candidate=p/f'candidate{cycle}.txt';candidate.write_text(''.join(before),encoding='utf8')
   with contextlib.redirect_stdout(io.StringIO()) as buf:
    code=v4.cmd_commit_patch(Namespace(dir=str(p),part='C',candidate=str(candidate),tickets=str(q)))
   self.assertEqual(code,0,buf.getvalue())
   current=v4.load_json(statefile)['part_sha256']
   self.assertEqual(current['A'],digests['A']);self.assertEqual(current['B'],digests['B'])
   self.assertNotEqual(current['C'],digests['C']);digests=current.copy()
   # stale audit cannot authorize another repair until STEP 5 rescores the new part
   with contextlib.redirect_stdout(io.StringIO()) as buf:
    stale=v4.cmd_gate(Namespace(dir=str(p),target='REPAIR',part='C'))
   self.assertEqual(stale,2)
  final=self.audit(scriptfiles);v4.save_json(q,final)
  self.assertEqual(v4.project_gate(statefile,'PUBLISH_READY',auditfile=q)['status'],'PASS')
  with contextlib.redirect_stdout(io.StringIO()) as buf:
   self.assertEqual(v4.cmd_gate(Namespace(dir=str(p),target='REPAIR',part='C')),2)

if __name__=='__main__': unittest.main(verbosity=2)
