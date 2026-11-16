from pathlib import Path
import pythoncom
import win32com.client.gencache as gc
import win32com.client.makepy as makepy
def constants():
    import swlib
    tlb=pythoncom.LoadTypeLib(str(Path(swlib._tlb_path()).with_name('swconst.tlb')))
    a=tlb.GetLibAttr()
    m=gc.EnsureModule(str(a[0]),a[1],a[3],a[4])
    if m is None:
        makepy.GenerateFromTypeLibSpec(tlb,bForDemand=False)
        m=gc.GetModuleForTypelib(str(a[0]),a[1],a[3],a[4])
    return m.constants
if __name__=='__main__':
    import sys
    c=constants()
    for n in dir(c):
        if any(x.lower() in n.lower() for x in sys.argv[1:]):print(n,getattr(c,n))
