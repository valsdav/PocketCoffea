import os
import sys
import json
from copy import deepcopy
from pprint import pprint, pformat
import cloudpickle
from collections import defaultdict
import inspect
import logging

from ..lib.cut_definition import Cut
from ..lib.categorization import StandardSelection, CartesianSelection
from ..parameters.cuts.preselection_cuts import passthrough
from ..lib.weights_manager import WeightCustom
from ..lib.hist_manager import Axis, HistConf


class Configurator:
    '''
    Main class driving the configuration of a PocketCoffea analysis.
    The Configurator groups the several aspects that define an analysis run:
    - skims, preselections, categorization
    - output: variables and columns
    - datasets
    - weights and variations
    - workflow
    - analysis parameters

    The running environment configuration is not part of the Configurator class. 
    '''
    def __init__(self,
                 workflow,
                 parameters,
                 datasets,
                 skim,
                 preselections,
                 categories,
                 weights,
                 variations,
                 variables,
                 columns = None,
                 workflow_options = None,
                 save_skimmed_files= None):
        
        # Save the workflow object and its options
        self.workflow = workflow
        self.workflow_options = workflow_options
        self.parameters = parameters
        # Save 
        # Load dataset
        self.datasets_cfg = datasets
        # The following attributes are loaded by load_datasets
        self.fileset = {}
        self.datasets = []
        self.samples = []

        self.subsamples = {}
        self.subsamples_list = [] # List of subsamples (for internal checks)
        self.total_samples_list = [] # List of subsamples and inclusive samples names
        self.has_subsamples = {}

        self.years = []
        self.eras = []

        self.load_datasets()
        self.load_subsamples()

        # Load histogram settings
        # No manipulation is needed, maybe some check can be added
        self.variables = variables
        
        # Categories: object handling categorization
        # - StandardSelection
        # - CartesianSelection
        ## Call the function which transforms the dictionary in the cfg
        # in the objects needed in the processors
        self.skim = []
        self.preselections = []
        self.load_cuts_and_categories(skim, preselections, categories)

        ## Weights configuration
        self.weights_config = {
            s: {
                "inclusive": [],
                "bycategory": {c: [] for c in self.categories.keys()},
                "is_split_bycat": False,
            }
            for s in self.samples
        }
        self.load_weights_config(weights)

        ## Variations configuration
        # The structure is very similar to the weights one,
        # but the common and inclusive collections are fully flattened on a
        # sample:category structure
        self.variations_config = {
            s: {
                "weights": {c: [] for c in self.categories.keys()},
                "shape": {c: [] for c in self.categories.keys()},
            }
            for s in self.samples
        }
        if "shape" not in variations:
            variations["shape"] = {"common": {"inclusive": []}}

        self.load_variations_config(
            variations["weights"], variation_type="weights"
        )
        self.load_variations_config(
            variations["shape"], variation_type="shape"
        )
        # Collecting overall list of available weights and shape variations per sample
        self.available_weights_variations = {s: ["nominal"] for s in self.samples}
        self.available_shape_variations = {s: [] for s in self.samples}
        for sample in self.samples:
            # Weights variations
            for cat, vars in self.variations_config[sample]["weights"].items():
                self.available_weights_variations[sample] += vars
            # Shape variations
            for cat, vars in self.variations_config[sample]["shape"].items():
                self.available_shape_variations[sample] += vars
            # make them unique
            self.available_weights_variations[sample] = list(
                set(self.available_weights_variations[sample])
            )
            self.available_shape_variations[sample] = list(
                set(self.available_shape_variations[sample])
            )

        # Column accumulator config
        self.columns = {}
        self.load_columns_config(columns)

        # Load workflow passing the Configurator self object
        self.load_workflow()

        # Save config file in output folder
        # self.save_config()


    def load_datasets(self):
        for json_dataset in self.datasets_cfg["jsons"]:
            ds_dict = json.load(open(json_dataset))
            ds_filter = self.datasets_cfg.get("filter", None)
            if ds_filter != None:
                for key, ds in ds_dict.items():
                    pass_filter = True
                    if "samples" in ds_filter:
                        if ds["metadata"]["sample"] not in ds_filter["samples"]:
                            pass_filter = False 
                    if "samples_exclude" in ds_filter:
                        if ds["metadata"]["sample"] in ds_filter["samples_exclude"]:
                            pass_filter = False
                    if "year" in ds_filter:
                        if ds["metadata"]["year"] not in ds_filter["year"]:
                            pass_filter = False
                    if pass_filter:
                        self.fileset[key] = ds
            else:
                self.fileset.update(ds_dict)

        # Now loading and storing the metadata of the filtered fileset
        if len(self.fileset) == 0:
            print("File set is empty: please check you dataset definition...")
            raise Exception("Wrong fileset configuration")
        else:
            for name, d in self.fileset.items():
                m = d["metadata"]
                if name not in self.datasets:
                    self.datasets.append(name)
                if (m["sample"]) not in self.samples:
                    self.samples.append(m["sample"])
                    self.years.append(m["year"])
                if 'era' in m.keys():
                    if (m["era"]) not in self.eras:
                        self.eras.append(m["era"])

    def load_subsamples(self):
        # subsamples configuration
        subsamples_dict = self.datasets_cfg.get("subsamples", {})
        # Save list of subsamples for each sample
        for sample in self.samples:
            if sample in subsamples_dict.keys():
                self.subsamples_list += list(subsamples_dict[sample].keys())
                self.has_subsamples[sample] = True
            else:
                self.has_subsamples[sample] = False

        # Complete list of samples and subsamples
        self.total_samples_list = list(set(self.samples + self.subsamples_list))

        # Now saving the subsamples definition cuts
        for sample in self.samples:
            if sample in subsamples_dict:
                subscfg = subsamples_dict[sample]
                if isinstance(subscfg, dict):
                    # Convert it to StandardSelection
                    self.subsamples[sample] = StandardSelection(subscfg)
                elif isinstance(subscfg, StandardSelection):
                    self.subsamples[sample] = subscfg
                elif isinstance(subscfg, CartesianSelection):
                    self.subsamples[sample] = subscfg
            else:
                # if there is no configured subsample, the full sample becomes its subsample
                self.subsamples[sample] = StandardSelection({sample: [passthrough]})
        # Unique set of cuts
        logging.info("Subsamples:")
        logging.info(self.subsamples)

   
    def load_cuts_and_categories(self, skim: list, preselections: list, categories):
        '''This function loads the list of cuts and groups them in categories.
        Each cut is identified by a unique id (see Cut class definition)'''
        # If the skim, preselection and categories list are empty, append a `passthrough` Cut
        
        if len(skim) == 0:
            skim.append(passthrough)
        if len(preselections) == 0:
            preselections.ppend(passthrough)
            
        if categories == {}:
            categories["baseline"] = [passthrough]

        for sk in skim:
            if not isinstance(sk, Cut):
                print("Please define skim, preselections and cuts as Cut objects")
                raise Exception("Wrong categories/cuts configuration")
            self.skim.append(sk)

        for pres in preselections:
            if not isinstance(pres, Cut):
                print("Please define skim, preselections and cuts as Cut objects")
                raise Exception("Wrong categories/cuts configuration")
            self.preselections.append(pres)

        # Now saving the categories
        if isinstance(categories, dict):
            # Convert it to StandardSelection
            self.categories = StandardSelection(categories)
        elif isinstance(categories, StandardSelection):
            self.categories = categories
        elif isinstance(categories, CartesianSelection):
            self.categories = categories
        # Unique set of cuts
        logging.info("Categories:")
        logging.info(self.categories)

    def load_weights_config(self, wcfg):
        '''This function loads the weights definition and prepares a list of
        weights to be applied for each sample and category'''
       
        # Get the list of statically available weights defined in the workflow
        available_weights = self.workflow.available_weights()
        # Read the config and save the list of weights names for each sample (and category if needed)
        if "common" not in wcfg:
            print("Weights configuration error: missing 'common' weights key")
            raise Exception("Wrong weight configuration")
        # common/inclusive weights
        for w in wcfg["common"]["inclusive"]:
            if isinstance(w, str):
                if w not in available_weights:
                    print(f"Weight {w} not available in the workflow")
                    raise Exception("Wrong weight configuration")
            # do now check if the weights is not string but custom
            for wsample in self.weights_config.values():
                # add the weight to all the categories and samples
                wsample["inclusive"].append(w)

        if "bycategory" in wcfg["common"]:
            for cat, weights in wcfg["common"]["bycategory"].items():
                for w in weights:
                    if isinstance(w, str):
                        if w not in available_weights:
                            print(f"Weight {w} not available in the workflow")
                            raise Exception("Wrong weight configuration")
                    for wsample in self.weights_config.values():
                        wsample["is_split_bycat"] = True
                        # looping on all the samples for this category
                        if w in wsample["inclusive"]:
                            raise Exception(
                                """Error! Trying to include weight {w}
                            by category, but it is already included inclusively!"""
                            )
                        wsample["bycategory"][cat].append(w)

        # Now look at specific samples configurations
        if "bysample" in wcfg:
            for sample, s_wcfg in wcfg["bysample"].items():
                if sample not in self.samples:
                    print(
                        f"Requested missing sample {sample} in the weights configuration"
                    )
                    raise Exception("Wrong weight configuration")

                if "inclusive" in s_wcfg:
                    for w in s_wcfg["inclusive"]:
                        if isinstance(w, str):
                            if w not in available_weights:
                                print(f"Weight {w} not available in the workflow")
                                raise Exception("Wrong weight configuration")
                        # append only to the specific sample
                        self.weights_config[sample]["inclusive"].append(w)

                if "bycategory" in s_wcfg:
                    for cat, weights in s_wcfg["bycategory"].items():
                        for w in weights:
                            if isinstance(w, str):
                                if w not in available_weights:
                                    print(f"Weight {w} not available in the workflow")
                                    raise Exception("Wrong weight configuration")
                            if w in self.weights_config[sample]["inclusive"]:
                                raise Exception(
                                    f"""Error! Trying to include weight {w}
                                by category, but it is already included inclusively!"""
                                )
                            self.weights_config[sample]["bycategory"][cat].append(w)
                            self.weights_config[sample]["is_split_bycat"] = True

        logging.info("Weights configuration")
        logging.info(self.weights_config)


        
    def load_variations_config(self, wcfg, variation_type):
        '''This function loads the variations definition and prepares a list of
        weights to be applied for each sample and category'''
             
        # Get the list of statically available variations defined in the workflow
        available_variations = self.workflow.available_variations()
        # Read the config and save the list of variations names for each sample (and category if needed)

        if "common" not in wcfg:
            print("Variation configuration error: missing 'common' weights key")
            raise Exception("Wrong variation configuration")
        # common/inclusive variations
        for w in wcfg["common"]["inclusive"]:
            if isinstance(w, str):
                if w not in available_variations:
                    print(f"Variation {w} not available in the workflow")
                    raise Exception("Wrong variation configuration")
            # do now check if the variations is not string but custom
            for wsample in self.variations_config.values():
                # add the variation to all the categories and samples
                for wcat in wsample[variation_type].values():
                    wcat.append(w)

        if "bycategory" in wcfg["common"]:
            for cat, variations in wcfg["common"]["bycategory"].items():
                for w in variations:
                    if isinstance(w, str):
                        if w not in available_variations:
                            print(f"Variation {w} not available in the workflow")
                            raise Exception("Wrong variation configuration")
                    for wsample in self.variations_config.values():
                        if w not in wsample[variation_type][cat]:
                            wsample[variation_type][cat].append(w)

        # Now look at specific samples configurations
        if "bysample" in wcfg:
            for sample, s_wcfg in wcfg["bysample"].items():
                if sample not in self.samples:
                    print(
                        f"Requested missing sample {sample} in the variations configuration"
                    )
                    raise Exception("Wrong variation configuration")
                if "inclusive" in s_wcfg:
                    for w in s_wcfg["inclusive"]:
                        if isinstance(w, str):
                            if w not in available_variations:
                                print(f"Variation {w} not available in the workflow")
                                raise Exception("Wrong variation configuration")
                        # append only to the specific sample
                        for wcat in self.variations_config[sample][
                            variation_type
                        ].values():
                            if w not in wcat:
                                wcat.append(w)

                if "bycategory" in s_wcfg:
                    for cat, variation in s_wcfg["bycategory"].items():
                        for w in variation:
                            if isinstance(w, str):
                                if w not in available_variations:
                                    print(
                                        f"Variation {w} not available in the workflow"
                                    )
                                    raise Exception("Wrong variation configuration")
                            self.variations_config[sample][variation_type][cat].append(
                                w
                            )

    def load_columns_config(self, wcfg):
        if wcfg == None:
            wcfg = {}
        for sample in self.samples:
            if self.has_subsamples[sample]:
                for sub in self.subsamples[sample]:
                    self.columns[sub] = {c: [] for c in self.categories.keys()}
            else:
                self.columns[sample] = {c: [] for c in self.categories.keys()}
        # common/inclusive variations
        if "common" in wcfg:
            if "inclusive" in wcfg["common"]:
                for w in wcfg["common"]["inclusive"]:
                    # do now check if the variations is not string but custom
                    for wsample in self.columns.values():
                        # add the variation to all the categories and samples
                        for wcat in wsample.values():
                            wcat.append(w)

            if "bycategory" in wcfg["common"]:
                for cat, columns in wcfg["common"]["bycategory"].items():
                    for w in columns:
                        for wsample in self.columns.values():
                            if w not in wsample[cat]:
                                wsample[cat].append(w)

        # Now look at specific samples configurations
        if "bysample" in wcfg:
            for sample, s_wcfg in wcfg["bysample"].items():
                if sample not in self.total_samples_list:
                    print(
                        f"Requested missing sample {sample} in the columns configuration"
                    )
                    raise Exception("Wrong columns configuration")
                if "inclusive" in s_wcfg:
                    for w in s_wcfg["inclusive"]:
                        # append only to the specific subsample
                        if sample in self.subsamples_list:
                            for wcat in self.columns[sample].values():
                                if w not in wcat:
                                    wcat.append(w)
                        elif self.has_subsamples[sample]:
                            # If it was added to the general one: include only in subsamples
                            for subs in self.subsamples[sample]:
                                for wcat in self.columns[subs].values():
                                    if w not in wcat:
                                        wcat.append(w)
                        else:
                            # Add only to the general sample
                            for wcat in self.columns[sample].values():
                                if w not in wcat:
                                    wcat.append(w)

                if "bycategory" in s_wcfg:
                    for cat, columns in s_wcfg["bycategory"].items():
                        for w in columns:
                            if sample in self.subsamples_list:
                                self.columns[sample][cat].append(w)
                            elif self.has_subsamples[sample]:
                                for subs in self.subsamples[sample].keys():
                                    self.columns[subs][cat].append(w)
                            else:
                                self.columns[sample][cat].append(w)

    # def overwrite_check(self, path):
    #         version = 1
    #         while os.path.exists(path):
    #             tag = str(version).rjust(2, '0')
    #             path = f"{self.output}_v{tag}"
    #             version += 1
    #         if path != self.output:
    #             print(f"The output will be saved to {path}")
    #         self.output = path
    #         self.cfg['output'] = self.output

    def filter_dataset(self, nfiles):
        filtered_dataset = {}
        for sample, ds in self.fileset.items():
            ds["files"] = ds["files"][0:nfiles]
            filtered_dataset[sample] = ds
        self.fileset = filtered_dataset

    # def define_output(self):
    #     self.outfile = os.path.join(self.output, "output_{dataset}.coffea")

    def load_workflow(self):
        self.processor_instance = self.workflow(cfg=self)

    def save_config(self, output):
        ocfg = {}
        ocfg["datasets"] = {"names": self.datasets,
                            "samples": self.samples,
                            "fileset": self.fileset,
                            }
        
        subsamples_cuts = self.subsamples
        dump_subsamples = {}
        for sample, subsamples in subsamples_cuts.items():
            dump_subsamples[sample] = {}
            dump_subsamples[sample] = subsamples.serialize()
        ocfg["datasets"]["subsamples"] = dump_subsamples

        skim_dump = []
        presel_dump = []
        cats_dump = {}
        for sk in self.skim:
            skim_dump.append(sk.serialize())
        for pre in self.preselections:
            presel_dump.append(pre.serialize())

        ocfg["skim"] = skim_dump
        ocfg["preselections"] = presel_dump

        # categories
        ocfg["categories"] = self.categories.serialize()

        ocfg["workflow"] = {
            "name": self.workflow.__name__,
            "workflow_options": self.workflow_options,
            "srcfile": inspect.getsourcefile(self.workflow),
        }

        ocfg["weights"] = {}
        for sample, weights in self.weights_config.items():
            out = {"bycategory": {}, "inclusive": []}
            for cat, catw in weights["bycategory"].items():
                out["bycategory"][cat] = []
                for w in catw:
                    if isinstance(w, WeightCustom):
                        out["bycategory"][cat].append(w.serialize())
                    else:
                        out["bycategory"][cat].append(w)
            for w in weights["inclusive"]:
                if isinstance(w, WeightCustom):
                    out["inclusive"].append(w.serialize())
                else:
                    out["inclusive"].append(w)
            ocfg["weights"][sample] = out

        ocfg["variations"] = self.variations_config
        ocfg["variables"] = {
            key: val.serialize() for key, val in self.variables.items()
        }

        ocfg["columns"] = {
            s: {c: [] for c in self.categories} for s in self.total_samples_list
        }
        for sample, columns in self.columns.items():
            for cat, cols in columns.items():
                for col in cols:
                    ocfg["columns"][sample][cat].append(col.__dict__)

        # Save the serialized configuration in json
        output_cfg = os.path.join(output, "config.json")
        print("Saving config file to " + output_cfg)
        json.dump(ocfg, open(output_cfg, "w"), indent=2)
        # Pickle the configurator object in order to be able to reproduce completely the configuration
        cloudpickle.dump(
            self, open(os.path.join(output, "configurator.pkl"), "wb")
        )


    def __repr__(self):
        s = ['Configurator instance:',
             f"  - Workflow: {self.workflow}",
             f"  - {len(self.samples)} samples: {self.samples}",
             f"  - {len(self.subsamples)} subsamples: {list(self.subsamples.keys())}",
             f"  - Skim: {[c.name for c in self.skim]}",
             f"  - Preselection: {[c.name for c in self.preselections]}",
             f"  - Categories: {self.categories}",
             f"  - Variables:  {list(self.variables.keys())}",
             f"  - Columns: {self.columns}",
             f"  - available weights variations: {self.available_weights_variations} ",
             f"  - available shape variations: {self.available_shape_variations}",
             ]
            
        # - skim
        # - preselection
        # - categories: {self.categories}
        # - workflow: {self.workflow}
        
        return "\n".join(s)

    def __str__(self):
        return repr(self)
