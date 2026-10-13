"""Generate editable Visio XML and matching SVG previews using only Python."""
from pathlib import Path
import html
import textwrap
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
NS = "http://schemas.microsoft.com/visio/2003/core"
ET.register_namespace("", NS)


def element(parent, tag, value=None, **attrs):
    child = ET.SubElement(parent, "{" + NS + "}" + tag, {k: str(v) for k, v in attrs.items()})
    if value is not None:
        child.text = str(value)
    return child


PAGES = []


def page(name, subtitle):
    p = {"name": name, "subtitle": subtitle, "nodes": [], "edges": []}
    PAGES.append(p)
    return p


def box(p, key, text, x, y, w=3.8, h=.85, kind="process"):
    p["nodes"].append(dict(key=key, text=text, x=x, y=y, w=w, h=h, kind=kind))


def edge(p, a, b, label="", side_a="bottom", side_b="top", via=None):
    p["edges"].append((a, b, label, side_a, side_b, via or []))


p = page("01 Overall flow", "AI-FCM Bedrock v1.3.0 | Current implementation | 28 September 2026")
box(p,"start","START: Select PDF, DOCX or TXT",5,1.65,kind="start")
box(p,"read","Extract embedded text; preserve page markers. Apply configured text limit.",5,2.95)
box(p,"ready","Readable text and connection settings ready?",5,4.3,h=1.1,kind="decision")
box(p,"input_error","Show input/configuration error. Correct input and try again.",10,4.3,w=3,kind="failed")
box(p,"send","User selects Extract fields. Send text and shared extraction prompt to Bedrock.",5,5.75)
box(p,"ai","AI returns section values, separate Special Instructions, and provider records as JSON.",5,7.1,h=1.05,kind="ai")
box(p,"valid","Parse and normalize output (pages 2-3). Accepted JSON and field types?",5,8.65,h=1.2,kind="decision")
box(p,"retry","First invalid response?",10,8.65,w=3,h=1.1,kind="decision")
box(p,"again","Retry once with a complete-JSON reminder.",10,6.5,w=3)
box(p,"error","Show extraction error. No completed result.",10,10.45,w=3,kind="failed")
box(p,"check","Compute completeness and NEXT STEP (page 4). Missing facts do not trigger a retry.",5,10.45,h=1.05)
box(p,"out","Display five sections + four optional extras. Export grouped JSON, CSV or TXT.",5,12,h=1.05)
box(p,"end","END: Human reviews results. No automatic CMS handoff.",5,13.6,h=.95,kind="start")
box(p,"notes","AI interprets document context; Python validates structure, applies fallback and checks completeness.\n\nPDF extraction uses embedded text, not OCR. API/transport failures surface as errors; malformed-output retry is separate from client transport retries.",10,13,w=3.1,h=2.5,kind="note")
for a,b in [("start","read"),("read","ready"),("send","ai"),("ai","valid"),("check","out"),("out","end")]: edge(p,a,b)
edge(p,"ready","send","Yes")
edge(p,"ready","input_error","No","right","left")
edge(p,"valid","check","Yes")
edge(p,"valid","retry","No","right","left")
edge(p,"retry","again","Yes","top","bottom")
edge(p,"again","ai","Re-send","left","right",[(7.6,6.5),(7.6,7.1)])
edge(p,"retry","error","No")

p=page("02 Section priority", "Scalar fields | Model separates sources; Python resolves permitted missing values")
box(p,"start","For each scalar field: read named-section value from model JSON.",4.5,1.85)
box(p,"exists","Primary value present?",4.5,3.35,h=1.1,kind="decision")
box(p,"keep","Keep primary value. Never overwrite it with Special Instructions.",9.5,3.35,w=3.4,kind="passed")
box(p,"allowed","Special Instructions fallback allowed for this field?",4.5,5.15,h=1.3,kind="decision")
box(p,"missing","Use Not found",9.5,5.15,w=3.4,kind="note")
box(p,"fallback","Special Instructions value present?",4.5,7,h=1.1,kind="decision")
box(p,"use","Use Special Instructions value",4.5,8.7,kind="process")
box(p,"next","Keep role-specific fields separate; reject emails used as phone numbers. Continue to next field.",4.5,10.3,h=1.1)
box(p,"blocked","NO FALLBACK\nAll claimant/customer fields\nClaim Number, Claim ID, Claim Type",3.4,12.8,w=4.6,h=1.5,kind="note")
box(p,"whitelist","FALLBACK ALLOWED\nInjury date, jurisdiction, accident description, injury description, diagnosis code\nAll case manager fields\nAttorney + referral metadata\nProviders: see page 3",9,12.8,w=4.8,h=2.2,kind="note")
box(p,"note","Optional does not mean fallback is allowed: claimant Address-line-2 is optional but never uses Special Instructions. Missing/null/unknown values normalize to Not found. Identifiers remain strings.",9.5,8.9,w=3.4,h=2.3,kind="note")
edge(p,"start","exists")
edge(p,"exists","keep","Yes","right","left")
edge(p,"exists","allowed","No")
edge(p,"allowed","missing","No","right","left")
edge(p,"allowed","fallback","Yes")
edge(p,"fallback","use","Yes")
edge(p,"fallback","missing","No","right","bottom",[(7.1,7),(9.5,7)])
edge(p,"use","next")
edge(p,"keep","next","Next field","right","left",[(11.6,3.35),(11.6,11.2),(1.9,11.2),(1.9,10.3)])
edge(p,"missing","next","Next field","right","right",[(11.4,5.15),(11.4,10.3)])

