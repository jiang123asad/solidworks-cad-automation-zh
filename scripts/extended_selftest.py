"""Bounded, sequential functional tests on task-owned SolidWorks documents.

Each PASS requires a postcondition and a saved model when relevant.
Exceptions are failed test setups/calls, never a claim that SW lacks the feature.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse,json,math,sys,time,traceback
import pythoncom
from win32com.client import VARIANT

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import swlib
from sw_constants import constants

ap=argparse.ArgumentParser(description='Creates owned SW samples and checks geometric postconditions. Runs sequentially; does not certify all SW features.')
ap.add_argument('--out',required=True,type=Path,help='New empty result directory')
ap.add_argument('--group',choices=('body','specialty','all'),default='all')
args=ap.parse_args()
OUT=args.out.resolve()
if OUT.exists() and any(OUT.iterdir()):ap.error('--out must be absent or empty')
OUT.mkdir(parents=True,exist_ok=True)
GROUP=OUT
sw=swlib.app()
M=swlib.mod()
C=constants()
records=[]
owned=[]
original_dir=sw.GetCurrentWorkingDirectory()

def arr(values):return VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_R8,values)
def objects(values):return VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_DISPATCH,values)
def check(cond,message):
    if not cond:raise AssertionError(message)
def wrap(name,obj):
    check(obj is not None,'No '+name+' object')
    return swlib.wrap(getattr(M,name),obj)

def new(typ=1):
    if typ==1:raw=swlib.new_part(sw)
    elif typ==2:raw=sw.NewAssembly()
    else:
        template=sw.GetUserPreferenceStringValue(C.swDefaultTemplateDrawing)
        raw=sw.NewDocument(template,0,0.,0.)
    check(raw is not None,'New document failed')
    owned.append(raw)
    return raw,swlib.model(raw)

def close_all_owned():
    for raw in reversed(owned):
        try:sw.CloseDoc(swlib.model(raw).GetTitle())
        except Exception as exc:print('CLEANUP',str(exc),flush=True)
    owned.clear()
    sw.SetCurrentWorkingDirectory(str(OUT))

def planes(doc):
    out=[]; f=doc.FirstFeature()
    while f is not None:
        f=wrap('IFeature',f)
        if f.GetTypeName2()=='RefPlane':out.append(f)
        f=f.GetNextFeature()
    return out

def sketch(doc,plane=0):
    doc.ClearSelection2(True)
    p=planes(doc)[plane] if isinstance(plane,int) else plane
    check(p.Select2(False,0),'Select sketch plane failed')
    sk=doc.SketchManager
    sk.InsertSketch(True)
    sk.AddToDB=True
    return sk

def end_sketch(doc):
    sk=doc.SketchManager
    sk.AddToDB=False
    sk.InsertSketch(True)
    return swlib.last_sketch(doc)

def select_sketch(doc,s=None,mark=0,append=False):
    if not append:doc.ClearSelection2(True)
    s=s or swlib.last_sketch(doc)
    check(s is not None and s.Select2(append,mark),'Sketch selection failed')

def extrude(doc,h=.02,merge=True,draft=0,mid=False):
    select_sketch(doc)
    f=doc.FeatureManager.FeatureExtrusion2(True,False,False,6 if mid else 0,0,h,0.,
        bool(draft),False,False,False,math.radians(draft),0.,False,False,False,False,merge,True,True,0,0.,False)
    doc.ClearSelection2(True);doc.ForceRebuild3(False)
    return f

def cut(doc,h=.04,draft=0):
    select_sketch(doc)
    f=doc.FeatureManager.FeatureCut4(True,False,True,0,0,h,0.,bool(draft),False,False,False,
        math.radians(draft),0.,False,False,False,False,False,True,True,False,False,False,0,0.,False,True)
    doc.ClearSelection2(True);doc.ForceRebuild3(False)
    return f

def block(x=.04,y=.03,z=.02,origin=(0,0)):
    raw,doc=new();sk=sketch(doc)
    sk.CreateCornerRectangle(origin[0],origin[1],0,origin[0]+x,origin[1]+y,0)
    end_sketch(doc);f=extrude(doc,z)
    check(f is not None and swlib.total_volume(raw)>0,'Block extrusion failed')
    return raw,doc,f

def cylinder(r=.015,h=.04):
    raw,doc=new();sk=sketch(doc)
    sk.CreateCircleByRadius(0,0,0,r);end_sketch(doc);f=extrude(doc,h)
    check(f is not None and swlib.total_volume(raw)>0,'Cylinder extrusion failed')
    return raw,doc,f

def metrics(raw):
    return {'volume_mm3':swlib.total_volume(raw),'solid_bodies':len(swlib.bodies(raw)),
            'faces':swlib.total_faces(raw),'features':len(swlib.walk_features(swlib.model(raw)))}

def changed(raw,doc,before,direction=None):
    doc.ClearSelection2(True);doc.ForceRebuild3(False)
    after=swlib.total_volume(raw)
    if direction=='down':check(after<before-1e-4,'No verified material removal')
    if direction=='up':check(after>before+1e-4,'No verified material addition')
    return metrics(raw)

def save(raw,name):
    doc=swlib.model(raw)
    suffix={1:'.SLDPRT',2:'.SLDASM',3:'.SLDDRW'}[doc.GetType()]
    path=GROUP/(name+suffix)
    swlib.save_as(doc,path)
    return str(path)

def test(name,fn,category=None):
    print('BEGIN',name,flush=True)
    start=time.monotonic()
    try:
        info=fn(name)
        rec={'name':name,'category':category or args.group,'status':'PASS','evidence':info}
    except Exception as exc:
        rec={'name':name,'category':category or args.group,'status':'FAIL',
             'error':str(exc),'traceback':traceback.format_exc(limit=4)}
    finally:close_all_owned()
    rec['seconds']=round(time.monotonic()-start,2)
    records.append(rec)
    (GROUP/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(rec['status'],name,json.dumps(rec.get('evidence',rec.get('error')),ensure_ascii=False,default=str),flush=True)

def geometry_case(method,call,expected_min=1):
    def fn(name):
        raw,doc=new();sk=sketch(doc)
        result=call(doc,sk)
        f=end_sketch(doc)
        data=wrap('ISketch',f.GetSpecificFeature2())
        segments=data.GetSketchSegments() or []
        points=data.GetSketchPoints2() or []
        check(len(segments)+len(points)>=expected_min,'No persistent sketch geometry')
        return {'segments':len(segments),'points':len(points),'file':save(raw,name)}
    return fn

def select_body(doc,body,mark,append=False):
    data=wrap('ISelectionMgr',doc.SelectionManager).CreateSelectData()
    data.Mark=mark
    return swlib.select_body_mark(doc,body,mark,append)


def body_tests():
    def move(name):
        raw,doc,_=block();v=swlib.total_volume(raw)
        check(select_body(doc,swlib.bodies(raw)[0],1),'Body mark 1 selection failed')
        f=doc.FeatureManager.InsertMoveCopyBody2(.06,0,0,0,0,0,0,0,0,0,True,1)
        info=changed(raw,doc,v,'up')
        bs=swlib.bodies(raw)
        centers=sorted(b.GetMassProperties(1.)[0] for b in bs)
        check(f is not None and len(bs)==2 and abs(centers[1]-centers[0]-.06)<1e-8,'Copy count/displacement mismatch')
        return {**info,'center_x_m':centers,'file':save(raw,name)}
    test('move-copy-body-native-select2',move)
    def mirror(name):
        raw,doc,_=block(.01,.02,.02,(.01,0));v=swlib.total_volume(raw)
        doc.ClearSelection2(True)
        check(select_body(doc,swlib.bodies(raw)[0],256),'Body mark 256 failed')
        check(planes(doc)[2].Select2(True,2),'Mirror plane mark 2 failed')
        f=doc.FeatureManager.InsertMirrorFeature2(True,False,False,False,0)
        info=changed(raw,doc,v,'up');bs=swlib.bodies(raw)
        centers=sorted(b.GetMassProperties(1.)[0] for b in bs)
        check(f is not None and len(bs)==2 and abs(sum(centers))<1e-8,'Mirror symmetry mismatch')
        return {**info,'center_x_m':centers,'file':save(raw,name)}
    test('mirror-body-dedicated-api',mirror)
    def thicken(name):
        raw,doc=new();s=sketch(doc);s.CreateCornerRectangle(0,0,0,.04,.03,0);end_sketch(doc);select_sketch(doc)
        doc.InsertPlanarRefSurface();doc.ForceRebuild3(False)
        surface=wrap('IBody2',wrap('IPartDoc',raw).GetBodies2(1,False)[0])
        doc.ClearSelection2(True);check(select_body(doc,surface,1),'Surface body mark 1 failed')
        f=doc.FeatureManager.FeatureBossThicken(.002,0,0,False,True,False,True)
        info=changed(raw,doc,0,'up');check(f is not None and abs(info['volume_mm3']-2400)<.01,'Thicken analytic mismatch')
        return {**info,'file':save(raw,name)}
    test('thicken-surface-mark1',thicken)
    def draft(name):
        raw,doc,_=block();v=swlib.total_volume(raw)
        neutral=swlib.plane_face_at(raw,2,0,.01);side=swlib.plane_face_at(raw,0,40,.01)
        doc.ClearSelection2(True)
        check(swlib.select_mark(raw,neutral,1,False),'Neutral mark 1 failed')
        check(swlib.select_mark(raw,side,2,True),'Draft face mark 2 failed')
        f=doc.FeatureManager.InsertMultiFaceDraft(math.radians(3),False,False,0,False,False)
        info=changed(raw,doc,v)
        check(f is not None and abs(info['volume_mm3']-v)>1.,'Draft had no geometric effect')
        normals=[]
        for face in swlib.faces(swlib.bodies(raw)[0]):
            surf=wrap('ISurface',face.GetSurface())
            if surf.IsPlane():normals.append(list(surf.PlaneParams[:3]))
        check(any(abs(abs(n[2])-math.sin(math.radians(3)))<1e-6 for n in normals),'3 degree face not found')
        return {**info,'plane_normals':normals,'file':save(raw,name)}
    test('neutral-plane-draft-dedicated-api',draft)
    def linear(name):
        raw,doc,_=block(.01,.01,.01);v=swlib.total_volume(raw);body=swlib.bodies(raw)[0]
        edge=next(e for e in swlib.edges(body) if all(x is not None for x in (e.GetStartVertex(),e.GetEndVertex())) and abs(wrap('IVertex',e.GetStartVertex()).GetPoint()[0]-wrap('IVertex',e.GetEndVertex()).GetPoint()[0])>.009)
        doc.ClearSelection2(True);select_body(doc,body,256)
        swlib.select_mark(raw,edge,1,True)
        data=wrap('ILinearPatternFeatureData',doc.FeatureManager.CreateDefinition(C.swFmLPattern))
        data.PatternElement=C.swBodiesToPattern;data.BodyPattern=True;data.PatternBodyArray=objects([body]);data.D1Axis=edge
        data.D1TotalInstances=3;data.D1Spacing=.03;data.D1ReverseDirection=False
        data.D2TotalInstances=1;data.GeometryPattern=False
        f=doc.FeatureManager.CreateFeature(data);info=changed(raw,doc,v,'up')
        check(f is not None and info['solid_bodies']==3 and abs(info['volume_mm3']-3000)<.01,'Linear array count/volume mismatch')
        return {**info,'file':save(raw,name)}
    test('linear-body-pattern-element2',linear)
    def circular(name):
        raw,doc,_=block(.01,.01,.01,(.02,0));v=swlib.total_volume(raw)
        doc.ClearSelection2(True);planes(doc)[1].Select2(False,0);planes(doc)[2].Select2(True,0)
        doc.InsertAxis2(True);axis=next(swlib.find_feature(doc,n) for t,n,d in swlib.walk_features(doc) if t=='RefAxis')
        doc.ClearSelection2(True);select_body(doc,swlib.bodies(raw)[0],256);axis.Select2(True,1)
        data=wrap('ICircularPatternFeatureData',doc.FeatureManager.CreateDefinition(C.swFmCirPattern))
        data.PatternElement=C.swBodiesToPattern;data.BodyPattern=True;data.PatternBodyArray=objects(swlib.bodies(raw))
        data.Axis=axis.GetSpecificFeature2();data.TotalInstances=4;data.Spacing=2*math.pi;data.EqualSpacing=True;data.ReverseDirection=False
        f=doc.FeatureManager.CreateFeature(data);info=changed(raw,doc,v,'up')
        check(f is not None and info['solid_bodies']==4 and abs(info['volume_mm3']-4000)<.01,'Circular array count/volume mismatch')
        return {**info,'file':save(raw,name)}
    test('circular-body-pattern-element2',circular)
def specialty_tests():
    def hole(name):
        raw,doc,_=block();v=swlib.total_volume(raw)
        doc.ClearSelection2(True)
        data=wrap('IWizardHoleFeatureData2',doc.FeatureManager.CreateDefinition(C.swFmHoleWzd))
        data.InitializeHole(C.swWzdCounterBore,C.swStandardISO,C.swStandardISOHexBolt,'M6',C.swEndCondThroughAll)
        data.HoleDiameter=.0066;data.HoleDepth=.03
        check(doc.Extension.SelectByRay(.02,.015,.05,0.,0.,-1.,.001,2,False,0,0),'Hole ray failed')
        f=doc.FeatureManager.CreateFeature(data)
        info=changed(raw,doc,v,'down');check(f is not None,'Hole Wizard no feature')
        radii=[c[6] for face in swlib.faces(swlib.bodies(raw)[0]) if (c:=swlib.cyl_of(face))]
        check(any(abs(r-3.3)<.001 for r in radii),'Hole diameter mismatch')
        return {**info,'cylinder_radii_mm':radii,'file':save(raw,name)}
    test('hole-wizard-featuredata-iso-counterbore',hole)
    def rib(name):
        raw,doc,_=block(.04,.03,.005)
        s=sketch(doc);s.CreateCornerRectangle(0,0,0,.04,.005,0);end_sketch(doc);extrude(doc,.03)
        v=swlib.total_volume(raw)
        doc.ClearSelection2(True);planes(doc)[2].Select2(False,0)
        doc.FeatureManager.InsertRefPlane(8,.02,0,0.,0,0.)
        plane=planes(doc)[-1];s=sketch(doc,plane)
        active=wrap('ISketch',doc.GetActiveSketch2());xf=active.ModelToSketchTransform
        mu=wrap('IMathUtility',sw.GetMathUtility())
        a=wrap('IMathPoint',wrap('IMathPoint',mu.CreatePoint(arr([.02,.005,.025]))).MultiplyTransform(xf)).ArrayData
        b=wrap('IMathPoint',wrap('IMathPoint',mu.CreatePoint(arr([.02,.025,.005]))).MultiplyTransform(xf)).ArrayData
        s.CreateLine(*a,*b);end_sketch(doc);select_sketch(doc)
        doc.FeatureManager.InsertRib(True,False,.003,0,False,False,False,0.,False,False)
        info=changed(raw,doc,v,'up')
        check(any(t=='Rib' for t,n,d in swlib.walk_features(doc)),'No rib feature')
        return {**info,'file':save(raw,name)}
    test('rib-model-transform-correct-refplane',rib)
    def material(name):
        import xml.etree.ElementTree as ET
        raw,doc,_=block();p=wrap('IPartDoc',raw)
        paths=[Path(x) for x in sw.GetMaterialDatabases() if Path(x).exists()]
        check(paths,'No local material database')
        db=next((x for x in paths if 'solidworks materials' in x.name.lower()),paths[0])
        entries=ET.parse(db).getroot().findall('.//material')
        target=next((e.attrib['name'] for e in entries if 'AISI 1020' in e.attrib.get('name','')),entries[0].attrib['name'])
        p.SetMaterialPropertyName2('',str(db),target);doc.ForceRebuild3(False)
        got=p.GetMaterialPropertyName2('','')
        check(target in str(got),'Material did not round-trip')
        mass=wrap('IMassProperty',doc.Extension.CreateMassProperty());mass.UseSystemUnits=True
        density=mass.Mass/mass.Volume
        check(density>0,'Density invalid')
        return {'material':str(got),'density_kg_m3':density,'mass_kg':mass.Mass,'file':save(raw,name)}
    test('assign-material-and-density',material)
    def appearance(name):
        raw,doc,_=block();e=doc.Extension
        values=[.15,.65,.25,1.,.6,.3,.5,0.,0.]
        e.SetMaterialPropertyValues(arr(values),1,None)
        got=list(e.GetMaterialPropertyValues(1,None))
        check(all(abs(a-b)<=1/255+1e-6 for a,b in zip(got[:3],values[:3])),'RGB readback mismatch')
        return {'rgb':got[:3],'file':save(raw,name)}
    test('appearance-rgb-readback',appearance)
    def interference(name):
        # Identical coincident blocks give an exact positive interference oracle.
        pr,pd,_=block();source=Path(save(pr,name+'-component'))
        raw,doc=new(2);a=wrap('IAssemblyDoc',raw)
        for x in (0.,.02):check(a.AddComponent5(str(source),0,'',False,'',x,0.,0.) is not None,'Add component failed')
        mgr=wrap('IInterferenceDetectionMgr',a.InterferenceDetectionManager)
        try:
            mgr.TreatCoincidenceAsInterference=False;mgr.IncludeMultibodyPartInterferences=True
            ints=mgr.GetInterferences() or [];count=mgr.GetInterferenceCount()
            volumes=[wrap('IInterference',i).Volume*1e9 for i in ints]
            check(count==1 and len(volumes)==1 and abs(volumes[0]-12000)<.1,'Interference volume mismatch')
        finally:mgr.Done()
        return {'interferences':count,'volumes_mm3':volumes,'file':save(raw,name)}
    test('assembly-interference-volume',interference)

if __name__=='__main__':
    try:
        if args.group in ('body','all'):body_tests()
        if args.group in ('specialty','all'):specialty_tests()
    finally:
        close_all_owned()
        sw.SetCurrentWorkingDirectory(original_dir)
    print('SUMMARY', {s:sum(r['status']==s for r in records) for s in ('PASS','FAIL')},flush=True)
    sys.exit(int(any(r['status']=='FAIL' for r in records)))
