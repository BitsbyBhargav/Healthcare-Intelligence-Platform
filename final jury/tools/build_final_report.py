"""Build the measured jury report, warehouse figure, and viva notes."""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs';REPORT=ROOT/'reports';REPORT.mkdir(exist_ok=True)
def get(p):return json.loads((ROOT/p).read_text())
c=get('outputs/classification/results.json');g=get('outputs/clustering/results.json');m=get('outputs/mining/results.json')
contract=get('A_warehouse_design/star_schema_contract.json');cloud=get('B_snowflake_deployment/warehouse_status.json')
fig,ax=plt.subplots(figsize=(12,7));ax.set(xlim=(0,12),ylim=(0,7));ax.axis('off')
def box(x,y,w,h,title,body,fill='#eaf2f3'):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.1',facecolor=fill,edgecolor='#52777d',linewidth=1.2))
    ax.text(x+.12,y+h-.23,title,fontweight='bold',fontsize=10,color='#153c45',va='top')
    ax.text(x+.12,y+h-.63,body,fontsize=8.3,color='#233f46',va='top',linespacing=1.4)
box(4.55,2.35,3.05,2.25,'FACT_ENCOUNTER','PK: ENCOUNTER_KEY\n7 surrogate foreign keys\nStay, costs and clinical counts\nLabel availability and model role\nSource-specific nulls retained','#d4e9e7')
positions=[(.2,4.85),(4.55,5.1),(8.8,4.85),(.2,2.55),(8.8,2.55),(.2,.2),(8.8,.2)]
for (name,attrs),(x,y) in zip(contract['dimensions'].items(),positions):
    short='\n'.join(a for a in attrs if a!='SOURCE_KEY' or name=='SOURCE')[:110]
    box(x,y,2.8,1.65,'DIM_'+name,'PK: '+name+'_ID\n'+short)
    ax.annotate('',xy=(6.05,3.45),xytext=(x+1.4,y+.8),arrowprops={'arrowstyle':'->','color':'#93adb2','lw':1},zorder=0)
ax.set_title('Star schema - one source encounter per fact row',fontsize=16,fontweight='bold',color='#153c45',pad=15)
fig.tight_layout();fig.savefig(OUT/'warehouse_star.png',dpi=170,bbox_inches='tight');plt.close(fig)

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyJ',fontName='Helvetica',fontSize=9.2,leading=13,spaceAfter=7,textColor=colors.HexColor('#243c45')))
styles.add(ParagraphStyle(name='SmallJ',fontName='Helvetica',fontSize=7.6,leading=10,spaceAfter=5))
styles['Title'].textColor=colors.HexColor('#174c50');styles['Heading1'].textColor=colors.HexColor('#174c50')
story=[]
def para(t,small=False):return Paragraph(t,styles['SmallJ' if small else 'BodyJ'])
def p(t):story.append(para(t))
def title(t):story.append(Paragraph(t,styles['Heading1']));story.append(Spacer(1,7))
def table(headers,rows,widths=None):
    content=[[para(escape(str(v)),True) for v in headers]]+[[para(escape(str(v)),True) for v in row] for row in rows]
    t=Table(content,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dcebec')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#174c50')),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f6f7')])]))
    story.append(t);story.append(Spacer(1,9))
def page():story.append(PageBreak())
def image(path,w,h):story.append(Image(str(path),width=w,height=h,hAlign='LEFT'));story.append(Spacer(1,8))

