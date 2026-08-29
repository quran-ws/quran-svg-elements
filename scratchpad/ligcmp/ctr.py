import os,sys,io,re,contextlib,math
sys.path.insert(0,'tools'); os.environ.setdefault('QSVG_ROOT',os.getcwd())
import xml.etree.ElementTree as ET
NS='{http://www.w3.org/2000/svg}'
_TOK=re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(-?(?:\d+\.?\d*|\.\d+)(?:[eE]-?\d+)?)")
_NARG=dict(M=2,L=2,H=1,V=1,C=6,S=4,Q=4,T=2,A=7,Z=0)

def subpaths(d):
    """[[(x,y),...],...] one list of on-curve+control points per subpath."""
    toks=[(m.group(1),m.group(2)) for m in _TOK.finditer(d)]
    i=0;cmd=None;x=y=sx=sy=0.0;out=[];cur=None
    while i<len(toks):
        if toks[i][0]:
            cmd=toks[i][0];i+=1
            if cmd in 'Zz':
                x,y=sx,sy;continue
        if cmd is None: break
        n=_NARG[cmd.upper()];a=[]
        while len(a)<n and i<len(toks) and toks[i][1] is not None:
            a.append(float(toks[i][1]));i+=1
        if len(a)<n: break
        rel,c=cmd.islower(),cmd.upper()
        if c=='M':
            x,y=(x+a[0],y+a[1]) if rel else (a[0],a[1]); sx,sy=x,y
            cur=[(x,y)];out.append(cur);cmd='l' if rel else 'L';continue
        if cur is None: cur=[(x,y)];out.append(cur)
        if c=='L': x,y=(x+a[0],y+a[1]) if rel else (a[0],a[1])
        elif c=='H': x=x+a[0] if rel else a[0]
        elif c=='V': y=y+a[0] if rel else a[0]
        elif c in 'CSQT':
            pts=[(a[j],a[j+1]) for j in range(0,len(a),2)]
            for px,py in pts: cur.append((x+px,y+py) if rel else (px,py))
            x,y=(x+pts[-1][0],y+pts[-1][1]) if rel else pts[-1]
            continue
        elif c=='A': x,y=(x+a[5],y+a[6]) if rel else (a[5],a[6])
        cur.append((x,y))
    return [s for s in out if len(s)>1]

def mat(s):
    m=re.match(r'\s*matrix\(([^)]*)\)',s or '')
    if m:
        v=[float(t) for t in re.split(r'[\s,]+',m.group(1).strip())]
        return tuple(v[:6])
    m=re.match(r'\s*translate\(([^)]*)\)',s or '')
    if m:
        v=[float(t) for t in re.split(r'[\s,]+',m.group(1).strip())]
        return (1,0,0,1,v[0],v[1] if len(v)>1 else 0)
    m=re.match(r'\s*scale\(([^)]*)\)',s or '')
    if m:
        v=[float(t) for t in re.split(r'[\s,]+',m.group(1).strip())]
        return (v[0],0,0,v[1] if len(v)>1 else v[0],0,0)
    return (1,0,0,1,0,0)

def mul(A,B):
    a,b,c,d,e,f=A; g,h,i,j,k,l=B
    return (a*g+c*h, b*g+d*h, a*i+c*j, b*i+d*j, a*k+c*l+e, b*k+d*l+f)

def apply(M,p):
    a,b,c,d,e,f=M; x,y=p
    return (a*x+c*y+e, b*x+d*y+f)

def walk(node, M, wordkey, out, wordattr):
    for ch in node:
        tag=ch.tag.split('}')[-1]
        M2=mul(M,mat(ch.get('transform'))) if ch.get('transform') else M
        if tag=='g':
            wk=wordattr(ch)
            walk(ch,M2,wk if wk is not None else wordkey,out,wordattr)
        elif tag=='path' and ch.get('d'):
            for sp in subpaths(ch.get('d')):
                out.append((wordkey,[apply(M2,p) for p in sp]))
