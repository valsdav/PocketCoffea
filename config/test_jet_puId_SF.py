from PocketCoffea.parameters.cuts.baseline_cuts import semileptonic_presel, passthrough
from config.parton_matching.functions import *
from PocketCoffea.lib.cut_definition import Cut
from PocketCoffea.lib.cut_functions import get_nObj, get_nBtag
from PocketCoffea.workflows.base import ttHbbBaseProcessor

cfg =  {

    "dataset" : {
        "jsons": ["datasets/signal_ttHTobb_2018_local.json",
                  "datasets/backgrounds_MC_2018_local.json"],
        "filter" : {
            "samples": ["TTToSemiLeptonic","ttHTobb"],
            "samples_exclude" : [],
            "year": ["2018"]
        }
    },

    # Input and output files
    "workflow" : ttHbbBaseProcessor,
    "output"   : "output/test_jet_puId_SF",
    "workflow_extra_options": {},
    "split_eras" :False,
    "triggerSF" : "PocketCoffea/parameters/semileptonic_triggerSF/triggerSF_2018UL_Ele32_EleHT/sf_trigger_electron_etaSC_vs_electron_pt_2018_Ele32_EleHT_pass_v03.coffea",

    "run_options" : {
        "executor"       : "iterative",
        "workers"        : 1,
        "scaleout"       : 60,
        "partition"      : "standard",
        "walltime"       : "03:00:00",
        "mem_per_worker" : "4GB", # GB
        "exclusive"      : False,
        "chunk"          : 400000,
        "retries"        : 30,
        "max"            : None,
        "skipbadfiles"   : None,
        "voms"           : None,
        "limit"          : 2,
    },
   #"run_options" : {
    #     "executor"       : "dask/slurm",
    #     "workers"        : 1,
    #     "scaleout"       : 120,
    #     "partition"      : "short",
    #     "walltime"       : "01:00:00",
    #     "mem_per_worker" : "8GB", # GB
    #     "exclusive"      : False,
    #     "chunk"          : 500000,
    #     "retries"        : 30,
    #     "treereduction"  : 10,
    #     "max"            : None,
    #     "skipbadfiles"   : None,
    #     "voms"           : None,
    #     "limit"          : None,
    # },


    # Cuts and plots settings
    "finalstate" : "semileptonic",
    "skim": [ get_nBtag(3, 15., coll="Jet")],
    "preselections" : [semileptonic_presel] ,

    "categories": {
        "noSF" : [passthrough],
        "SF": [passthrough],
    },

    "weights": {
        "common": {
            "inclusive": ["genWeight","lumi","XS", "pileup", "sf_ele_reco_id", "sf_mu_id_iso","sf_btag"],
            "bycategory" : {
                "SF" : ["sf_jet_puId"],
            }
        },
    },
    
    "variables" : {
        "muon_pt" : {'binning' : {'n_or_arr' : 100, 'lo' : 0, 'hi' : 500}, 'xlim' : (0,500),  'xlabel' : "$p_{T}^{\mu}$ [GeV]"},
        "muon_eta" : None,
        "muon_phi" : None,
        "electron_pt" : None,
        "electron_eta" : None,
        "electron_phi" : None,
        "jet_pt" : None,
        "jet_eta" : None,
        "jet_phi" : None,
        "jet_btagDeepFlavB" : None,
        "nmuon" : None,
        "nelectron" : None,
        "nlep" : None,
        "nmuon" : None,
        "nelectron" : None,
        "nlep" : None,
        "njet" : None,
        "nbjet" : None,
        "Ht" : {'binning' : {'n_or_arr' : 100, 'lo' : 0, 'hi' : 2500}, 'xlim':(0, 500), 'xlabel' : "$H_T$ Jets [GeV]"},
    },
     "variables2d" : {
         "Njet_Ht": {
             "Njet": {'binning': {"n_or_arr": [4,5,6,7,8,9,11,20]}, "xlabel":"N Jets"},
             "Ht": {'binning': {"n_or_arr": [0,500,650,800,1000,1200,1400,1600, 1800, 2000, 5000]}, "ylabel":"$H_T$ Jets"}
         },
     },
    "scale" : "log"
}
