# Configuration

A PocketCoffea analysis can be customized by writing a configuration file, containing all the information needed
to setup an analysis run.

The PocketCoffea configuration comprehends:

- Input dataset specification
- Analysis parameters (see [Parameters](./parameters.md) page)
- Custom processor specification
- Skimming, preselection and categories 
- Weights configuration
- Systematic variations configuration
- Histograms output configuration
- Running mode configuration:  local, multiprocessing, cluster

:::{note}
The configuration is wrapped by a `Configurator` object, usually saved in a python script containing a `cfg` variable.
:::

A full simplified example is available
[here](https://github.com/PocketCoffea/AnalysisConfigs/blob/main/configs/zmumu/example_config.py).
In this page we will describe in details all the components of a more complete example about [ttHbb semileptonic channel](https://github.com/PocketCoffea/AnalysisConfigs/blob/main/configs/tests/analysis_config_subsamples.py).

```python    
from pocket_coffea.utils.configurator import Configurator
from pocket_coffea.lib.cut_definition import Cut
from pocket_coffea.lib.cut_functions import get_nObj_min, get_HLTsel,get_nBtagEq,get_nBtagMin
from pocket_coffea.parameters.cuts import passthrough
from pocket_coffea.parameters.histograms import *
import os

from pocket_coffea.workflows.tthbb_base_processor import ttHbbBaseProcessor 

# importing custom cut functions
from custom_cut_functions import *
localdir = os.path.dirname(os.path.abspath(__file__))

# Loading default parameters
from pocket_coffea.parameters import defaults
default_parameters = defaults.get_default_parameters()
defaults.register_configuration_dir("config_dir", localdir+"/params")

# merging additional analysis specific parameters
parameters = defaults.merge_parameters_from_files(default_parameters,
                                                  f"{localdir}/params/object_preselection.yaml",
                                                  f"{localdir}/params/btagsf_calibration.yaml",
                                                  f"{localdir}/params/triggers.yaml",
                                                  update=True)

# Configurator instance
cfg = Configurator(
    parameters = parameters,
    datasets = {
        "jsons": [f"{localdir}/datasets/backgrounds_MC_ttbar_2018.json",
                  f"{localdir}/datasets/backgrounds_MC_ttbar_2017.json",
                  f"{localdir}/datasets/DATA_SingleEle.json",
                  f"{localdir}/datasets/DATA_SingleEle.json",
                    ],
        "filter" : {
            "samples": ["TTToSemiLeptonic","DATA_SingleEle","DATA_SingleEle"],
            "samples_exclude" : [],
            "year": ['2018','2017']
        },
        "subsamples":{
            "TTToSemiLeptonic": {
                "=1b":  [get_nBtagEq(1, coll="Jet")],
                "=2b" : [get_nBtagEq(2, coll="Jet")],
                ">2b" : [get_nBtagMin(3, coll="Jet")]
            }
        }
    },

    workflow = ttHbbBaseProcessor,
    workflow_options = {},
    
    # Skimming and categorization
    skim = [
             get_nObj_min(4, 15., "Jet"),
             get_HLTsel()
             ],
             
    preselections = [semileptonic_presel_nobtag],
    
    categories = {
        "baseline": [passthrough],
        "1b" : [ get_nBtagEq(1, coll="BJetGood")],
        "2b" : [ get_nBtagEq(2, coll="BJetGood")],
        "3b" : [ get_nBtagEq(3, coll="BJetGood")],
        "4b" : [ get_nBtagEq(4, coll="BJetGood")]
    },
    
    # Weights configuration
    weights = {
        "common": {
            "inclusive": ["genWeight","lumi","XS",
                          "pileup",
                          "sf_ele_reco", "sf_ele_id",
                          "sf_mu_id","sf_mu_iso",
                          "sf_btag", "sf_jet_puId", 
                          ],
            "bycategory" : {
            }
        },
        "bysample": {
             "inclusive": [],
             "bycategory": {}
        }
    },

    variations = {
        "weights": {
            "common": {
                "inclusive": [  "pileup",
                                "sf_ele_reco", "sf_ele_id",
                                "sf_mu_id", "sf_mu_iso", "sf_jet_puId",
                                "sf_btag"                               
                              ],
                "bycategory" : {
                }
            },
            "bysample": {
                "inclusive": [],
                "bycategory": {}
            } 
        },
        "shape": {
        ....
        }
    },

    
   variables = {
        **ele_hists(coll="ElectronGood", pos=0),
        **muon_hists(coll="MuonGood", pos=0),
        **count_hist(name="nElectronGood", coll="ElectronGood",bins=3, start=0, stop=3),
        **count_hist(name="nMuonGood", coll="MuonGood",bins=3, start=0, stop=3),
        **count_hist(name="nJets", coll="JetGood",bins=10, start=4, stop=14),
        **count_hist(name="nBJets", coll="BJetGood",bins=12, start=2, stop=14),
        **jet_hists(coll="JetGood", pos=0),
        **jet_hists(coll="JetGood", pos=1),
        **jet_hists(coll="JetGood", pos=2),
    },

    columns = {
        "common": {
             "inclusive": [],
             "bycategory": {}
        },
        "bysample": {
            "TTToSemiLeptonic" : { "inclusive":  [ColOut("LeptonGood",["pt","eta","phi"])]},
            "TTToSemiLeptonic__=1b" :{ "inclusive":  [ColOut("JetGood",["pt","eta","phi"])]},
            "TTToSemiLeptonic__=2b":{ "inclusive":  [ColOut("BJetGood",["pt","eta","phi"])]},
        }
    }
)

run_options = {
        "executor"       : "dask/lxplus",
        "env"            : "singularity",
        "workers"        : 1,
        "scaleout"       : 50,
        "worker_image"   : "/cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cms-analysis/general/pocketcoffea:lxplus-cc7-latest",
        "queue"          : "microcentury",
        "walltime"       : "00:40:00",
        "mem_per_worker" : "4GB", # GB
        "disk_per_worker" : "1GB", # GB
        "exclusive"      : False,
        "chunk"          : 400000,
        "retries"        : 50,
        "treereduction"  : 20,
        "adapt"          : False,
        
    }
```
                

## Datasets

The dataset configuration has the following structure:

```python
cfg = Configurator(
    datasets = {
        "jsons": [f"{localdir}/datasets/backgrounds_MC_ttbar_2018.json",
                  f"{localdir}/datasets/backgrounds_MC_ttbar_2017.json",
                  f"{localdir}/datasets/DATA_SingleEle.json",
                  f"{localdir}/datasets/DATA_SingleEle.json",
                    ],
        "filter" : {
            "samples": ["TTToSemiLeptonic","DATA_SingleEle","DATA_SingleEle"],
            "samples_exclude" : [],
            "year": ['2018','2017']
        },
        "subsamples":{
            "TTToSemiLeptonic": {
                "=1b":  [get_nBtagEq(1, coll="Jet")],
                "=2b" : [get_nBtagEq(2, coll="Jet")],
                ">2b" : [get_nBtagMin(3, coll="Jet")]
            }
        }
    },
    ....
    )
```

- The `jsons` key contains the list of dataset definition file to consider as inputs
- The `filter` dictionary gives the user the possibility to filter on the fly the desidered samples to include or
  exclude from the full list taken from the jsons files. Samples can be filtered by name of by year.
  
- `subsamples` makes possible to define cuts splitting the events in multiple sub-samples. See
  the [datasets](./datasets.md) page for a more in-depth definition of them. A list of Cut objects is used to define the
  subsample, an AND between them is used to mask the events. 
  
  In the example, by using the `subsamples` option
  effectively the `TTToSemiLeptonic` sample will be split in the framework in 3 pieces called  `TTToSemiLeptonic__=1b`,
  `TTToSemiLeptonic__=2b`, `TTToSemiLeptonic__>2b`. 
  
  :::{warning}
  Subsamples do not need to be exclusive. Subsample masks are applied before exporting histograms, columns and counting events.
  :::


## Workflow

```python
from pocket_coffea.workflows.tthbb_base_processor import ttHbbBaseProcessor

"workflow" : ttHbbBaseProcessor,
"worflow_options" : {},
```

- `workflow` key specifies directly the class to use.
- `workflow_options`: dictionary with additional options for specific processors (user defined)

  
## Cuts and categories

The events skimming, preselection and categorization is defined in a structured way in PocketCoffea:
see [Concepts#Filtering](./concepts.md#filtering) for a detailed explanation of the difference between the steps.

```python
cfg = Configurator(
   skim = [
                get_nObj_min(4, 15., "Jet"),
                get_HLTsel()
                ],

   preselections = [semileptonic_presel_nobtag],

   categories = StandardSelection({
          "baseline": [passthrough],
           "1b" : [ get_nBtagEq(1, coll="BJetGood")],
           "2b" : [ get_nBtagEq(2, coll="BJetGood")],
           "3b" : [ get_nBtagEq(3, coll="BJetGood")],
           "4b" : [ get_nBtagEq(4, coll="BJetGood")]
      }),
   ....
)
```

A `Cut` is a simple object grouping a name, a cut function, a dictionary of parameters.
The same `Cut` object can be used in different points of the configuration.
The `Cut` objects are defined in `pocket_coffea.lib.cut_definition`.
Have a look at the documentation about the [Cut object](./concepts.md#cut-object) and its
[API](pocket_coffea.lib.cut_definition). 

PocketCoffea implements a set of **factory methods** for common cut functions: they are defined in [cut_functions](pocket_coffea.lib.cut_functions).

In the configuration the categorization is split in:

- **Skim**:
     The skim configuration is a list of `Cut` object. Events passing the **AND** of the list of cuts pass the skim.
- **Preselections**:
     The preselection is a list of `Cut` object and **AND** between them is applied.

     :::{alert}
     **N.B.**: The preselection cut is applied after objects preselections and cleaning. 
     :::

- **Categories**: Splitting of events for histograms and columns output.


### Categorization utilities
PocketCoffea defines different ways to categorize events. 
The code is available at [pocket_coffea.lib.categorization](pocket_coffea.lib.categorization).

- **StandardSelection**:
     handles the definition of categories from a dictionary of Cut objects. Each key defines a category with a list of
     `Cut` objects which are applied with an **AND**.
     
    ```python
    categories = StandardSelection({
          "baseline": [passthrough],
           "1b" : [ get_nBtagEq(1, coll="BJetGood")],
           "2b" : [ get_nBtagEq(2, coll="BJetGood")],
           "3b" : [ get_nBtagEq(3, coll="BJetGood")],
           "4b" : [ get_nBtagEq(4, coll="BJetGood")]
      }),
    ```
     
- **CartesianSelection**: 
    handles the definition of cartesian product of categories. The class keeps a list of
    [MultiCut](pocket_coffea.lib.categorization.MultiCut) objects, each defining a set of subcategories (or bins).
    The `CartesianSelection` utils defines automatically categories which are the cartesian products of the bins defined
    by each MultiCut. 
    A `StandardSelection` object can be embedded in the CartesianSelection to defined "common" categories not used in the
    cartesian product.
    This utility can be very useful to build a differential analysis. 
    
    For example, this is the configuration to build categories as
    $((N_{jets} [4,5,>6]) \times (N_{bjets} [3,4,5,>6])) + \text{inclusive} + 4jets40pt$
    
    ```python
    categories = CartesianSelection(
        multicuts = [
            MultiCut(name="Njets",
                     cuts=[
                         get_nObj_eq(4, 15., "JetGood"),
                         get_nObj_eq(5, 15., "JetGood"),
                         get_nObj_min(6, 15., "JetGood"),
                     ],
                     cuts_names=["4j","5j","6j"]),
            MultiCut(name="Nbjet",
                    cuts=[
                         get_nObj_eq(3, 15., "BJetGood"),
                         get_nObj_eq(4, 15., "BJetGood"),
                         get_nObj_eq(5, 15., "BJetGood"),
                         get_nObj_min(6, coll="BJetGood"),
                     ],
                     cuts_names=["3b","4b","5b","6b"])
        ],
        common_cats = StandardSelection({
            "inclusive": [passthrough],
            "4jets_40pt" : [get_nObj_min(4, 40., "JetGood")]
        })
    ),
    ```
    
    
    :::{warning}
    The standard `PackedSelection` utility from coffea can handle a maximum of 64 categories. The `CartesianSelection`
    tool overcomes this limitation internally.
    :::
    
     


## Weights

Weights are handled in PocketCoffea through the `WeightsManager` object (see API :ref:`weightsmanager`).
The configuration file sets which weight is applied to which sample in which category.

```python
                
   "weights": {
        "common": {
            "inclusive": ["genWeight","lumi","XS",
                          "pileup",
                          "sf_ele_reco", "sf_ele_id",
                          "sf_mu_id","sf_mu_iso",
                          "sf_btag",
                          "sf_btag_calib", 
                          ],
            "bycategory" : {
                ....
            }
        },
        "bysample": {
            "ttHbb": {
                 "inclusive" : ["sf_jet_puId"],
                 "bycategory": {
                    ....
                 }
            }
        }
    }
```


To reduce boilerplate configuration the weights are specified following a `decision-tree` style and applied in a hierarchical fashion. 
Weights can be assigned to all samples (`common` key), inclusively or by category.
Weights can also be assigned to specific samples, again inclusively or in specific categories.

   
A set of *predefined weights* with centrally produced corrections and scale factors for the CMS Run2 ultra-legacy
analysis have been already implemented in PocketCoffea and are available in the configuration by using string
identifiers:

- **genWeight**: MC generator weight
- **lumi**
- **XS**: sample cross-section
- **pileup**: pileup scale factor
- **sf_ele_reco**, **sf_ele_id**: electron reconstruction and ID scalefactors. The working point is defined by the
  `finalstate` configuration.
- **sf_mu_id**, **sf_mu_iso**: muon id and isolation SF.
- **sf_btag**: btagPOG shape scale factors
- **sf_btag_calib**: custom computed btag SF corrections for ttHbb
- **sf_jet_puId**:  jet puID SF

If a weight is requested in the configuration, but it doens't exist, the framework emits an error before running.

## On-the-flight custom weights

Weights can be created by the user directly in the configuration. The `WeightCustom` object allows to create
a function with a name that get called for each chunk to produce an array of weights (and optionally their variations).
Have a look at the API :ref:`weightsmanager`. 

```python

   WeightCustom(
      name="custom_weight",
      function= lambda events, size, metadata: [("pt_weight", 1 + events.JetGood[:,0].pt/400.)]
   )
```

The custom weight can be added in the configuration instead of the string identifier of centrally-defined weights.

```python
   custom_w = WeightCustom(
      name="custom_weight",
      function= lambda events, size, metadata: [("pt_weight", 1 + events.JetGood[:,0].pt/400.)]
   )

    "weights": {
        "common": {
            "inclusive": [... ],
            "bycategory" : {
                "3jets": [custom_w]
            }
        }
   }
```


The user can create a library of custom weights and include them in the configuration.



## Variations

## Histograms configuration
 