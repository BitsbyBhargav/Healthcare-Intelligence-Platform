"""Draw Jury 2 architecture and association flow from the documented full-cohort run."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables/figures'
plt.rcParams['font.family'] = 'Times New Roman'
NAVY = '#111111'
TEAL = '#333333'

def canvas(title):
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set(xlim=(0, 11), ylim=(0, 6))
    ax.axis('off')
    ax.text(.3, 5.72, title, fontsize=19, weight='bold', color=NAVY)
    return fig, ax

def box(ax, x, y, w, h, title, body='', dark=False):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=0.08',
        linewidth=1.1,edgecolor=TEAL,facecolor=NAVY if dark else '#f2f2f2'))
    color = 'white' if dark else NAVY
    if body:
        ax.text(x+w/2,y+h-.22,title,ha='center',va='center',fontsize=14,weight='bold',color=color)
        ax.text(x+w/2,y+(h-.34)/2,body,ha='center',va='center',fontsize=12.5,linespacing=1.3,color=color)
    else:
        ax.text(x+w/2,y+h/2,title,ha='center',va='center',fontsize=14,weight='bold',color=color)

def arrow(ax, start, end):
    ax.annotate('',xy=end,xytext=start,arrowprops=dict(arrowstyle='-|>',lw=1.4,color=TEAL,shrinkA=3,shrinkB=3))

def save(fig, name):
    OUT.mkdir(parents=True,exist_ok=True)
    fig.subplots_adjust(left=0,right=1,top=1,bottom=0)
    fig.savefig(OUT/name,dpi=300,facecolor='white')
    plt.close(fig)

def build():
    fig,ax=canvas('JURY 2  |  SYSTEM ARCHITECTURE')
    box(ax,.3,4.75,10.4,.65,'Shared source: preserved UCI encounter CSV  |  101,766 encounters',dark=True)
    ax.plot([1.95,9.05],[4.48,4.48],color=TEAL,lw=1.4)
    arrow(ax,(5.5,4.75),(5.5,4.48))
    for x in [1.95,5.5,9.05]: arrow(ax,(x,4.48),(x,4.22))
    box(ax,.3,2.85,3.3,1.35,'CLASSIFICATION','Patient-separated splits\nTrain-only preprocessing\n5 models -> selected pipeline')
    box(ax,3.85,2.85,3.3,1.35,'ASSOCIATION MINING','Diagnosis-medication baskets\nApriori + FP-Growth\nSupport / confidence / lift')
    box(ax,7.4,2.85,3.3,1.35,'CLINICAL PROFILING','Age, diagnoses, medications\nPrior admissions and stay\nDescriptive readmission rates')
    ax.plot([1.95,9.05],[2.55,2.55],color=TEAL,lw=1.4)
    for x in [1.95,5.5,9.05]: arrow(ax,(x,2.85),(x,2.55))
    arrow(ax,(5.5,2.55),(5.5,2.28))
    box(ax,.3,1.53,10.4,.72,'PERSISTED OUTPUTS  |  jury_2_dw/outputs','CSV tables, JSON metrics, charts and fitted prediction pipeline')
    arrow(ax,(5.5,1.53),(5.5,1.22))
    box(ax,.3,.48,10.4,.72,'STREAMLIT PRESENTATION','Association rules | model benchmark | best classifier | profiles | example inference',dark=True)
    ax.text(.3,.14,'Parallel source consumers: Jury 1 ETL / SQLite / OLAP; supplementary Orange sample (3,000 unique patients).',fontsize=11,color=NAVY)
    save(fig,'architecture.png')

    fig,ax=canvas('PATTERN MATCHING  |  ASSOCIATION-MINING WORKFLOW')
    box(ax,.3,4.55,3.1,.85,'ENCOUNTER INPUT','101,766 rows\nOne encounter = one basket')
    box(ax,3.95,4.55,6.75,.85,'BUILD AND ENCODE BASKETS','Deduplicate DIAG groups + active MED items\nExclude IDs / absent items; Boolean matrix: 101,766 x 33')
    arrow(ax,(3.4,4.98),(3.95,4.98))
    ax.plot([2.85,8.15],[4.24,4.24],color=TEAL,lw=1.4)
    arrow(ax,(7.32,4.55),(7.32,4.24))
    arrow(ax,(2.85,4.24),(2.85,3.96));arrow(ax,(8.15,4.24),(8.15,3.96))
    box(ax,.3,3.02,5.1,.92,'APRIORI','Candidate generation + downward-closure pruning\nSupport >= 3%; max size 3 -> 85 itemsets')
    box(ax,5.6,3.02,5.1,.92,'FP-GROWTH','FP-tree compression + frequent-pattern growth\nSupport >= 3%; max size 3 -> 85 itemsets')
    ax.plot([2.85,8.15],[2.71,2.71],color=TEAL,lw=1.4)
    arrow(ax,(2.85,3.02),(2.85,2.71));arrow(ax,(8.15,3.02),(8.15,2.71))
    arrow(ax,(5.5,2.71),(5.5,2.44))
    box(ax,.3,1.43,10.4,.98,'GENERATE AND FILTER RULES - EACH ALGORITHM','Confidence >= 35%; lift >= 1; DIAG and MED present across the union of both sides\nMixed item types may occur on either side; 23 qualifying rules per algorithm')
    arrow(ax,(5.5,1.43),(5.5,1.12))
    box(ax,.3,.39,10.4,.71,'VALIDATE, EXPORT AND PRESENT','Compare both result sets; independently check metrics -> CSV / JSON / chart -> Streamlit',dark=True)
    ax.text(.3,.10,'Interpretation: co-occurrence in historical encounters; association does not establish treatment efficacy or causation.',fontsize=11,color=NAVY)
    save(fig,'mining_workflow.png')

if __name__=='__main__':
    build()