story.append(Paragraph('Healthcare Intelligence Platform',styles['Title']))
story.append(Paragraph('Final jury implementation report',styles['Heading2']))
p('22 November 2026 | Data Warehousing, Data Mining and Machine Learning')
title('Project and business decision')
p('Advance the original hospital/readmission project with an integrated, source-traceable warehouse. Analyze observed diabetes readmission patterns for follow-up review, and segment larger hospital encounter data by retrospective resource use. Intended users are hospital analytics and care-management teams.')
table(['Source','Published records','Observed readmission labels'],[['UCI diabetes encounters','101,766','101,766'],['SPARCS 2023 discharges','2,125,754','Unavailable'],['SPARCS 2024 discharges','2,196,737','Unavailable'],['Integrated master','4,424,257','101,766']],[190,110,170])
p('The single final master is modelled.csv with 51 columns. Integration is a schema-aligned union, not a patient-level join between unrelated sources. No synthetic records or generated readmission outcomes are included in the final warehouse or final classifier results.')
p('Shared age bands, gender and admission categories are aligned. Different diagnosis systems, source periods and unavailable clinical fields remain explicit. No missing calendar dates, hospital identities or outcomes are invented.')
title('Measured implementation status')
p(f"Snowflake dimensional build: <b>{cloud['status']}</b>, {cloud['fact_rows']:,} fact rows, seven dimensions and zero failed checks, as reported by the user from the final SQL result. Staging context, 51-column table, nine staged files, file validation and total load are also supported by saved user screenshots.")
p('Three classifiers, two mining algorithms, and four clustering methods were executed locally. Results and reproducible scripts are independent of earlier jury implementations. The synthetic augmentation experiment is retained separately as exploratory work.')
page()
title('A - Warehouse design')
p('Grain: one published encounter/discharge record from a named source snapshot. Natural fact key: source-qualified ENCOUNTER_KEY. Each dimension has a numeric surrogate primary key; FACT_ENCOUNTER has seven foreign keys.')
image(OUT/'warehouse_star.png',490,285)
table(['Table','Role'],[['DIM_SOURCE','Source and cohort provenance'],['DIM_PERIOD','Reported period; UCI year remains unknown'],['DIM_DEMOGRAPHIC','Source-aware age, gender, race and ethnicity'],['DIM_ADMISSION','Admission, disposition and payer context'],['DIM_DIAGNOSIS','Source coding system, diagnosis and APR group'],['DIM_FACILITY','Public hospital identity/location where available'],['DIM_TREATMENT','UCI medication and laboratory categories'],['FACT_ENCOUNTER','Stay, costs, utilization counts, labels and cohort roles']],[140,330])
p('Relationships are one dimension row to many fact rows. Null-safe joins retain redacted/unavailable attributes. Surrogate keys do not create a real patient identity. Standard Snowflake primary/foreign keys are informational, so duplicate/orphan checks are explicit.')
page()
title('B - Snowflake deployment')
p('Compute: FINAL_JURY_WH, X-Small, configured with 60-second auto-suspend. Database: HEALTHCARE_FINAL_JURY. STAGING stores the source landing table and file format/stage; DW stores typed records, dimensions, the fact table and analytical views.')
p('Batch workflow: modelled.csv -> nine lossless gzip packages -> MODELLED_STAGE -> validation -> MODELLED_RAW -> typed source snapshot -> dimensions -> FACT_ENCOUNTER -> analytical views. Continuous ingestion is not required by the supplied rubric.')
table(['Checkpoint','Recorded result'],[['Source contract','51 CSV columns in exact staging order'],['Files','Nine packages, each below 31 MB'],['File validation','Empty Snowflake error result'],['Staging load','4,424,257 rows'],['Dimensional load','User reported PASS; 4,424,257 facts; 7 dimensions'],['Integrity checks','User reported 0 failed warehouse checks']],[145,325])
e=ROOT/'B_snowflake_deployment/evidence/05_staging_loaded_4424257.png'
if e.exists():image(e,470,55)
p('Demonstrate the live implementation with 07_demo_queries.sql: source counts, age/admission slice, UCI label profile, hospital estimated-cost summary and warehouse checks. V_ENCOUNTER_ANALYTICS reconstructs all 51 source fields using the star joins. V_SOURCE_SUMMARY provides source-filtered aggregations.')
p('No Snowflake credentials are stored in this project. The local dashboard shows saved results/evidence and does not claim a live Snowflake connection. Query execution and current objects are shown in the authenticated Snowflake worksheet.')
page()
title('C - Supervised dataset and validation')
p('UCI Diabetes 130-US Hospitals, 1999-2008: 101,766 encounters and 50 CSV columns. Excluding 2,423 death/hospice discharges gives 99,343 eligible real encounters. The target is the published readmitted category: NO, &gt;30 or &lt;30. NO means no recorded readmission, not established complete follow-up.')
table(['Partition','Real encounters'],[[k,f'{v:,}'] for k,v in c['split_rows'].items()],[220,250])
p('The saved patient-group split has no patients shared across train, validation and test. Nineteen predictors cover stay, lab/procedure/medication counts, prior utilization, demographics, admission categories, diabetes treatment, laboratory categories and a broad primary-diagnosis group. IDs and the target are excluded from predictors.')
p('Source ? markers become missing; literal None laboratory results remain categories for tests not performed. Median imputation, StandardScaler and one-hot encoding are fitted on training data only. These are discharge-stage features; the experiment is not an admission-time risk forecast.')
title('E - Three classification algorithms')
comp=pd.read_csv(OUT/'classification/comparison.csv')
table(['Algorithm','Validation macro F1','Test macro F1','Test accuracy'],[[r.algorithm,f'{r.validation_macro_f1:.4f}',f'{r.test_macro_f1:.4f}',f'{r.test_accuracy:.4f}'] for r in comp.itertuples()],[160,110,100,100])
p('Logistic Regression fits class score boundaries with balanced weights; Decision Tree learns threshold rules (depth 10, minimum leaf 40); Random Forest averages randomized trees (120 trees, depth 14, minimum leaf 8, balanced subsample weights). All use the same real partitions, predictors and preprocessing. The selected model maximizes validation macro F1 before test evaluation.')
page()
title('F - Classification implementation')
p('Selected model: <b>'+c['selected']+'</b>. A fitted scikit-learn Pipeline stores preprocessing and classifier together. The dashboard sends an example through the same predictor construction and pipeline, displays its three class probabilities, and selects the largest probability. These probabilities are not calibrated clinical confidence.')
image(OUT/'classification/confusion_matrix.png',405,290)
selected=c['test'][c['selected']]
table(['Metric','Held-out result'],[['Accuracy',f"{selected['accuracy']:.4f}"],['Macro precision',f"{selected['per_class']['macro avg']['precision']:.4f}"],['Macro recall',f"{selected['per_class']['macro avg']['recall']:.4f}"],['Macro F1',f"{selected['macro_f1']:.4f}"],['Early-readmission recall',f"{selected['per_class']['<30']['recall']:.4f}"],['Macro OVR ROC AUC',f"{selected['macro_ovr_roc_auc']:.4f}"]],[220,250])
p(f"Majority-class baseline accuracy is {c['majority_baseline']['accuracy']:.4f}, with macro F1 {c['majority_baseline']['macro_f1']:.4f}. The selected model does not beat that baseline on accuracy; macro F1 and minority recall expose the tradeoff. No prospective or external clinical validation is claimed.")
page()
title('D - Apriori and FP-Growth')
p('A reproducible sample of 15,000 real training encounters is transformed into categorical transactions. Items include age band, diagnosis group, insulin, medication change, diabetes medication, HbA1c and readmission label. Minimum support 0.03; minimum confidence 0.35; lift above 1.05; maximum itemset length 3.')
table(['Algorithm','Itemsets','Rules','Seconds'],[[n,v['itemsets'],v['rules'],f"{v['seconds']:.3f}"] for n,v in m['algorithms'].items()],[150,90,90,140])
p('Apriori builds frequent candidates level by level. FP-Growth compresses transactions into a frequent-pattern tree and mines conditional patterns. Identical thresholds returned matching frequent itemsets.')
rules=pd.read_csv(OUT/'mining/apriori_rules.csv').head(5)
for r in rules.itertuples():
    p('<b>'+escape(r.antecedents)+' -> '+escape(r.consequents)+'</b>')
    p(f'Support {r.support:.3f}; confidence {r.confidence:.3f}; lift {r.lift:.3f}.')
