import sys, json, re, tts2, asr
from script import SCENES
def norm(s):
    s=re.sub(r'[^א-ת0-9]','',s)
    for a,b in (('ך','כ'),('ם','מ'),('ן','נ'),('ף','פ'),('ץ','צ'),('ט','ת'),('כ','ק'),('ע','א'),('ו',''),('י',''),('ה','')): s=s.replace(a,b)
    return s
def cer(r,h):
    r,h=norm(r),norm(h); d=list(range(len(h)+1))
    for i,c in enumerate(r,1):
        p=d[:]; d[0]=i
        for j,e in enumerate(h,1): d[j]=min(p[j]+1,d[j-1]+1,p[j-1]+(c!=e))
    return d[-1]/max(1,len(r))
def run(voice, cfg, tag, rate=1.0, verbose=True):
    tts2.CFG.update(cfg); tot=0; out=[]
    for sid,s in SCENES:
        heb=' '.join(t.split('|')[0] for t in s.split()).replace('1.','אחת.').replace('2.','שתיים.').replace('3.','שלוש.'); phon=' '.join(t.split('|')[1] for t in s.split())
        tts2.synth(phon,'/tmp/e.wav',voice=voice,rate=rate)
        h=asr.tx('/tmp/e.wav'); c=cer(heb,h); tot+=c; out.append((sid,round(c,2),h))
    print(tag,voice,'MEAN CER',round(tot/len(SCENES),3))
    if verbose:
        for o in out: print('  ',o)
    return tot/len(SCENES)
if __name__=='__main__':
    base=dict(stop=62,fric=78,son=54,nas=54,vow=72,svow=108,fall=0.80,endp=200)
    slow=dict(stop=84,fric=92,son=64,nas=72,vow=76,svow=112,fall=0.88,endp=450)
    for v in ('hb1','hb2'):
        run(v,base,'base'); run(v,slow,'slow')
