"""Build two academic PDFs using actual outputs and genuine UI evidence.

ReportLab supplies layout; diagrams depict the implemented code architecture.
No screenshot is reconstructed or relabelled from a chart.
"""
from pathlib import Path
import json,re,sqlite3
from html import escape
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT,TA_JUSTIFY
from reportlab.lib.pagesizes import A4,A3,landscape
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Image,Table,TableStyle,KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents

R=Path(__file__).resolve().parents[1]; O=R/'jury_2_dw/outputs'; D=R/'deliverables'; E=D/'evidence'
BLUE=colors.HexColor('#153e56'); TEAL=colors.HexColor('#147b83'); GREY=colors.HexColor('#526674')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyJ',fontName='Helvetica',fontSize=9.7,leading=14,spaceAfter=8,alignment=TA_JUSTIFY,textColor=colors.HexColor('#203440')))
styles.add(ParagraphStyle(name='SmallText',fontSize=8,leading=11,spaceAfter=7,textColor=GREY))
styles.add(ParagraphStyle(name='CoverTitle',fontName='Helvetica-Bold',fontSize=25,leading=32,spaceAfter=18,textColor=BLUE))
styles.add(ParagraphStyle(name='Kicker',fontName='Helvetica-Bold',fontSize=10,leading=14,spaceAfter=12,textColor=TEAL))
styles.add(ParagraphStyle(name='TableHeader',parent=styles['SmallText'],textColor=colors.white,fontName='Helvetica-Bold'))
styles['Heading1'].textColor=BLUE;styles['Heading1'].fontSize=19;styles['Heading1'].leading=24
styles['Heading1'].spaceAfter=17
styles['Heading2'].textColor=TEAL;styles['Heading2'].fontSize=12;styles['Heading2'].leading=17
styles['Heading2'].spaceBefore=10;styles['Heading2'].spaceAfter=9
report=json.loads((O/'best_model_report.json').read_text())
clinical=json.loads((O/'clinical_summary.json').read_text())
mining=json.loads((O/'mining_summary.json').read_text())
orange=json.loads((D/'logs/orange_validation.json').read_text())
provenance=json.loads((O/'run_provenance.json').read_text())
comparison=pd.read_csv(O/'model_comparison.csv')
rules=pd.read_csv(O/'fp_growth_rules.csv')

def clean(s):
    return str(s).replace('—','-').replace('–','-').replace('’',"'").replace('→',' -> ').replace('≥','>=').replace('×','x')
def markup(s):
    s=escape(clean(s))
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'`([^`]+)`',r'<font name="Courier">\1</font>',s)
    return s
def para(s,style='BodyJ'): return Paragraph(markup(s),styles[style])
def text(story,s):
    for block in s.strip().split('\n\n'):
        if block.strip(): story.append(para(block.strip()))
