"""Inspect all part bodies; for assembly/drawing report tree only."""
import argparse
import sys
import swlib

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('file')
    ap.add_argument('--features',action='store_true')
    ap.add_argument('--edges',action='store_true')
    args = ap.parse_args()
    sw = swlib.app()
    with swlib.owned_doc(sw,args.file) as raw:
        doc = swlib.model(raw)
        print(doc.GetTitle())
        if args.features:
            for t,n,d in swlib.walk_features(doc):
                print('  '*d,t,n)
        if doc.GetType() != 1:
            print('Geometry adapter not implemented for assemblies/drawings')
            return 1
        bs = swlib.bodies(raw)
        print('Bodies:',len(bs),'total volume mm3:',swlib.total_volume(raw),'total faces:',swlib.total_faces(raw))
        for i,body in enumerate(bs,1):
            box = [v*1000 for v in body.GetBodyBox()]
            print('Body',i,'bbox mm [xmin,ymin,zmin,xmax,ymax,zmax]:',box)
            print('volume mm3:',swlib.volume(body),'faces:',len(swlib.faces(body)),'axis hint:',swlib.axial_axis(body))
            for face in swlib.faces(body):
                cyl,cone = swlib.cyl_of(face),swlib.cone_of(face)
                if cyl:
                    print('Cylinder [origin mm, axis unitless, radius mm]:',cyl)
                if cone:
                    print('Cone [origin mm, axis unitless, half angle deg, reference radius mm]:',cone)
            if args.edges:
                for edge in swlib.edges(body):
                    c = swlib.circle_of(edge)
                    if c:
                        print('Circle [center mm, axis unitless, radius mm]:',c)
    return 0

if __name__ == '__main__':
    sys.exit(main())