p=page("03 Provider processing", "Primary-section records first, followed by Special Instructions records")
box(p,"start","For each provider record: validate required keys and normalize values.",4.6,1.85)
box(p,"phone","Phone contains @? Replace with Not found. Keep dates/times tied to their provider.",4.6,3.2)
box(p,"skip","All values missing OR exact duplicate of a retained record?",4.6,4.75,h=1.25,kind="decision")
box(p,"drop","Skip this record",9.5,4.75,w=3.2,kind="note")
box(p,"match","Exactly one compatible retained record with the same name?",4.6,6.65,h=1.3,kind="decision")
box(p,"new","Keep as separate record. Do not merge ambiguous or conflicting records.",9.5,6.65,w=3.2,h=1.15)
box(p,"merge","Fill only missing values in the retained record. Keep existing values.",4.6,8.45,h=1)
box(p,"more","More input records?",4.6,10.05,h=1.1,kind="decision")
box(p,"sort","Sort retained records by populated requested fields, most complete first.",4.6,11.65)
box(p,"end","Keep all retained providers. Preserve records in JSON and aligned slots in CSV/TXT.",4.6,13.05,h=1,kind="start")
box(p,"note","COMPATIBLE means:\nNon-missing names match, ignoring case.\nEvery provider value either matches or is missing on one side.\nConflicting phone, location or appointment data prevents merging.\n\nCompleteness uses seven requested fields; provider street address and Doctor/Facility classification do not add to the score.",9.6,11.7,w=3.4,h=3.1,kind="note")
edge(p,"start","phone")
edge(p,"phone","skip")
edge(p,"skip","drop","Yes","right","left")
edge(p,"skip","match","No")
edge(p,"match","new","No","right","left")
edge(p,"match","merge","Yes")
edge(p,"merge","more")
edge(p,"drop","more","Next","right","right",[(11.5,4.75),(11.5,9.15),(7,9.15),(7,10.05)])
edge(p,"new","more","Next","bottom","right",[(9.5,9.4),(7.1,9.4),(7.1,10.05)])
edge(p,"more","phone","Yes","left","left",[(1.5,10.05),(1.5,3.2)])
edge(p,"more","sort","No")
edge(p,"sort","end")

p=page("04 NEXT STEP", "Completeness of extracted information | Not a confidence score or factual verification")
box(p,"start","Evaluate normalized extraction results",4.5,1.8,kind="start")
box(p,"scalar","List every missing non-optional scalar field.",4.5,3.15)
box(p,"provider","At least one provider has all seven requested fields?",4.5,4.75,h=1.25,kind="decision")
box(p,"gaps","Add missing fields from the provider with the fewest gaps. If none: add all seven.",9.5,4.75,w=3.3,h=1.3)
box(p,"empty","Missing required-field list empty?",4.5,6.65,h=1.2,kind="decision")
box(p,"passed","NEXT STEP: Passed\nRequired information complete",3.4,8.5,w=3.6,h=1.05,kind="passed")
box(p,"failed","NEXT STEP: Failed\nDisplay missing required fields",8.7,8.5,w=3.6,h=1.05,kind="failed")
box(p,"display","Keep results available for review/export in either case. JSON also lists gaps for every provider.",6,10.35,w=5.8,h=1.1)
box(p,"optional","OPTIONAL / NOT GATING\nClaimant Address-line-2\nOffice Phone Number\nNurse Case Manager E-mail Address\nAll attorney + referral metadata\nFour legacy extras: nurse name, employer email, provider street address, Doctor/Facility classification",3.45,13,w=4.65,h=2.6,kind="note")
box(p,"required","PROVIDER: ALL SEVEN IN ONE RECORD\nProvider / Facility Name\nPhone Number\nCity, State, Zip\nAppointment Date, Appointment Time\n\nSeparate partial records cannot collectively satisfy this requirement. Other incomplete providers do not fail a referral if one is complete.",9,13,w=4.65,h=2.6,kind="note")
edge(p,"start","scalar")
edge(p,"scalar","provider")
edge(p,"provider","gaps","No","right","left")
edge(p,"provider","empty","Yes")
edge(p,"gaps","empty","Continue","bottom","right",[(9.5,6.65)])
edge(p,"empty","passed","Yes","left","top",[(2.1,6.65),(2.1,7.55),(3.4,7.55)])
edge(p,"empty","failed","No","bottom","top",[(4.5,7.5),(8.7,7.5)])
edge(p,"passed","display","","bottom","top",[(3.4,9.55),(6,9.55)])
edge(p,"failed","display","","bottom","top",[(8.7,9.75),(6,9.75)])

