"""Run with the installed Orange Python, separately from the project environment."""
from pathlib import Path
import json, importlib, importlib.metadata as metadata
from xml.etree import ElementTree as ET
import numpy as np
from AnyQt.QtWidgets import QApplication
from Orange.data import Table
from Orange.evaluation import CrossValidation, CA, F1, AUC
from Orange.classification import TreeLearner, NaiveBayesLearner, KNNLearner, RandomForestLearner
from Orange.widgets.data.owtable import OWTable
from orangecontrib.associate.widgets.owassociate import OWAssociate
from orangecontrib.associate.widgets.owitemsets import OWItemsets
R=Path(__file__).resolve().parents[1]; D=R/'jury_2_dw/orange_demo'
app=QApplication.instance() or QApplication([])
for file in D.glob('*.ows'):
 root=ET.parse(file).getroot(); nodes={}
 for node in root.find('nodes'):
  module,cls=node.attrib['qualified_name'].rsplit('.',1)
  nodes[node.attrib['id']]=getattr(importlib.import_module(module),cls)
 for edge in root.find('links'):
  src=nodes[edge.attrib['source_node_id']]; dst=nodes[edge.attrib['sink_node_id']]
  assert edge.attrib['source_channel'] in [x.name for x in src.get_signals('outputs')]
  assert edge.attrib['sink_channel'] in [x.name for x in dst.get_signals('inputs')]
association=Table(str(D/'orange_associations.tab'))
assert len(association)==3000 and all(v.is_discrete for v in association.domain.attributes)
assert not association.domain.class_vars
w=OWAssociate(); w.minSupport=3; w.minConfidence=35; w.filterAntecedentMax=2; w.filterConsequentMax=2
w.set_data(association); w.find_rules()
assert not w.Error.no_disc_features.is_shown() and w.nRules>0
assert len(w.table_rules)>0
t=OWTable(); t.set_dataset(w.table_rules); t.handleNewSignals()
i=OWItemsets(); i.minSupport=3; i.filterMaxItems=3; i.set_data(association)
assert not i.Error.no_disc_features.is_shown() and i.nItemsets>0
# Reproduce the original symptom with the File widget's default Iris dataset.
bad=OWAssociate(); bad.set_data(Table('iris')); assert bad.Error.no_disc_features.is_shown()
c=Table(str(D/'orange_classification.tab')); assert c.domain.class_var.name=='readmitted'
from Orange.widgets.model.owtree import OWTreeLearner
from Orange.widgets.model.owknn import OWKNNLearner
from Orange.widgets.model.owrandomforest import OWRandomForest
import base64,pickle
scheme=ET.parse(D/'jury2_classification.ows').getroot()
props={int(p.attrib['node_id']):pickle.loads(base64.b64decode(p.text)) for p in scheme.find('node_properties')}
tree_widget=OWTreeLearner()
knn_widget=OWKNNLearner()
forest_widget=OWRandomForest()
for widget,node in [(tree_widget,2),(knn_widget,4),(forest_widget,5)]:
 for key,value in props[node].items(): setattr(widget,key,value)
learners=[tree_widget.create_learner(),NaiveBayesLearner(),knn_widget.create_learner(),forest_widget.create_learner()]
result=CrossValidation(k=5,random_state=42,store_data=True)(c,learners)
assert not any(result.failed)
from Orange.widgets.evaluate.owconfusionmatrix import OWConfusionMatrix
from Orange.widgets.evaluate.owrocanalysis import OWROCAnalysis
from Orange.widgets.visualize.owdistributions import OWDistributions
cm=OWConfusionMatrix(); cm.set_results(result)
roc=OWROCAnalysis(); roc.set_results(result)
dist=OWDistributions(); dist.set_data(c); dist.handleNewSignals()
app.processEvents()
summary={'Orange':metadata.version('Orange3'),'Associate':metadata.version('Orange3-Associate'),'rows':len(c),'discrete_association_features':len(association.domain.attributes),'rules':w.nRules,'itemsets':i.nItemsets,'rule_output_rows':len(w.table_rules),'iris_reproduces_error':True,'five_fold_accuracy':CA(result).tolist(),'five_fold_macro_f1':F1(result,average='macro').tolist(),'five_fold_auc':AUC(result).tolist(),'learners':['Decision Tree','Naive Bayes','KNN','Random Forest'],'widget_checks':['Rules','Itemsets','Rule Table','Confusion Matrix','ROC Analysis','Distributions'],'scope':'Real widget execution; separate from desktop visual verification'}
(R/'deliverables/logs/orange_validation.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
for widget in [w,t,i,bad,cm,roc,dist,tree_widget,knn_widget,forest_widget]: widget.onDeleteWidget(); widget.close()
