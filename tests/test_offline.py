import ast
from contextlib import contextmanager
import copy
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch, Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import swlib, batch_support as batch, compare_versions as compare, add_cone, gui_helper

class FilesystemTests(unittest.TestCase):
    def test_locked_directory_cleanup_does_not_mask_success(self):
        with tempfile.TemporaryDirectory() as t:
            dst=Path(t)/'saved.SLDPRT'
            with patch.object(batch.shutil,'rmtree'),self.assertWarns(UserWarning):
                with batch.staged_file(dst) as staged:
                    staged.write_bytes(b'verified')
            self.assertEqual(dst.read_bytes(),b'verified')

    def test_no_overwrite_or_alias(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'原件.SLDPRT'; p.write_bytes(b'original')
            with self.assertRaises(FileExistsError):
                batch.plan_outputs([p],p.parent)
            with self.assertRaises(FileExistsError):
                with batch.staged_file(p,p): pass
            self.assertEqual(p.read_bytes(),b'original')

    def test_duplicate_stems_fail(self):
        with tempfile.TemporaryDirectory() as t:
            a=Path(t)/'a'/'part.SLDPRT';b=Path(t)/'b'/'part.SLDPRT'
            with self.assertRaises(ValueError):
                batch.plan_outputs([a,b],Path(t)/'out')

    def test_stage_rollback(self):
        with tempfile.TemporaryDirectory() as t:
            src=Path(t)/'source.SLDPRT';src.write_bytes(b'original')
            dst=Path(t)/'out'/'result.SLDPRT'
            with self.assertRaises(RuntimeError):
                with batch.staged_file(dst,src) as staged:
                    staged.write_bytes(b'invalid modified model')
                    raise RuntimeError('geometry rejected')
            self.assertFalse(dst.exists())
            self.assertEqual(src.read_bytes(),b'original')
            self.assertEqual(list(dst.parent.iterdir()),[])

    def test_stage_publish(self):
        with tempfile.TemporaryDirectory() as t:
            dst=Path(t)/'出力.SLDPRT'
            with batch.staged_file(dst) as staged:
                staged.write_bytes(b'verified')
            self.assertEqual(dst.read_bytes(),b'verified')

    def test_globs_and_empty_glob(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'a.SLDPRT';p.touch()
            self.assertEqual(batch.expand_inputs([str(Path(t)/'*.SLDPRT'),str(p)]),[p])
            with self.assertRaises(FileNotFoundError):
                batch.expand_inputs([str(Path(t)/'*.MISSING')])

    def test_relative_pairing_preserves_duplicate_names(self):
        with tempfile.TemporaryDirectory() as t:
            for d in ('a','b'):
                p=Path(t)/d/'相同.SLDPRT';p.parent.mkdir();p.touch()
            self.assertEqual(set(compare.collect(t)),{'a/相同.sldprt','b/相同.sldprt'})

class GeometryTests(unittest.TestCase):
    def test_hi_cone_boundary_correspondence(self):
        circles=[(0,0,40,0,0,1,16.63),(0,0,39.097011,0,0,1,20)]
        self.assertTrue(add_cone.matches_end_cone(circles,2,40,20,3.37,0.902989,'hi'))
        flipped=[(0,0,40,0,0,1,20),(0,0,39.097011,0,0,1,16.63)]
        self.assertFalse(add_cone.matches_end_cone(flipped,2,40,20,3.37,0.902989,'hi'))

    def test_lo_cone_boundary_correspondence(self):
        circles=[(0,0,0,0,0,1,16.63),(0,0,.902989,0,0,1,20)]
        self.assertTrue(add_cone.matches_end_cone(circles,2,0,20,3.37,0.902989,'lo'))

    def test_cylinder_units(self):
        surface=NS(IsCylinder=lambda:True,CylinderParams=[.01,.02,.03,0.,0.,1.,.005])
        face=NS(GetSurface=lambda:surface)
        with patch.object(swlib,'mod',return_value=NS(ISurface=object)),patch.object(swlib,'wrap',side_effect=lambda cls,obj:obj):
            self.assertEqual(swlib.cyl_of(face),[10.,20.,30.,0.,0.,1.,5.])

    def test_axis_for_disc_not_bbox_longest(self):
        cylinders=[[0,0,0,0,0,1,50],[0,0,0,0,0,-1,10]]
        circles=[(0,0,0,0,0,1,50),(0,0,4,0,0,1,50)]
        with patch.object(swlib,'faces',return_value=cylinders),patch.object(swlib,'cyl_of',side_effect=lambda x:x),patch.object(swlib,'edges',return_value=circles),patch.object(swlib,'circle_of',side_effect=lambda x:x):
            self.assertEqual(swlib.axial_axis(object()),(2,0,4))

    def test_offset_or_tilted_axes_rejected(self):
        for cylinders in ([[0,0,0,.7071,0,.7071,10]],[[0,0,0,0,0,1,10],[1,0,0,0,0,1,5]]):
            with patch.object(swlib,'faces',return_value=cylinders),patch.object(swlib,'cyl_of',side_effect=lambda x:x):
                self.assertIsNone(swlib.axial_axis(object()))

    def test_metric_classification_does_not_claim_same_geometry(self):
        a={'volume':100,'faces':6,'bodies':1,'box_mm':[0,0,0,1,1,1],'features':[('Extrude','A',0)]}
        self.assertEqual(compare.classify(a,copy.deepcopy(a)),'NO_DIFFERENCE_DETECTED')
        b=copy.deepcopy(a);b['features']=[('Extrude','Renamed',0)]
        self.assertEqual(compare.classify(a,b),'FEATURES_DIFFER')
        b=copy.deepcopy(a);b['box_mm'][0]=.5
        self.assertEqual(compare.classify(a,b),'METRICS_DIFFER')

    def test_cone_keeps_requested_width_and_rejects_narrow_ring(self):
        # At R=10 with ring width=1, requested width=2 must fail before sketching.
        doc=NS(SketchManager=object(),FeatureManager=object())
        circles=[(0,0,z,0,0,1,r) for z in (0,20) for r in (9,10)]
        with patch.object(swlib,'model',return_value=doc),patch.object(swlib,'main_body',return_value=(object(),1)),patch.object(swlib,'axial_axis',return_value=(2,0,20)),patch.object(swlib,'faces',return_value=[object()]),patch.object(swlib,'cyl_of',return_value=[0,0,0,0,0,1,10]),patch.object(swlib,'edges',return_value=circles),patch.object(swlib,'circle_of',side_effect=lambda c:c):
            with self.assertRaisesRegex(ValueError,'exceeds end annulus'):
                add_cone.modify(object(),2,75,'hi')

class ComContractTests(unittest.TestCase):
    def test_body_selection_uses_native_select2_with_mark(self):
        data=NS(Mark=0)
        body=NS(Select2=Mock(return_value=True))
        doc=NS(SelectionManager=NS(CreateSelectData=lambda:data))
        with patch.object(swlib,'mod',return_value=NS(ISelectionMgr=object,IBody2=object)),patch.object(swlib,'wrap',side_effect=lambda cls,obj:obj),patch.object(swlib,'model',return_value=doc):
            self.assertTrue(swlib.select_body_mark(doc,body,256,True))
        self.assertEqual(data.Mark,256)
        body.Select2.assert_called_once_with(True,data)

    def test_save_errors_propagate(self):
        for result in ((False,0,0),(True,2,0)):
            with self.assertRaises(RuntimeError):swlib._save_result(result,'Save')
        swlib._save_result((True,0,0),'Save')

    def test_reject_open_user_document_without_closing(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'p.SLDPRT';p.touch()
            sw=NS(GetOpenDocumentByName=lambda _:object(),CloseDoc=Mock())
            with self.assertRaisesRegex(RuntimeError,'already open'):
                with swlib.owned_doc(sw,p):pass
            sw.CloseDoc.assert_not_called()

    def test_owned_document_closes_on_exception(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'p.SLDPRT';p.touch()
            sw=NS(GetOpenDocumentByName=lambda _:None,CloseDoc=Mock())
            with patch.object(swlib,'open_doc',return_value='raw'),patch.object(swlib,'model',return_value=NS(GetTitle=lambda:'owned')):
                with self.assertRaisesRegex(RuntimeError,'bad geometry'):
                    with swlib.owned_doc(sw,p):raise RuntimeError('bad geometry')
            sw.CloseDoc.assert_called_once_with('owned')

    def test_open_type_errors_and_warnings(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'p.SLDASM';p.touch()
            sw=NS(OpenDoc6=Mock(return_value=('raw',0,4)))
            with self.assertWarns(UserWarning):self.assertEqual(swlib.open_doc(sw,p,readonly=True),'raw')
            self.assertEqual(sw.OpenDoc6.call_args.args[1:3],(2,3))
            sw.OpenDoc6.return_value=(None,8,0)
            with self.assertRaisesRegex(RuntimeError,'errors=8'):swlib.open_doc(sw,p)

    def test_part_output_readback_failure_never_publishes(self):
        with tempfile.TemporaryDirectory() as t:
            src=Path(t)/'source.SLDPRT';src.write_bytes(b'original')
            dst=Path(t)/'result.SLDPRT'
            @contextmanager
            def owned(*a,**kw):yield object()
            with patch.object(swlib,'owned_doc',owned),patch.object(swlib,'total_volume',return_value=42),patch.object(swlib,'verify_volume_file',side_effect=RuntimeError('disk mismatch')):
                with self.assertRaisesRegex(RuntimeError,'disk mismatch'):
                    with swlib.part_output(NS(GetOpenDocumentByName=lambda _:None,GetCurrentWorkingDirectory=lambda:t,SetCurrentWorkingDirectory=lambda _:True),src,dst) as (_,stage):Path(stage).write_bytes(b'modified')
            self.assertFalse(dst.exists())
            self.assertEqual(src.read_bytes(),b'original')

    def test_feature_cycle_is_bounded(self):
        class Feature:
            Name='cycle'
            def GetTypeName2(self):return 'Test'
            def GetFirstSubFeature(self):return self
            def GetNextSubFeature(self):return self
        with patch.object(swlib,'mod',return_value=NS(IFeature=object)),patch.object(swlib,'wrap',side_effect=lambda cls,obj:obj):
            with self.assertRaises(RuntimeError):
                swlib.walk_features(NS(FirstFeature=lambda:Feature()),limit=10)

class GuiTests(unittest.TestCase):
    def test_ambiguous_green_regions_rejected(self):
        from PIL import Image,ImageDraw
        im=Image.new('RGB',(140,140),'white');d=ImageDraw.Draw(im)
        d.rectangle((10,10,20,20),fill=(20,130,30))
        d.rectangle((80,80,90,90),fill=(20,130,30))
        self.assertIsNone(gui_helper.find_button(im,region=(0,0,140,140)))

    def test_confirm_does_not_click_by_default(self):
        with patch.object(gui_helper,'find_button',return_value=(10,20,50)),patch.object(gui_helper,'click') as click:
            self.assertEqual(gui_helper.confirm(im=object()),(False,(10,20,50)))
            click.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