COLORS={"process":"#EAF2FB","ai":"#EDE7FA","decision":"#FFF2CC","passed":"#DFF2E5",
        "failed":"#FCE4E4","start":"#DDE8F0","note":"#F4F6F8","label":"#FFFFFF"}


def lines(node):
    return [line for paragraph in node["text"].split("\n") for line in (textwrap.wrap(paragraph, max(15,int(node["w"]*10))) or [""])]


def anchor(n, side):
    x,y=n["x"],n["y"]
    return {"top":(x,y-n["h"]/2),"bottom":(x,y+n["h"]/2),
            "left":(x-n["w"]/2,y),"right":(x+n["w"]/2,y)}[side]


def vis_shape(parent, ident, node):
    n=node
    s=element(parent,"Shape",ID=ident,NameU=n["key"],Type="Shape")
    xf=element(s,"XForm")
    for k,v in dict(PinX=n["x"],PinY=16-n["y"],Width=n["w"],Height=n["h"],LocPinX=n["w"]/2,LocPinY=n["h"]/2,Angle=0).items(): element(xf,k,v)
    line=element(s,"Line"); element(line,"LineWeight",.012); element(line,"LineColor","#40556B"); element(line,"LinePattern",0 if n["kind"]=="label" else 1)
    fill=element(s,"Fill"); element(fill,"FillForegnd",COLORS[n["kind"]]); element(fill,"FillPattern",1)
    textblock=element(s,"TextBlock"); element(textblock,"VerticalAlign",1)
    for k in ["LeftMargin","RightMargin","TopMargin","BottomMargin"]: element(textblock,k,.07)
    char=element(s,"Char",IX=0); element(char,"Font",0); element(char,"Size",.135 if n["kind"]=="note" else .15); element(char,"Color","#142B42")
    para=element(s,"Para",IX=0); element(para,"HorzAlign",1)
    w,h=n["w"],n["h"]
    points=[(w/2,h),(w,h/2),(w/2,0),(0,h/2),(w/2,h)] if n["kind"]=="decision" else [(0,0),(w,0),(w,h),(0,h),(0,0)]
    geom=element(s,"Geom",IX=0)
    for i,(x,y) in enumerate(points):
        row=element(geom,"MoveTo" if i==0 else "LineTo",IX=i+1); element(row,"X",x); element(row,"Y",y)
    element(s,"Text",n["text"])


