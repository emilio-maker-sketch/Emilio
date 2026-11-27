import sys,glob,os
from PIL import Image,ImageDraw
fs=sys.argv[2:];out=sys.argv[1];n=len(fs);c=4;r=(n+c-1)//c;W=Image.new('RGB',(c*480,r*270))
for i,f in enumerate(fs):
    im=Image.open(f).convert('RGB');im.thumbnail((480,270));W.paste(im,((i%c)*480,(i//c)*270))
    ImageDraw.Draw(W).text(((i%c)*480+5,(i//c)*270+5),os.path.basename(f),fill=(255,255,0))
W.save(out,quality=80)