p('Support is the fraction containing both sides; confidence is the consequent fraction among antecedent records; lift divides confidence by consequent prevalence. For example, lift 2 means twice the marginal prevalence, not twice the causal effect. Common medication categories can yield unsurprising rules; interpret their clinical and operational relevance cautiously.')
page()
title('G - Unsupervised dataset')
p(f"SPARCS 2023 and 2024 supply {g['eligible_full_records']:,} eligible real encounters after excluding capped/nonpositive stays, nonpositive cost, unavailable severity 1-4, and missing age. A fixed uniform hash sample of 5,000 encounters is used identically for all four algorithms.")
p('The representation uses standardized log1p(stay), log1p(estimated cost), severity and one-hot common age bands. Charges are excluded from fitting because of correlation with cost. No identifiers or readmission labels enter distances. Cost-method differences between years remain a source limitation.')
title('H - Four clustering algorithms')
table(['Algorithm','Clusters','Noise','Silhouette','DB index'],[[n,v['clusters'],v['noise'],f"{v['silhouette']:.3f}" if v['silhouette'] is not None else 'Undefined',f"{v['davies_bouldin']:.3f}" if v['davies_bouldin'] is not None else 'Undefined'] for n,v in g['algorithms'].items()],[140,70,65,95,100])
image(OUT/'clustering/four_algorithms.png',490,355)
p(f"Shared PCA display explains {g['pca_explained_variance']:.1%} of representation variance; models use the full representation. DBSCAN metrics exclude its noise and must be read with coverage. Silhouette uses the same fixed sampling indices where applicable.")
page()
title('I - Selected clustering implementation')
p('K-Means was selected as the highest-silhouette method that assigns every sampled encounter. It iteratively assigns each point to a centroid and updates centroids, minimizing within-cluster squared distances. K=2..6 was compared with 10 initializations and seed 42; K=2 was selected.')
profiles=pd.read_csv(OUT/'clustering/profiles.csv');profiles=profiles[profiles.algorithm.eq(g['selected'])]
table(['Cluster','Records','Mean stay (days)','Mean estimated cost (USD)','Mean severity'],[[int(r.cluster),int(r.records),f'{r.mean_stay:.2f}',f'{r.mean_estimated_cost:,.2f}',f'{r.mean_severity:.2f}'] for r in profiles.itertuples()],[60,70,100,150,90])
p('Cluster 0 has longer average stays, higher estimated costs and higher severity than cluster 1 in this sample. This supports descriptive resource-use segmentation for reviewing capacity and follow-up planning. It does not demonstrate saved costs, predicted future demand, or medically validated patient types. Cluster identifiers are arbitrary.')
table(['K','Sample silhouette'],[[v['k'],f"{v['silhouette']:.4f}"] for v in g['k_search']],[220,250])
title('J - Interpret performance metrics')
p('Classification: accuracy is the fraction correct; precision is correct positives among predicted positives; recall is detected cases among actual cases; F1 balances precision and recall. Macro averages give equal weight to each class. The confusion matrix reveals which outcomes are missed.')
p('Clustering: higher silhouette suggests separation; lower Davies-Bouldin suggests compact/separated groups; higher Calinski-Harabasz suggests stronger between-group separation relative to within-group spread. None is clinical ground truth. DBSCAN coverage and source-specific profiles remain essential.')
page()
title('Demonstration and viva preparation')
p('1. Explain the hospital/readmission foundation and larger source integration. 2. Show star grain/relationships and Snowflake PASS. 3. Explain observed versus unavailable readmission labels. 4. Show mining rules. 5. Compare three classifiers, demonstrate one prediction and its held-out metrics. 6. Show the unsupervised dataset and four methods. 7. Explain K-Means profiles and limits.')
for q,a in [
 ('Why warehouse instead of just CSV?','Consistent dimensions, typed measures, source traceability, reusable joins and analytical SQL.'),
 ('Star schema versus Snowflake platform?','Star is the logical fact/dimension design. Snowflake is the cloud platform running it.'),
 ('Does this require streaming?','No. The rubric asks for data loading; this implementation uses a verified batch load.'),
 ('Does SPARCS increase labeled readmission tests?','No. It adds real encounter covariates and resource/clustering data. Observed readmission evaluation remains on UCI.'),
 ('How was leakage prevented?','Patient-disjoint real splits; transformations fitted on training only; validation selects models; test is not used for tuning.'),
 ('Why macro F1?','Class imbalance makes accuracy alone hide the poorly detected early-readmission class.'),
 ('Why only 5,000 clustering rows?','All four algorithms must share a reproducible feasible benchmark; hierarchical methods have large pairwise-memory costs.'),
 ('Why K-Means?','It had the best common-sample silhouette among full-coverage methods, with interpretable resource profiles.'),
 ('Are synthetic results part of the final claims?','No. The exploratory SMOTENC pilot is saved separately; the master and final measured classifiers use real source records.'),
 ('What remains limited?','Retrospective cohorts, different source populations/cost methods, modest classification performance, sampled clustering, and no external clinical validation.')]:
    p('<b>'+q+'</b> '+a)
