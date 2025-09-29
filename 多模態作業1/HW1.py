#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DIP HW1 — 單檔可執行：讀檔+中心10x10、點運算（negative/log/gamma）、重採樣（NN/Bilinear）
from __future__ import annotations
import os, sys, struct, math, csv, argparse
from dataclasses import dataclass
from typing import List

# ---------- Core ----------
'''等於以下寫法'''
#def __init__(self, w: int, h: int, pix: bytearray):
#    self.w = w
#    self.h = h
#    self.pix = pix

@dataclass
class Image:
    w: int
    h: int
    pix: bytearray  # row-major uint8
    def get(self,x:int,y:int)->int:             #取某格陣列的值
        return self.pix[y*self.w+x]
    def set(self,x:int,y:int,v:int)->None:      #設定某陣列為v
        self.pix[y*self.w+x]=v&0xFF             #0x:16進位   &0xFF強制0-255

# ---------- RAW 512x512 ----------
RAW_W=512; RAW_H=512; RAW_BYTES=RAW_W*RAW_H
def load_raw_512(path:str)->Image:
    b=open(path,'rb').read()                    #bytes物件=不可改的byte序列 0-255(預設16進位) '\x00\x10...'  一維
    if len(b)!=RAW_BYTES:                       #len() 檔案大小
        raise ValueError(f"RAW size mismatch: {len(b)}")  #f=formatted string: {變數}間不用再打+ 
    return Image(RAW_W,RAW_H,bytearray(b))      #bytearray可改值 一維

# ---------- BMP (8/24bit, BI_RGB) 讀成灰階 ----------
@dataclass
class _BMPHeader:
    file_size:int; off_bits:int; dib_size:int; width:int; height:int
    planes:int; bit_count:int; compression:int; size_image:int
    xppm:int; yppm:int; clr_used:int; clr_important:int