def table(story,headers,rows,widths=None):
    data=[[para(v,'TableHeader') for v in headers]]+[[para(v,'SmallText') for v in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BLUE),('TEXTCOLOR',(0,0),(-1,0),colors.white),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f0f6f8'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,0),1,TEAL),('LINEBELOW',(0,-1),(-1,-1),.4,colors.HexColor('#bfd2dc'))]))
    story.extend([KeepTogether([t]) if len(rows)<=10 else t,Spacer(1,12)])
def figure(story,path,caption,width=487,max_height=360):
    path=Path(path)
    if not path.is_file(): raise FileNotFoundError(f'Required evidence missing: {path}')
    w,h=ImageReader(str(path)).getSize();scale=min(width/w,max_height/h)
    story.append(KeepTogether([Image(str(path),width=w*scale,height=h*scale),Spacer(1,5),para(caption,'SmallText')]))
    story.append(Spacer(1,10))
def footer(canvas,doc):
    w,h=doc.pagesize
    canvas.saveState();canvas.setStrokeColor(TEAL);canvas.setLineWidth(.6)
    canvas.line(doc.leftMargin,33,w-doc.rightMargin,33)
    canvas.setFont('Helvetica',8);canvas.setFillColor(GREY)
    canvas.drawString(doc.leftMargin,21,'HEALTHCARE INTELLIGENCE PLATFORM  |  JURY 2  |  21 OCTOBER 2026')
    canvas.drawRightString(w-doc.rightMargin,21,str(doc.page));canvas.restoreState()
class ReportDoc(SimpleDocTemplate):
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name=='Heading1':
            label=flowable.getPlainText();key='chapter-'+str(self.page)
            self.canv.bookmarkPage(key)
            self.notify('TOCEntry',(0,label,self.page,key))
            self.canv.addOutlineEntry(label,key,0,False)
def cover(story,title,evidence=False):
    story.extend([Spacer(1,35),para('DATA WAREHOUSING AND DATA MINING','Kicker'),para(title,'CoverTitle')])
    text(story,'Integrated Clinical & Operational Healthcare Intelligence Platform: Data Warehouse with AI-Driven Patient Readmission & Bed Capacity Prediction')
    story.append(para('Jury 2 focus: Predictive Patient Risk Mining and Clinical Feature Profiling using Healthcare Data','Heading2'))
    story.append(Spacer(1,22))
    table(story,['Team member name','Registration number'],[['________________________________','________________________'] for _ in range(4)], [270,210] if not evidence else [400,320])
    for label in ['Department','Institution','Faculty / Guide']:
        story.append(para(label+': __________________________________________________________'))
    story.append(Spacer(1,16))
    text(story,'Verified implementation and evidence edition - 21 October 2026. Personal and institutional details are intentionally left blank for the team to complete.')
    if evidence:
        text(story,'Screenshots in this document were captured directly from the working Streamlit application in an isolated Google Chrome session. No dashboard interface or displayed result was reconstructed. Landscape A3 pages preserve screenshot readability; zoom when viewing on a smaller display.')
    story.append(PageBreak())
def chapter(story,n,title):
    if story and not isinstance(story[-1],PageBreak):story.append(PageBreak())
    story.append(Paragraph(f'Chapter {n} - {title}',styles['Heading1']))
def section(story,title,body):
    story.append(para(title,'Heading2'));text(story,body)
def handover_section(name):
    content=(R/'docs/TECHNICAL_HANDOVER.md').read_text(encoding='utf-8')
    m=re.search(r'^## '+re.escape(name)+r'\n(.*?)(?=^## |\Z)',content,re.M|re.S)
    if not m:raise ValueError(name)
    return m.group(1).strip()
def markdown(story,source):
    lines=source.splitlines(); block=[]; code=False
    def flush():
        if block:text(story,' '.join(block));block.clear()
    for line in lines:
        if line.startswith('```'):flush();code=not code;continue
        if code:
            story.append(para(line,'SmallText'));continue
        if line.startswith('#'):flush();story.append(para(line.lstrip('# ').strip(),'Heading2'));continue
        if not line.strip():flush();continue
        if line.startswith('|'):continue
        if re.match(r'^\d+\. |^\* |^- ',line):flush();story.append(para(line));continue
        block.append(line)
    flush()
def diagrams():
    D.joinpath('figures').mkdir(exist_ok=True)
    def diagram(filename,boxes,arrows,title):
        fig,ax=plt.subplots(figsize=(11,6));ax.set(xlim=(0,11),ylim=(0,6));ax.axis('off')
        for x,y,w,h,label in boxes:
            patch=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.08',facecolor='#e9f3f6',edgecolor='#147b83',linewidth=1.5)
            ax.add_patch(patch);ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=10,color='#153e56',wrap=True)
        for start,end in arrows:ax.annotate('',xy=end,xytext=start,arrowprops=dict(arrowstyle='->',color='#527381',lw=1.8))
        ax.set_title(title,fontsize=14,pad=15,color='#153e56');fig.tight_layout();fig.savefig(D/'figures'/filename,dpi=180);plt.close(fig)
    diagram('architecture.png',[(3.6,4.8,3.6,.75,'Preserved UCI encounter CSV\n101,766 encounters'),(.3,2.8,3.1,1,'Jury 1: local ETL\nSQLite star schema + OLAP'),(4.0,2.8,3.1,1,'Jury 2: features\nclassification / mining / profiles'),(7.8,2.8,2.8,1,'Orange export\n3,000 unique patients'),(.3,.7,3.1,1,'Warehouse dashboard\nTableau / Power BI assets'),(4.0,.7,3.1,1,'Current artifacts\nStreamlit + saved inference'),(7.8,.7,2.8,1,'Supplementary Orange\nclassification / association')],[((4.1,4.8),(1.85,3.8)),((5.55,4.8),(5.55,3.8)),((7.0,4.8),(9.2,3.8)),((1.85,2.8),(1.85,1.7)),((5.55,2.8),(5.55,1.7)),((9.2,2.8),(9.2,1.7))],'Implemented data flow (design schematic derived from source code)')
    diagram('model_workflow.png',[(.2,4.6,2.9,.9,'Patient-group split\ntrain / validation / test'),(4,4.6,2.9,.9,'Training-only pipeline\nimputation / scale / one-hot'),(7.8,4.6,2.9,.9,'Five fixed candidates\nsame rows and feature set'),(7.8,2.5,2.9,.9,'Select validation macro F1\ntie-break: <30-day recall'),(4,2.5,2.9,.9,'Refit selected Random Forest\ntrain + validation'),(.2,2.5,2.9,.9,'Untouched test patients\nmetrics / CM / ROC'),(4,.4,2.9,.9,'Persist complete pipeline\nStreamlit discharge-time demo')],[((3.1,5.05),(4,5.05)),((6.9,5.05),(7.8,5.05)),((9.25,4.6),(9.25,3.4)),((7.8,2.95),(6.9,2.95)),((4,2.95),(3.1,2.95)),((1.7,2.5),(5.45,1.3))],'Classification experiment and inference workflow')
    diagram('mining_workflow.png',[(.3,4.5,3,1,'Encounter records\n3 diagnosis columns + meds'),(4,4.5,3,1,'Basket construction\ngroup ICD-9, active meds'),(7.7,4.5,3,1,'Boolean encoding\n101,766 x 33 items'),(.3,2.3,3,1,'Apriori\n85 frequent itemsets'),(4,2.3,3,1,'FP-Growth\n85 frequent itemsets'),(7.7,2.3,3,1,'Rules + transparent filters\n23 qualifying rules each'),(4,.3,3,1,'CSV / JSON / chart\nStreamlit association view')],[((3.3,5),(4,5)),((7,5),(7.7,5)),((9.2,4.5),(1.8,3.3)),((9.2,4.5),(5.5,3.3)),((3.3,2.8),(7.7,2.8)),((7,2.8),(7.7,2.8)),((9.2,2.3),(5.5,1.3))],'Association mining flow (same baskets and thresholds for both algorithms)')