title('Sources and reproducibility')
for source in ['UCI dataset: https://doi.org/10.24432/C5230J','SPARCS 2023: https://health.data.ny.gov/d/46xm-urtu','SPARCS 2024: https://health.data.ny.gov/d/sf4k-39ay','Snowflake: https://docs.snowflake.com/','Measured implementation: tools/complete_analytics.py and B_snowflake_deployment SQL files']:
    story.append(para(escape(source),True))
def footer(canvas,doc):
    canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#52777d'));canvas.drawString(40,23,'Healthcare Intelligence Platform | Final jury | 22 November 2026');canvas.drawRightString(A4[0]-40,23,str(doc.page))
# Present every rubric block in the user's requested A-J order.
markers=[]
for i,item in enumerate(story):
    if isinstance(item,Paragraph):
        text=item.getPlainText()
        if len(text)>3 and text[0] in 'ABCDEFGHIJ' and text[1:4]==' - ':markers.append((text[0],i))
suffix_index=next(i for i,item in enumerate(story) if isinstance(item,Paragraph) and item.getPlainText()=='Demonstration and viva preparation')
sections={}
for j,(letter,start) in enumerate(markers):
    end=markers[j+1][1] if j+1<len(markers) else suffix_index
    section=story[start:end]
    while section and isinstance(section[-1],PageBreak):section.pop()
    sections[letter]=section