def load_bmp_gray(path:str)->Image:
    b=open(path,'rb').read()                    #read讀出來會是byte序列 不可改 要改成bytearray
    if b[:2]!=b'BM': raise ValueError("Not BMP")
    # ★ 正確解析 BITMAPFILEHEADER：IHHI（不是 IHI）
    file_size, _r1, _r2, off_bits = struct.unpack_from('<IHHI', b, 2)
    dib_size = struct.unpack_from('<I', b, 14)[0]
    if dib_size<40: raise ValueError("DIB<40")
    (width, height, planes, bit_count, compression, size_image,
     xppm, yppm, clr_used, clr_important) = struct.unpack_from('<iiHHIIIIII', b, 18)
    hdr=_BMPHeader(file_size,off_bits,dib_size,width,abs(height),planes,
                   bit_count,compression,size_image,xppm,yppm,clr_used,clr_important)
    if compression!=0: raise ValueError("Compressed BMP not supported")
    flip = (height>0)
    if bit_count==24:
        stride=((hdr.width*3+3)//4)*4
        pix=bytearray(hdr.width*hdr.height)
        for r in range(hdr.height):
            src_r=(hdr.height-1-r) if flip else r
            base=off_bits+src_r*stride
            for x in range(hdr.width):
                B=b[base+3*x+0]; G=b[base+3*x+1]; R=b[base+3*x+2]
                Y=int(0.114*B+0.587*G+0.299*R+0.5)
                pix[r*hdr.width+x]=Y
        return Image(hdr.width,hdr.height,pix)
    elif bit_count==8:
        pal_sz=clr_used or 256
        pal_off=14+dib_size
        palette=b[pal_off:pal_off+4*pal_sz]  # BGRA
        stride=((hdr.width+3)//4)*4
        pix=bytearray(hdr.width*hdr.height)
        for r in range(hdr.height):
            src_r=(hdr.height-1-r) if flip else r
            base=off_bits+src_r*stride
            for x in range(hdr.width):
                idx=b[base+x]
                B,G,R,_=palette[4*idx:4*idx+4]
                Y=int(0.114*B+0.587*G+0.299*R+0.5)
                pix[r*hdr.width+x]=Y
        return Image(hdr.width,hdr.height,pix)
    else:
        raise ValueError(f"Unsupported BMP bit depth: {bit_count}")

# ---------- 儲存 ----------
def save_bmp_gray(path:str,img:Image)->None:
    w,h=img.w,img.h; stride=((w+3)//4)*4
    size_pixels=stride*h; size_palette=256*4
    off_bits=14+40+size_palette; file_size=off_bits+size_pixels
    head=bytearray(); head+=b'BM'; head+=struct.pack('<IHHI',file_size,0,0,off_bits)
    info=struct.pack('<IIIHHIIIIII',40,w,h,1,8,0,size_pixels,2835,2835,256,256)
    palette=bytearray().join(bytes((i,i,i,0)) for i in range(256))  # 256-level灰階
    pix=bytearray(stride*h)
    for y in range(h):
        dst=h-1-y; base=dst*stride
        line=img.pix[y*w:(y+1)*w]; pix[base:base+w]=line
    with open(path,'wb') as f: f.write(head); f.write(info); f.write(palette); f.write(pix)

def save_center_csv(path:str, mat:List[List[int]])->None:
    os.makedirs(os.path.dirname(path),exist_ok=True)
    with open(path,'w',newline='',encoding='utf-8') as f:
        csv.writer(f).writerows(mat)

# ---------- 小工具 ----------
def list_images(folder:str)->List[str]:
    exts={'.bmp','.BMP','.raw'}
    out=[os.path.join(folder,n) for n in os.listdir(folder) if os.path.splitext(n)[1] in exts]
    out.sort(); return out

def load_any(path:str)->Image:
    ext=os.path.splitext(path)[1].lower()
    return load_raw_512(path) if ext=='.raw' else load_bmp_gray(path)

def center_10x10(img:Image)->List[List[int]]:
    cx,cy=img.w//2,img.h//2; sx,sy=cx-5,cy-5
    M=[]; 
    for j in range(10):
        row=[]
        for i in range(10):
            x=min(max(sx+i,0),img.w-1); y=min(max(sy+j,0),img.h-1)
            row.append(img.get(x,y))
        M.append(row)
    return M

# ---------- 點運算 ----------
def op_negative(img:Image)->Image: return Image(img.w,img.h,bytearray(255-v for v in img.pix))
def op_log(img:Image)->Image:
    c=255.0/math.log(1+255.0); return Image(img.w,img.h,bytearray(
        min(255,int(c*math.log(1+v)+0.5)) for v in img.pix))
def op_gamma(img:Image,gamma:float)->Image:
    inv=1.0/255.0; out=bytearray()
    for v in img.pix:
        y=int(255.0*(v*inv)**gamma+0.5); out.append(0 if y<0 else (255 if y>255 else y))
    return Image(img.w,img.h,out)

# ---------- 重採樣 ----------
def resize_nn(img:Image,W:int,H:int)->Image:
    sx=img.w/W; sy=img.h/H; out=bytearray(W*H)
    for y in range(H):
        yy=int((y+0.5)*sy-0.5); yy=max(0,min(img.h-1,yy))
        for x in range(W):
            xx=int((x+0.5)*sx-0.5); xx=max(0,min(img.w-1,xx))
            out[y*W+x]=img.get(xx,yy)
    return Image(W,H,out)

def resize_bilinear(img:Image,W:int,H:int)->Image:
    sx=img.w/W; sy=img.h/H; out=bytearray(W*H)
    for y in range(H):
        fy=(y+0.5)*sy-0.5; y0=int(math.floor(fy)); y1=y0+1
        wy1=fy-y0; wy0=1-wy1; y0=max(0,min(img.h-1,y0)); y1=max(0,min(img.h-1,y1))
        for x in range(W):
            fx=(x+0.5)*sx-0.5; x0=int(math.floor(fx)); x1=x0+1
            wx1=fx-x0; wx0=1-wx1; x0=max(0,min(img.w-1,x0)); x1=max(0,min(img.w-1,x1))
            v00=img.get(x0,y0); v01=img.get(x1,y0); v10=img.get(x0,y1); v11=img.get(x1,y1)
            v0=v00*wx0+v01*wx1; v1=v10*wx0+v11*wx1; v=int(v0*wy0+v1*wy1+0.5)
            out[y*W+x]=0 if v<0 else (255 if v>255 else v)
    return Image(W,H,out)

# ---------- 任務 ----------
def task_a(data_dir:str,out_dir:str)->None:
    os.makedirs(out_dir,exist_ok=True)
    for p in list_images(data_dir):
        img=load_any(p); base=os.path.splitext(os.path.basename(p))[0]
        save_bmp_gray(os.path.join(out_dir,f'a_view_{base}.bmp'), img)
        save_center_csv(os.path.join(out_dir,f'a_center_{base}.csv'), center_10x10(img))
        print('[a] done', base)

def task_b(data_dir:str,out_dir:str,gammas:List[float])->None:
    os.makedirs(out_dir,exist_ok=True)
    for p in list_images(data_dir):
        img=load_any(p); base=os.path.splitext(os.path.basename(p))[0]
        save_bmp_gray(os.path.join(out_dir,f'b_negative_{base}.bmp'), op_negative(img))
        save_bmp_gray(os.path.join(out_dir,f'b_log_{base}.bmp'), op_log(img))
        for g in gammas:
            save_bmp_gray(os.path.join(out_dir,f'b_gamma{g:.2f}_{base}.bmp'), op_gamma(img,g))
        print('[b] done', base)

def task_c(data_dir:str,out_dir:str)->None:
    os.makedirs(out_dir,exist_ok=True)
    cases=[((512,512),(128,128),'512to128'),
           ((512,512),(32,32),'512to32'),
           ((32,32),(512,512),'32to512'),
           ((512,512),(1024,512),'512to1024x512'),
           ((128,128),(256,512),'128to256x512')]
    for p in list_images(data_dir):
        img0=load_any(p); base=os.path.splitext(os.path.basename(p))[0]
        nn32=resize_nn(img0,32,32); nn128=resize_nn(img0,128,128)
        for src_size,dst_size,tag in cases:
            src=img0 if src_size==(512,512) else (nn32 if src_size==(32,32) else nn128)
            save_bmp_gray(os.path.join(out_dir,f'c_nn_{tag}_{base}.bmp'),
                          resize_nn(src,dst_size[0],dst_size[1]))
            save_bmp_gray(os.path.join(out_dir,f'c_bilinear_{tag}_{base}.bmp'),
                          resize_bilinear(src,dst_size[0],dst_size[1]))
        print('[c] done', base)

# ---------- CLI & no-args 預設 ----------
def build_cli():
    p=argparse.ArgumentParser(description="DIP HW1")
    sub=p.add_subparsers(dest='cmd', required=False)
    pa=sub.add_parser('a'); pa.add_argument('--data', required=True); pa.add_argument('--out', required=True)
    pb=sub.add_parser('b'); pb.add_argument('--data', required=True); pb.add_argument('--out', required=True)
    pb.add_argument('--gamma', nargs='*', type=float, default=[0.5,1.0,2.0])
    pc=sub.add_parser('c'); pc.add_argument('--data', required=True); pc.add_argument('--out', required=True)
    return p

def run_defaults_here():
    if getattr(sys, 'frozen', False):  # 如果是 exe 模式
        here = os.path.dirname(sys.executable)
    else:                              # 如果是 py 模式
        here = os.path.dirname(os.path.abspath(__file__))

    task_a(here, os.path.join(here,'out','a'))
    task_b(here, os.path.join(here,'out','b'), [0.5, 1.0, 2.0])
    task_c(here, os.path.join(here,'out','c'))

def main(argv:List[str])->int:
    if not argv:            # ★ 沒有參數 → 直接用當前夾跑完 a/b/c
        run_defaults_here(); return 0
    args=build_cli().parse_args(argv)
    if args.cmd=='a': task_a(args.data,args.out)
    elif args.cmd=='b': task_b(args.data,args.out,args.gamma)
    elif args.cmd=='c': task_c(args.data,args.out)
    else: print("需要子命令 a/b/c"); return 1
    return 0



if __name__=='__main__': raise SystemExit(main(sys.argv[1:]))