def build_evidence():
    path=D/'Jury2_Three_Dashboard_Evidence.pdf'
    size=landscape(A3);doc=SimpleDocTemplate(str(path),pagesize=size,leftMargin=43,rightMargin=43,topMargin=32,bottomMargin=43,title='Jury 2 - Three Dashboard Evidence',author='Healthcare Intelligence Platform Team')
    s=[];cover(s,'Jury 2 - Three Dashboard Evidence',True)
    pages=[('1. Pattern Matching / Association Rule Mining','01_association.png','Apriori and FP-Growth were run on 101,766 encounters. Both found 85 itemsets and 23 filtered rules. The screenshot shows actual FP-Growth rule support, confidence and lift. Co-occurrence does not establish a medical treatment effect.'),('1.1 Frequent itemsets','01_itemsets.png','The expanded frequent-pattern table displays the itemsets underlying the rules. Thresholds: support 3%, confidence 35%, lift at least 1; maximum itemset size 3.'),('2. Five-Model Classification Comparison','02_benchmark.png','Decision Tree, Gaussian Naive Bayes, kNN, Random Forest and XGBoost share the same patient-separated split. Random Forest wins validation macro F1 at 0.43471; kNN has higher accuracy but almost no early-readmission recall.'),('3. Selected Best Classifier','03_best_model.png','Random Forest on 20,488 untouched test encounters: accuracy 51.11%, macro F1 0.43302, macro one-vs-rest ROC-AUC 0.65031 and <30-day recall 30.04%. Confusion-matrix rows are true outcomes; columns are predictions.'),('3.1 Classification report and interpretation','03_best_details.png','Early-readmission precision is 19.93% and F1 is 0.23960. Permutation importance is exploratory, using 250 held-out rows and two repeats. This is a discharge-time academic prototype with limited minority-class performance.')]
    pages.insert(2,('1.2 Association rule chart','01_association_chart.png','The actual dashboard chart compares lift across the highest-ranked rules, with confidence encoded by colour. The current dataset shows modest enrichment; this visual does not establish medical causation.'))
    for i,(title,file,explanation) in enumerate(pages):
        s.append(para(title,'Heading1'));text(s,explanation)
        figure(s,E/file,'Genuine Streamlit viewport capture - '+file,width=size[0]-86,max_height=size[1]-185)
        if i<len(pages)-1:s.append(PageBreak())
    doc.build(s,onFirstPage=footer,onLaterPages=footer)

