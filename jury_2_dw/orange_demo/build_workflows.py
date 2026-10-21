"""Generate Orange workflows with explicit dataset bindings and bounded learners.
Run with Orange's Python. Regenerate after relocating the project.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
import base64
import pickle
from Orange.widgets.utils.filedialogs import RecentPath

D = Path(__file__).resolve().parent


def make(title, description, nodes, edges, filename):
    root = ET.Element("scheme", version="2.0", title=title, description=description)
    ns = ET.SubElement(root,"nodes")
    for i, (name, qn, widget_title, pos) in enumerate(nodes):
        ET.SubElement(ns,"node",id=str(i),name=name,qualified_name=qn,
                      project_name="Orange3" if qn.startswith("Orange.") else "Orange3-Associate",
                      version="",title=widget_title,position=str(pos))
    ls = ET.SubElement(root,"links")
    for i,(src,dst,sc,dc) in enumerate(edges):
        ET.SubElement(ls,"link",id=str(i),source_node_id=str(src),sink_node_id=str(dst),
                      source_channel=sc,sink_channel=dc,enabled="true")
    ET.SubElement(root,"annotations")
    ET.SubElement(root,"thumbnail")
    properties = ET.SubElement(root,"node_properties")
    dataset = 'orange_associations.tab' if 'association' in filename else 'orange_classification.tab'
    settings = {'recent_paths': [RecentPath(str(D / dataset), 'basedir', dataset)],
                'source': 0, 'context_settings': []}
    def prop(node, values):
        element = ET.SubElement(properties, 'properties', node_id=str(node), format='pickle')
        element.text = base64.b64encode(pickle.dumps(values)).decode('ascii')
    prop(0, settings)
    if 'association' in filename:
        prop(2, {'minSupport': 3, 'minConfidence': 35, 'autoFind': True,
                 'filterAntecedentMax': 2, 'filterConsequentMax': 2})
        prop(3, {'minSupport': 3, 'filterMaxItems': 3, 'autoFind': True})
    else:
        prop(2, {'limit_depth': True, 'max_depth': 8, 'min_leaf': 10,
                 'limit_min_leaf': True, 'min_internal': 20,
                 'limit_min_internal': True, 'binary_trees': False})
        prop(4, {'n_neighbors': 15, 'metric_index': 0, 'weight_index': 0})
        prop(5, {'n_estimators': 100, 'use_random_state': True})
        prop(6, {'n_folds': 2, 'cv_stratified': True, 'resampling': 0})
    state=ET.SubElement(root,"session_state")
    ET.SubElement(state,"window_groups")
    ET.indent(root,space="  ")
    ET.ElementTree(root).write(D / filename,encoding="utf-8",xml_declaration=True)

make("Jury 2 - Classification in Orange",
     "Load orange_classification.tab in File. The target column is already marked as class. "
     "Use Test and Score then Confusion Matrix / ROC. The experiment is supplementary.",
     [
         ("File","Orange.widgets.data.owfile.OWFile","Classification data", "(80.0,180.0)"),
         ("Data Table","Orange.widgets.data.owtable.OWTable","Preview data", "(320.0,50.0)"),
         ("Tree","Orange.widgets.model.owtree.OWTreeLearner","Decision Tree", "(325.0,170.0)"),
         ("Naive Bayes","Orange.widgets.model.ownaivebayes.OWNaiveBayes","Naive Bayes", "(325.0,255.0)"),
         ("kNN","Orange.widgets.model.owknn.OWKNNLearner","kNN", "(325.0,340.0)"),
         ("Random Forest","Orange.widgets.model.owrandomforest.OWRandomForest","Random Forest", "(325.0,425.0)"),
         ("Test and Score","Orange.widgets.evaluate.owtestandscore.OWTestAndScore","Test & Score", "(600.0,230.0)"),
         ("Confusion Matrix","Orange.widgets.evaluate.owconfusionmatrix.OWConfusionMatrix","Confusion Matrix", "(850.0,160.0)"),
         ("ROC Analysis","Orange.widgets.evaluate.owrocanalysis.OWROCAnalysis","ROC Analysis", "(850.0,310.0)"),
         ("Distributions","Orange.widgets.visualize.owdistributions.OWDistributions","Distributions", "(95.0,395.0)"),
     ],
     [(0,1,"Data","Data"), (0,6,"Data","Data"),
      (2,6,"Learner","Learner"), (3,6,"Learner","Learner"),
      (4,6,"Learner","Learner"), (5,6,"Learner","Learner"),
      (6,7,"Evaluation Results","Evaluation Results"),
      (6,8,"Evaluation Results","Evaluation Results"),
      (0,9,"Data","Data")],
     "jury2_classification.ows")

make("Jury 2 - FP Growth Association Mining in Orange",
     "Install Orange3-Associate add-on. Load orange_associations.tab into File. "
     "Configure support ~3% and confidence ~35% then press Find Rules.",
     [
         ("File","Orange.widgets.data.owfile.OWFile","Association data", "(65.0,160.0)"),
         ("Data Table","Orange.widgets.data.owtable.OWTable","Review transactions", "(310.0,55.0)"),
         ("Association Rules","orangecontrib.associate.widgets.owassociate.OWAssociate","FP-Growth Rules", "(355.0,205.0)"),
         ("Frequent Itemsets","orangecontrib.associate.widgets.owitemsets.OWItemsets","Frequent Itemsets", "(355.0,360.0)"),
         ("Data Table","Orange.widgets.data.owtable.OWTable","Rule table", "(665.0,195.0)"),
     ],
     [(0,1,"Data","Data"), (0,2,"Data","Data"), (0,3,"Data","Data"),
      (2,4,"Rules","Data")],
     "jury2_association.ows")

for filename in ["jury2_classification.ows","jury2_association.ows"]:
    ET.parse(D / filename)
    print("Valid XML:", filename)