prefix=story[:markers[0][1]]
while prefix and isinstance(prefix[-1],PageBreak):prefix.pop()
ordered=prefix
for letter in 'ABCDEFGHIJ':ordered += [PageBreak()]+sections[letter]
ordered += [PageBreak()]+story[suffix_index:]
story=ordered
doc=SimpleDocTemplate(str(REPORT/'Final_Jury_Report.pdf'),pagesize=A4,rightMargin=40,leftMargin=40,topMargin=35,bottomMargin=40)
doc.build(story,onFirstPage=footer,onLaterPages=footer)

viva='''FINAL JURY - TEN-MINUTE REHEARSAL

OPENING (30 seconds)
Our project advances hospital readmission analytics through a source-traceable
UCI-SPARCS warehouse. We integrated 4,424,257 real encounters into 51 fields,
deployed the star schema to Snowflake, and compared mining, classification,
and clustering methods. Different sources retain their outcome availability.

A/B (90 seconds)
Show the star diagram: one encounter per fact row, seven dimensions. Explain
PK/FK joins, typed measures, null-safe handling, source-qualified record keys.
Show Snowflake PASS: 4,424,257 facts, seven dimensions, zero failed checks.
Use 07_demo_queries.sql for live source counts and slices. Batch loading,
not streaming. Snowflake platform and star schema are different concepts.

C/E/F/J (3 minutes)
UCI has 101,766 records; exclude 2,423 death/hospice encounters. Patient-group
split: 59,565 training, 19,917 validation, 19,861 test. Nineteen predictors.
Compare Logistic Regression, Decision Tree and Random Forest under the same
preprocessing and partitions. Validation macro F1 selects Random Forest.
Test: accuracy 0.5212, macro F1 0.4382, early-readmission recall 0.2988,
macro ROC AUC 0.6555. Accuracy is below the majority-class baseline; explain
the minority-detection tradeoff. Show one prediction, probabilities and matrix.
Discharge-time variables mean this is not an admission-time prediction model.

D (1 minute)
15,000 real training transactions; Apriori and FP-Growth both returned 445
frequent itemsets and 348 filtered rules. Support 3%, confidence 35%, lift
above 1.05, max length 3. Explain support/confidence/lift using a displayed rule.
Association is not causation. Same inputs and thresholds give matching itemsets.

G/H/I (3 minutes)
Clustering uses SPARCS resource variables, without readmission labels.
Reproducible 5,000-record sample; log stay, log estimated cost, severity and
one-hot age bands. Compare K-Means, Ward hierarchical, GMM and DBSCAN on the
same data. K=2..6 searched. K-Means K=2, silhouette 0.3122, assigns all rows.
DBSCAN yields 14 clusters and 136 noise rows; its scores exclude noise.
PCA display explains 73.24% of representation variance and is only a display.
K-Means cluster 0: 1,903 records, mean stay 10.77 days, cost $47,723.
Cluster 1: 3,097 records, mean stay 2.41 days, cost $10,787.
Explain these as observed resource-use groups, not clinical patient types.

CLOSING (30 seconds)
We demonstrate real integration, deployment and reproducible measured models.
SPARCS adds encounter volume but does not supply observed readmission labels.
Future work includes external labeled cohorts, calibrated probabilities,
prospective evaluation and source-year sensitivity analysis.

IF A QUESTION IS DIFFICULT
State the actual data/method, explain the limitation, and show the measured
evidence. Do not claim unmeasured accuracy, live occupancy or clinical benefit.
'''
(REPORT/'VIVA_REHEARSAL.txt').write_text(viva,encoding='utf-8')
print('Built warehouse figure, final PDF report, and viva rehearsal notes.')