def generate():
    root=ET.Element("{"+NS+"}VisioDocument",{"start":"190","metric":"0","DocLangID":"1033"})
    props=element(root,"DocumentProperties"); element(props,"Title","AI-FCM extraction logic v1.3.0"); element(props,"Creator","FCM Structured")
    fonts=element(root,"FaceNames"); element(fonts,"FaceName",ID=0,Name="Arial",UnicodeRanges="-1 -1 -1 -1",CharSets="0 0",Panose="2 11 6 4 2 2 2 2 2 4")
    pages=element(root,"Pages")
    for pi,p in enumerate(PAGES):
        vp=element(pages,"Page",ID=pi,NameU=p["name"],Name=p["name"])
        sheet=element(vp,"PageSheet"); pp=element(sheet,"PageProps"); element(pp,"PageWidth",12); element(pp,"PageHeight",16)
        shapes=element(vp,"Shapes")
        svg=['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="1280" viewBox="0 0 960 1280">',
             '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#40556B"/></marker></defs>',
             '<rect width="960" height="1280" fill="white"/>']
        headings=[dict(key="title",text=p["name"],x=6,y=.48,w=11,h=.5,kind="label"),
                  dict(key="subtitle",text=p["subtitle"],x=6,y=.94,w=11,h=.35,kind="label"),
                  dict(key="footer",text=f"FCM Structured | AI/referral_schema.py + AI/bedrock_core.py | Page {pi+1} of 4",x=6,y=15.65,w=11,h=.35,kind="label")]
        lookup={n["key"]:n for n in p["nodes"]}
        labels=[]
        for ei,(a,b,label,sa,sb,via) in enumerate(p["edges"]):
            pts=[anchor(lookup[a],sa)]+via+[anchor(lookup[b],sb)]
            s=element(shapes,"Shape",ID=100+ei,NameU=f"Connector.{ei}",Type="Shape")
            xf=element(s,"XForm")
            for k,v in dict(PinX=6,PinY=8,Width=12,Height=16,LocPinX=6,LocPinY=8,Angle=0).items(): element(xf,k,v)
            ln=element(s,"Line"); element(ln,"LineColor","#40556B"); element(ln,"LineWeight",.014); element(ln,"EndArrow",4)
            geom=element(s,"Geom",IX=0); element(geom,"NoFill",1)
            for i,(x,y) in enumerate(pts):
                row=element(geom,"MoveTo" if i==0 else "LineTo",IX=i+1); element(row,"X",x); element(row,"Y",16-y)
            svg.append('<polyline points="'+" ".join(f"{x*80},{y*80}" for x,y in pts)+'" fill="none" stroke="#40556B" stroke-width="1.4"/>')
            # Explicit triangles also render in PDF engines without SVG markers.
            ax,ay=pts[-2]; bx,by=pts[-1]
            norm=max(((bx-ax)**2+(by-ay)**2)**.5,.001)
            ux,uy=(bx-ax)/norm,(by-ay)/norm
            triangle=[(bx*80,by*80),(bx*80-ux*9-uy*4,by*80-uy*9+ux*4),
                      (bx*80-ux*9+uy*4,by*80-uy*9-ux*4)]
            svg.append('<polygon points="'+" ".join(f"{x},{y}" for x,y in triangle)+'" fill="#40556B"/>')
            if label:
                x,y=pts[0]; nx,ny=pts[1]; length=((nx-x)**2+(ny-y)**2)**.5
                ratio=min(.5,.38/max(length,.01))
                labels.append(dict(key=f"label{ei}",text=label,x=x+(nx-x)*ratio,y=y+(ny-y)*ratio,w=.78,h=.24,kind="label"))
        for ni,n in enumerate(p["nodes"]+headings+labels,1):
            vis_shape(shapes,ni,n)
            x,y,w,h=n["x"]*80,n["y"]*80,n["w"]*80,n["h"]*80
            fill=COLORS[n["kind"]]; stroke="none" if n["kind"]=="label" else "#40556B"
            if n["kind"]=="decision":
                svg.append(f'<polygon points="{x},{y-h/2} {x+w/2},{y} {x},{y+h/2} {x-w/2},{y}" fill="{fill}" stroke="{stroke}"/>')
            else:
                svg.append(f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" rx="{16 if n["kind"]=="start" else 3}" fill="{fill}" stroke="{stroke}"/>')
            ls=lines(n); fs=11 if n["kind"] in {"note","label"} else 12
            if n["key"]=="title": fs=24
            for j,t in enumerate(ls):
                svg.append(f'<text x="{x}" y="{y+(j-(len(ls)-1)/2)*14+4}" text-anchor="middle" font-family="Arial,sans-serif" font-size="{fs}" fill="#142B42">{html.escape(t)}</text>')
        svg.append('</svg>')
        (OUT/f"ai-flow-{pi+1}.svg").write_text("\n".join(svg),encoding="utf-8")
    ET.indent(root)
    ET.ElementTree(root).write(OUT/"AI-FCM-Current-Logic.vdx",encoding="utf-8",xml_declaration=True)
    preview='<!doctype html><html><head><meta charset="utf-8"><title>AI-FCM Current Logic</title><style>body{background:#e7edf3;font:16px Arial;margin:24px}main{max-width:960px;margin:auto}img{width:100%;display:block;margin:24px 0;box-shadow:0 3px 15px #aab}a{color:#174f87}@media print{body{margin:0;background:white}h1,p{display:none}img{break-after:page;margin:0;box-shadow:none}}</style></head><body><main><h1>AI-FCM extraction logic</h1><p>v1.3.0 · Four editable Visio pages · <a href="AI-FCM-Current-Logic.vdx">Download Visio XML</a></p>'
    preview+=''.join(f'<img src="ai-flow-{i+1}.svg" alt="{html.escape(p["name"])}">' for i,p in enumerate(PAGES))
    (OUT/"AI-FCM-Current-Logic.html").write_text(preview+'</main></body></html>',encoding="utf-8")
    print(f"Created {len(PAGES)} editable Visio pages and SVG/browser previews in {OUT}")


if __name__=="__main__":
    generate()