def build_report():
    path=D/'Jury2_Healthcare_Intelligence_Implementation_Report.pdf'
    doc=ReportDoc(str(path),pagesize=A4,leftMargin=49,rightMargin=49,topMargin=46,bottomMargin=48,title='Jury 2 - Healthcare Intelligence Implementation Report',author='Healthcare Intelligence Platform Team')
    s=[];cover(s,'Complete Jury 2 Implementation Report')
    s.append(para('Contents','Heading1'));toc=TableOfContents();toc.levelStyles=[ParagraphStyle(name='TOC',fontName='Helvetica',fontSize=10,leading=16,spaceBefore=4,textColor=BLUE)];s.append(toc);s.append(PageBreak())
    s.append(para('Abstract','Heading1'))
    text(s,f'''This implementation integrates a reproducible SQLite healthcare warehouse with three data-mining tasks: multiclass readmission prediction, diagnosis-medication association mining, and descriptive clinical feature profiling. It uses the preserved local UCI Diabetes 130-US Hospitals dataset, with {clinical['dataset_encounters']:,} encounters and {clinical['unique_patients']:,} patients. Jury 1 retains its ETL, SQL/OLAP and warehouse dashboard; Jury 2 adds a five-model benchmark, a saved inference pipeline and a six-view Streamlit demonstration.

Patients are separated across training, validation and test partitions to reduce leakage from repeated encounters. Among five fixed candidate configurations, Random Forest achieves the highest validation macro F1, 0.43471. After refitting on training plus validation data, it achieves test macro F1 0.43302, accuracy 0.51113 and macro one-vs-rest ROC-AUC 0.65031. Early-readmission recall is 0.30038 and precision is 0.19927, limiting practical reliability. Apriori and FP-Growth produce matching sets of 85 frequent itemsets and 23 filtered rules on all encounters. These describe associations rather than treatment effects.

The repository was backed up before restructuring, its source data were hash-verified, and 29 automated tests passed after repairs. Genuine browser evidence covers the three faculty-required dashboard views and saved-model inference. Supplementary Orange workflows use a separate 3,000-patient sample with explicit categorical data and saved widget settings. The project remains an academic discharge-time analytical prototype. Bed-capacity forecasting and length-of-stay prediction are future extensions.''')
    chapter(s,1,'Introduction')
    section(s,'1.1 Background and problem', '''Healthcare encounters combine demographic categories, diagnoses, treatments and operational measures. Analytical work must organise these fields consistently before attempting prediction or pattern discovery. A warehouse supports repeatable aggregation, while a mining layer tests whether historical encounter characteristics distinguish recorded outcomes and recurring diagnosis-medication combinations.

The project addresses two connected academic problems: constructing a queryable star schema and evaluating mining methods with an auditable path from source data to displayed evidence. Repeated patients, outcome imbalance and retrospective variables make this more than a simple accuracy exercise. A convincing demonstration must explain the data grain, prediction point, evaluation split and limitations of each result.''')
    section(s,'1.2 Objectives, USP and MVP', '''The objectives are to preserve the original cohort, provide repeatable ETL and OLAP, compare five classifiers consistently, select a model using validation evidence, verify Apriori and FP-Growth results, and display all three faculty-required views. A supplementary Orange demonstration makes categorical data and evaluation workflows inspectable without replacing the Python implementation.

The proposed distinguishing contribution is traceability across warehouse, feature definitions, model selection, rule mining and dashboard evidence in one small academic repository. The working MVP comprises the SQLite warehouse, precomputed analytical outputs, the six-view Streamlit application, a saved discharge-time inference pipeline, and the supplementary Orange workflows. It is not an operational hospital product.''')
    section(s,'1.3 Jury scope',handover_section('Architecture and scope'))
    chapter(s,2,'Literature and Technical Background')
    section(s,'2.1 Data warehousing and OLAP', '''A star schema places measured events in a central fact table and descriptive attributes in dimensions. The design makes the grain explicit and allows SQL to aggregate measures across categories. Roll-up aggregates detail to a coarser level; slice restricts the analysed population. This project demonstrates those operations in SQLite rather than claiming a distributed production warehouse.

ETL is also a reproducibility boundary. If extraction silently changes the source or loading targets a different database from the dashboard, subsequent results cannot be explained reliably. The repaired implementation reads the local source without overwriting it and uses one canonical active warehouse location.''')
    section(s,'2.2 Supervised classification and evaluation', '''Supervised classification learns relationships between predictor values and observed class labels. Decision trees partition the feature space; Naive Bayes combines feature likelihoods; nearest-neighbour methods compare similarity; bagged forests average many trees; boosting combines sequential corrections. The five implemented candidates represent different modelling assumptions rather than five cosmetic variants.

Validation selects between candidate configurations, while an untouched test partition estimates performance after selection. Because patients can recur, grouping by patient is essential. Accuracy, precision, recall, macro F1 and one-vs-rest AUC answer different questions. The scikit-learn documentation defines the implemented metrics [2]. The results chapters use the actual recorded values, including the weak minority-class performance.''')
    section(s,'2.3 Frequent patterns and descriptive profiling', '''A frequent itemset appears in a sufficient fraction of transactions. Apriori uses the downward-closure property to prune candidate sets; FP-Growth mines compressed conditional patterns. Association rules add a direction to co-occurrence and are described by support, confidence and lift [3]. A high confidence value can arise from a common consequent, making lift and prevalence important context.

Clinical profiling groups encounters and summarises observed outcomes. Such aggregation is useful for describing historical cohorts, but group differences can reflect confounding, coding and repeated observations. Neither mining rules nor profile rates establish medical causes. These distinctions guide the interpretations throughout this report.''')
    chapter(s,3,'Dataset Description')
    section(s,'3.1 Source and local file', '''The official source is UCI's Diabetes 130-US Hospitals for Years 1999-2008 dataset [1]. The local source is the project copy, not a newly downloaded or sampled replacement. Its byte-level SHA-256 is recorded in the provenance file and matches the pre-edit audit. Local validation finds 101,766 rows, 50 columns and 71,518 distinct patient identifiers. UCI's predictor count differs from the raw-column count because identifiers and targets have separate roles.

The source represents historical inpatient encounters involving diabetes, rather than a current hospital feed. The cohort and available variables constrain generalisation. No new personal identifiers or team identities were invented for this report.''')
    table(s,['Outcome','Encounter count','Share'],[[k,f'{v:,}',f'{100*v/101766:.2f}%'] for k,v in clinical['readmission_counts'].items()],[160,155,160])
    section(s,'3.2 Features, target and preprocessing','\n\n'.join(handover_section('Features, missingness and prediction point').split('\n\n')[1:]))
    table(s,['Predictor type','Included variables'],[['Numeric','time_in_hospital; num_lab_procedures; num_procedures; num_medications; number_outpatient; number_emergency; number_inpatient; number_diagnoses'],['Categorical','age; gender; race; admission_type_id; insulin; change; diabetesMed; A1Cresult; diag_1_group; diag_2_group']],[95,380])
    section(s,'3.3 Data-quality limits', '''The missing-value strategy is technically consistent but cannot reconstruct unrecorded clinical information. Empty A1C observations are treated as Unknown; they are not assumed to be normal tests. Grouped ICD-9 codes lose detail while reducing sparsity. Age bands and demographic categories limit granularity. No hospital-level or chronological holdout is available in the implemented benchmark, and population shift from this historical cohort remains unmeasured.''')
    chapter(s,4,'System Architecture')
    figure(s,D/'figures/architecture.png','Figure 4.1. Design schematic derived from implemented modules and file flow; this is an explanatory diagram, not a runtime screenshot.')
    section(s,'4.1 Data flow and phase integration', '''The original CSV is the common input. Jury 1 builds the fact and dimension tables for SQL/OLAP and warehouse visualisation. Jury 2 reads encounter-level columns from that same preserved CSV because its treatment/history predictors are not all stored in the existing fact table. This is a documented shared-source integration, not a claim that model training queries the warehouse.

Analysis scripts write versioned-by-reproduction output files in jury_2_dw/outputs. Streamlit displays these CSV/JSON/chart artifacts and loads the fitted pipeline for an example inference form. Orange preparation derives a distinct unique-patient demonstration sample. Keeping those experiment boundaries explicit avoids mixing Orange cross-validation scores with the primary holdout benchmark.''')
    table(s,['Technology','Implemented role'],[['Python / pandas / NumPy','Data loading, feature construction, ETL and analysis'],['SQLite / SQL','Star-schema warehouse, joins, roll-up and slice'],['scikit-learn / XGBoost','Five fixed classifiers, pipelines and evaluation'],['mlxtend','Apriori, FP-Growth, transaction encoding and rule metrics'],['Streamlit / Plotly / Matplotlib','Interactive views and reproducible analytical charts'],['Orange / Orange3-Associate','Supplementary categorical mining and classification workflows'],['pytest / Playwright / ReportLab','Automated checks, browser evidence and academic PDFs']],[145,330])
    chapter(s,5,'Jury 1 Implementation')
    section(s,'5.1 ETL, schema and SQLite',handover_section('Data warehouse operation'))
    with sqlite3.connect(R/'data/healthcare_dw.db') as c:
        rows=[[name,f'{c.execute("SELECT COUNT(*) FROM "+name).fetchone()[0]:,}'] for name in ['Fact_Admissions','Dim_Patient','Dim_Admission','Dim_Diagnosis']]
    table(s,['Table','Verified row count'],rows,[260,215])
    section(s,'5.2 SQL and visualisation', '''The roll-up query joins facts to patient demographics, groups by age band and computes admission count and mean stay. The slice query selects medication count greater than 15 and summarises outcomes and average laboratory count. Both were executed after ETL repair, and the console results are retained in deliverables/logs/olap.log.

The original Tableau workbook, Power BI asset and Jury 1 screenshots remain available. Their desktop applications were not retested in this run. The current Streamlit warehouse dashboard was executed with actual SQLite data and checked by AppTest and a real browser rendering. Figure 5.1 is a new genuine capture of that working dashboard.''')
    figure(s,E/'jury1_warehouse.png','Figure 5.1. Genuine browser screenshot of the preserved Jury 1 warehouse dashboard.',max_height=350)
    chapter(s,6,'Pattern Matching Implementation')
    section(s,'6.1 Transactions and algorithms',handover_section('Association mining'))
    figure(s,D/'figures/mining_workflow.png','Figure 6.1. Implemented association-mining workflow, derived from the actual script.')
    section(s,'6.2 Metric definitions and outputs', '''For antecedent A and consequent B, support is the count containing A union B divided by all encounters. Confidence is support(A union B) / support(A). Lift is confidence / support(B). These calculations use the same basket population and are independently recomputed in the tests for a real retained rule. CSV and JSON outputs contain the measured rule values.

Apriori took 0.089 seconds and FP-Growth took 0.256 seconds for itemset discovery in this run. These timings exclude surrounding load/export work and do not establish general speed rankings. The workload has only 33 observed items and a maximum itemset length of three, which makes candidate enumeration small.''')
    table(s,['Method','Itemsets','Rules','Itemset time'],[[k,mining[k]['frequent_itemsets'],mining[k]['cross_domain_rules'],str(mining[k]['seconds'])+' s'] for k in ['Apriori','FP-Growth']],[145,100,100,130])
    table(s,['Antecedent -> consequent','Support','Confidence','Lift'],[[r.antecedents+' -> '+r.consequents,f'{r.support:.4f}',f'{r.confidence:.4f}',f'{r.lift:.3f}'] for r in rules.head(5).itertuples()],[265,70,75,65])
    figure(s,O/'top_association_rules.png','Figure 6.2. Actual highest-lift qualifying FP-Growth rules. Truncated plot labels are expanded in the saved rule table.')
    chapter(s,7,'Classification Model Comparison')
    section(s,'7.1 Algorithms and evaluation process',handover_section('Training, comparison and evaluation').split('The verified winner')[0])
    figure(s,D/'figures/model_workflow.png','Figure 7.1. Training, validation selection, final test and saved inference workflow.')
    table(s,['Model','Accuracy','Macro F1','<30 recall','Macro AUC'],[[r.model,f'{r.accuracy:.4f}',f'{r.f1_macro:.4f}',f'{r.recall_under_30:.4f}',f'{r.roc_auc_ovr_macro:.4f}'] for r in comparison.itertuples()],[135,85,85,85,85])
    figure(s,O/'model_comparison.png','Figure 7.2. Actual validation comparison across the five fixed candidate configurations.')
    section(s,'7.2 Selection rationale and weaknesses', '''Random Forest obtains validation macro F1 0.43471, ahead of XGBoost at 0.42379. XGBoost achieves higher early-readmission recall, while kNN achieves the highest accuracy but under-30-day recall only 0.01526. These differences illustrate that the winner depends on the declared objective. The chosen criterion weights all three outcome classes equally; it was not optimised for a clinical intervention cost.

Gaussian Naive Bayes performs poorly overall despite high early-readmission recall because it predicts that class too often. Its conditional independence and Gaussian likelihood assumptions fit these correlated one-hot features poorly. The benchmark retains this measured result rather than hiding it. No exhaustive hyperparameter tuning or confidence-interval study was performed, so close comparisons should not be treated as definitive statistical superiority.''')
    chapter(s,8,'Selected Best Classifier')
    section(s,'8.1 Random Forest design and final evaluation', '''The selected candidate is an ensemble of 140 decision trees with maximum depth 18 and minimum leaf size four. Balanced sample weights give rarer outcomes more training influence. Random feature selection and averaging reduce the variance of individual trees. The saved pipeline includes numeric median imputation and scaling, categorical encoding, and the fitted forest; inference uses the same transformations and fixed class order.

After selecting with validation macro F1, the forest is refit on 81,278 training-plus-validation encounters. Evaluation uses the 20,488 untouched encounters from 14,304 test patients. The output classes remain NO, >30 and <30. These are recorded readmission categories, and the model uses discharge-time information.''')
    table(s,['Holdout metric','Measured value'],[[k,f'{v:.5f}'] for k,v in report['test_metrics'].items()],[280,195])
    figure(s,O/'best_confusion_matrix.png','Figure 8.1. Actual confusion matrix on the untouched test set.',max_height=345)
    figure(s,O/'best_roc.png','Figure 8.2. Actual one-vs-rest ROC curves on the untouched test set.',max_height=330)
    table(s,['Class','Precision','Recall','F1','Support'],[[label,f'{report["per_class_test_report"][label]["precision"]:.4f}',f'{report["per_class_test_report"][label]["recall"]:.4f}',f'{report["per_class_test_report"][label]["f1-score"]:.4f}',str(int(report['per_class_test_report'][label]['support']))] for label in report['class_order']],[95,95,95,95,95])
    section(s,'8.2 Interpretation and practical limits', '''Only 711 of 2,367 true early-readmission encounters are correctly assigned to <30; 845 are assigned to NO and 811 to >30. Conversely, many predicted early readmissions are false positives, giving precision 0.19927. Such errors materially limit use beyond an academic demonstration.

An all-NO baseline on the same test set achieves accuracy 0.53304 and macro F1 0.23180. Random Forest has lower accuracy but substantially higher macro F1 and nonzero minority recall. This comparison explains the criterion without claiming the model is clinically useful. Macro AUC 0.65031 indicates modest ranking ability, not calibrated risk probabilities or benefit to patients.''')
    figure(s,O/'best_feature_importance.png','Figure 8.3. Exploratory permutation importance on 250 fixed test rows, two repeats.')
    section(s,'8.3 Model interpretation',handover_section('Training, comparison and evaluation').split('Permutation importance')[1].join(['Permutation importance','']))
    chapter(s,9,'Clinical Feature Profiling')
    section(s,'9.1 Grouping and outputs', '''The profiling script summarises the same source cohort across age bands, primary diagnosis groups, medication counts, prior inpatient visits and observed length-of-stay bands. Each output contains encounter count, under-30-day count/rate, average hospital days and average medication count. Primary-diagnosis display excludes groups below 500 encounters to avoid presenting very small cohorts without context.

The overall early-readmission fraction is 11.16%, mean stay is 4.40 days and mean medication count is 16.02. Prior inpatient groups 0, 1 and 2+ have observed early-readmission rates 8.44%, 12.92% and 21.40%. This describes the historical sample, not a causal effect of prior care. Rates are encounter-weighted; repeated patients limit independence, and confidence intervals were not estimated.''')
    for file,caption in [('profile_age.png','age bands'),('profile_diagnosis.png','primary diagnosis categories'),('profile_medications.png','medication-load bands'),('profile_prior_inpatient.png','prior inpatient visits'),('profile_stay.png','observed length-of-stay bands')]:
        figure(s,O/file,'Figure 9.'+str(['profile_age.png','profile_diagnosis.png','profile_medications.png','profile_prior_inpatient.png','profile_stay.png'].index(file)+1)+'. Actual descriptive readmission rates by '+caption+'.',max_height=265)
    chapter(s,10,'Dashboard Implementation')
    section(s,'10.1 Application structure and faculty requirements', '''Streamlit's sidebar selects six views in one application. Association Mining exposes algorithm selection, frequent itemsets, a lift filter and rule metrics. Model Benchmark displays the five validation score rows, a selectable metric chart and selection rationale. Best Model displays the selected algorithm, test metrics, confusion matrix, ROC, class report and permutation importance. These are the three faculty-required views.

Overview provides context; Clinical Profiling allows cohort grouping; Live Risk Studio demonstrates the saved pipeline using a hypothetical bounded encounter form. The application does not retrain during browsing. It resolves artifacts relative to its source file, caches read-only results, checks the model bundle/class order, and reports missing or corrupt CSV/JSON files clearly.''')
    for file,caption in [('01_association.png','Association Mining, showing actual full-cohort rules.'),('02_benchmark.png','Five-model validation comparison and declared selection criterion.'),('03_best_model.png','Selected Random Forest test metrics, confusion matrix and ROC.'),('05_inference.png','Working saved-pipeline example inference on hypothetical input.')]:
        figure(s,E/file,'Figure 10.'+str(['01_association.png','02_benchmark.png','03_best_model.png','05_inference.png'].index(file)+1)+'. Genuine Streamlit browser screenshot: '+caption,max_height=360)
    section(s,'10.2 Demonstration sequence', '''Begin with the historical source counts and discharge-time prediction scope. Open Association Mining and interpret one measured rule. Compare validation macro F1 across the five classifiers; explain kNN's accuracy/recall trade-off. Show the selected model's test confusion matrix and read the early-readmission row, then demonstrate a hypothetical inference. Use a clinical profile and supplementary Orange workflow only after the three required views. The separate evidence PDF provides larger screenshots for inspection.''')
    chapter(s,11,'Orange Data Mining Integration')
    markdown(s,(R/'docs/ORANGE_DEMONSTRATION.md').read_text().split('## Repair evidence')[1].replace('## Association workflow','## Association workflow',1))
    table(s,['Supplementary learner','5-fold accuracy','Macro F1','AUC'],[[name,f'{orange["five_fold_accuracy"][i]:.4f}',f'{orange["five_fold_macro_f1"][i]:.4f}',f'{orange["five_fold_auc"][i]:.4f}'] for i,name in enumerate(orange['learners'])],[160,105,105,105])
    for file,caption in [('orange_rules.png','Desktop FP-Growth output: 45 actual rules at support 3% and confidence 35%.'),('orange_classification.png','Desktop Test & Score after fixing the Tree settings; all four learners produce metrics.')]:
        figure(s,E/file,'Figure 11.'+('1' if 'rules' in file else '2')+'. Genuine Orange screenshot. '+caption,max_height=230)
    chapter(s,12,'Testing and Validation')
    validation_text=(R/'docs/VALIDATION.md').read_text(encoding='utf-8').split('\n',1)[1]
    markdown(s,validation_text.split('\nNo external/temporal')[0])
    chapter(s,13,'Results and Discussion')
    section(s,'13.1 Consolidated findings', '''The integrated system is reproducible across warehouse construction, model comparison, rule mining and descriptive profiling. The active warehouse retains all 101,766 encounters, and a full fact/dimension join preserves the same count. The primary dataset remains byte-identical to the audit copy. The three required Streamlit views render actual generated results and support the tested interactions.

Random Forest wins the declared validation objective and generalises similarly in macro F1 to the untouched patient test set. Its test macro F1 of 0.43302 remains modest, and early-readmission recall of 0.30038 is insufficient for a reliable patient-care workflow. The majority baseline comparison demonstrates why reporting only accuracy would be misleading.

Both association algorithms return matching results on the same baskets and thresholds. The strongest retained lift is about 1.229, so the patterns are weak-to-moderate enrichments within the observed prescribing data. Clinical profiles highlight differences across utilisation cohorts, particularly prior inpatient history, without establishing causation. Orange demonstrates valid categorical workflows but its different sample and representation must remain clearly labelled.''')
    section(s,'13.2 Limitations and threats to validity', '''The implementation uses one historical dataset and one fixed patient-group split. It does not estimate uncertainty across repeated splits, test temporal drift, validate on a separate healthcare system, calibrate probabilities or quantify performance by demographic subgroups. Candidate hyperparameters were fixed rather than exhaustively tuned, and the Naive Bayes assumptions are poorly matched to the feature representation.

Repeated encounters remain in descriptive mining and profiling, making them encounter-weighted rather than independent patient observations. Diagnosis grouping simplifies clinical detail. A 250-row permutation sample is intentionally lightweight and noisy. Preserved BI assets were not interactively retested in their desktop applications. These limitations constrain claims and identify concrete next validation tasks.''')
    chapter(s,14,'Conclusion and Future Scope')
    section(s,'14.1 Work completed', '''Jury 1 functionality is preserved in a repaired local-source ETL/warehouse flow. Jury 2 provides five comparable classifiers, validation-based selection, a saved multiclass inference pipeline, matching Apriori/FP-Growth results, five clinical profiles and the three required dashboard views. A recoverable backup, dependency records, tests, genuine screenshots, technical handover and viva material support team transfer and academic review.

The academic contribution is an auditable end-to-end analytical prototype whose displayed results can be traced to a source cohort and executed code. Honest reporting of limited classification performance and observational rule meaning is part of the result. The deliverable is prepared for demonstration, with explicit boundaries on what was and was not tested.''')
    section(s,'14.2 Roadmap', '''Future modelling work should prioritise repeated patient-group validation, temporal and external testing, probability calibration and subgroup error analysis. Feature improvements and alternative class-imbalance strategies should be evaluated with a declared objective and an untouched final test cohort. Association studies should examine stability across cohorts, patient-level sensitivity analyses and clinically reviewed definitions.

Operational intelligence requires time-stamped admission/discharge and capacity data, appropriate occupancy forecasting baselines, capacity constraints and validation against real operational outcomes. A separate length-of-stay prediction task and a bed-capacity forecasting model could then be built and evaluated. Those features remain future scope, despite their presence in the broader project title. Clinical deployment would require a substantially different validation and governance programme.''')
    s.append(PageBreak());s.append(para('References','Heading1'))
    refs=[('[1] UCI Machine Learning Repository','Diabetes 130-US Hospitals for Years 1999-2008. Official dataset description and provenance.','https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008'),('[2] scikit-learn documentation','Metrics and scoring: quantifying the quality of predictions; pipelines, grouping and model documentation.','https://scikit-learn.org/stable/modules/model_evaluation.html'),('[3] mlxtend documentation','Association rules: support, confidence, lift and frequent-pattern interfaces.','https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/association_rules/'),('[4] Orange Data Mining documentation','File widget and native three-header tab-separated format.','https://orangedatamining.com/widget-catalog/data/file/'),('[5] Streamlit documentation','App testing framework and AppTest.','https://docs.streamlit.io/develop/api-reference/app-testing'),('[6] XGBoost documentation','Python estimator and tree-boosting parameters.','https://xgboost.readthedocs.io/en/stable/parameter.html')]
    for title,description,url in refs:
        text(s,title+'. '+description);s.append(Paragraph('<link href="'+escape(url,quote=True)+'" color="#147b83">'+escape(url)+'</link>',styles['SmallText']))
    text(s,'References accessed 21 October 2026. Library versions and the source SHA-256 are recorded in run_provenance.json. The implementation findings in this report derive from local source code, executed logs, CSV/JSON results and genuine screenshots, rather than unsupported literature claims.')
    s.append(PageBreak());s.append(para('Appendix A - Reproduction and artifact index','Heading1'))
    text(s,'Run commands and dependency instructions are in README.md. Technical handover, viva preparation, Orange demonstration and validation records are in docs/. Current analysis outputs are under jury_2_dw/outputs. The external pre-edit backup and the local archive preserve historical work. The complete final file tree, change disposition and Git state are in docs/FINAL_COMPLETION_REPORT.md.')
    table(s,['Artifact','Role'],[['model_comparison.csv / .json','Validation metrics for five models'],['best_model.joblib','Complete fitted preprocessing/classifier bundle'],['best_model_report.json','Selected-model holdout metrics and per-class report'],['run_provenance.json','Source hash, dependency versions, seeds, candidate parameters and split hashes'],['apriori_* / fp_growth_*','Real itemsets, rule tables and measured timing summaries'],['profile_*.csv / .json / .png','Clinical cohort counts, rates and charts'],['deliverables/evidence/','Genuine browser and Orange screenshots'],['deliverables/logs/','Executed pipeline, test, browser, Orange and PDF validation records']],[195,280])
    doc.multiBuild(s,onFirstPage=footer,onLaterPages=footer)

def main():
    D.mkdir(exist_ok=True);diagrams();build_evidence();build_report()
    for p in D.glob('*.pdf'):print(p,p.stat().st_size)
if __name__=='__main__':main()
