"""Render every final PDF page and validate text, images and page bounds."""
from pathlib import Path
import hashlib,json,subprocess,shutil
import pymupdf as fitz
from PIL import Image,ImageOps,ImageDraw
R=Path(__file__).resolve().parents[1];D=R/'deliverables';T=R/'tmp/pdfs';T.mkdir(parents=True,exist_ok=True)
def main():
    summary=[]
    poppler=shutil.which('pdftoppm')
    if not poppler:raise RuntimeError('pdftoppm is required for visual QA')
    for filename in ['Jury2_Three_Dashboard_Evidence.pdf','Jury2_Healthcare_Intelligence_Implementation_Report.pdf']:
        path=D/filename;doc=fitz.open(path);stem='evidence' if 'Evidence' in filename else 'report'
        prefix=T/stem
        for old in T.glob(stem+'-*.png'):
            assert old.resolve().parent==T.resolve()
            old.unlink()
        subprocess.run([poppler,'-r','85','-png',str(path),str(prefix)],check=True,capture_output=True)
        pages=[];fulltext=''
        for n,page in enumerate(doc):
            text=page.get_text();fulltext+=text
            boxes=[]
            for block in page.get_text('dict')['blocks']:
                x0,y0,x1,y1=block['bbox']
                if x0 < -1 or y0 < -1 or x1>page.rect.width+1 or y1>page.rect.height+1:boxes.append([x0,y0,x1,y1])
            assert not boxes,(filename,n+1,boxes)
            assert len(text.strip())>60 or page.get_images(),(filename,n+1,'empty page')
            assert '\ufffd' not in text,(filename,n+1,'replacement character')
            pages.append({'page':n+1,'characters':len(text),'images':len(page.get_images()),'out_of_bounds':boxes})
        if stem=='report':
            for chapter in range(1,15):assert f'Chapter {chapter} -' in fulltext,(chapter,'missing chapter')
            for term in ['Abstract','Contents','References','0.43302','0.65031','Registration number']:assert term in fulltext,term
            assert len(doc.get_toc())>=15,'missing document navigation'
        else:
            assert sum(bool(p['images']) for p in pages)>=5
            for term in ['Pattern Matching','Five-Model','Selected Best Classifier']:assert term in fulltext,term
        pngs=sorted(T.glob(stem+'-*.png'))
        for start in range(0,len(pngs),12):
            subset=pngs[start:start+12];sheet=Image.new('RGB',(900,4*340),(226,233,236));draw=ImageDraw.Draw(sheet)
            for i,file in enumerate(subset):
                thumb=Image.open(file).convert('RGB');thumb.thumbnail((280,305))
                x=(i%3)*300+(300-thumb.width)//2;y=(i//3)*340+20
                sheet.paste(thumb,(x,y));draw.text(((i%3)*300+10,(i//3)*340+325),file.name,fill='black')
            sheet.save(T/f'{stem}_contact_{start//12+1}.jpg')
        summary.append({'file':filename,'pages':len(doc),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'all_pages_rendered':True,'text_and_bounds_pass':True,'page_details':pages})
    (D/'logs/pdf_validation.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps([{k:v for k,v in x.items() if k!='page_details'} for x in summary],indent=2))
if __name__=='__main__':main()
