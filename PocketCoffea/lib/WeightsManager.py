from itertools import chain
from dataclasses import dataclass, field
from typing import List, Tuple
import awkward as ak
from functools import wraps
from collections.abc import Callable
from collections import defaultdict
from pprint import pprint

from coffea.analysis_tools import Weights
# Scale factors functions
from .scale_factors import (sf_ele_reco, sf_ele_id, sf_ele_trigger,
                            sf_mu, sf_btag, sf_btag_calib, sf_jet_puId)
from ..lib.pileup import sf_pileup_reweight

# Framework parameters
from ..parameters.lumi import lumi, goldenJSON
from ..parameters.samples import samples_info
from ..parameters.btag import btag, btag_variations

@dataclass
class WeightCustom():
    name: str
    function: Callable[[ak.Array, Weights, dict], ak.Array]
    variations: List[str] = None

    
class WeightsManager():    
    '''
    The WeightManager class handles the
    weights defined by the framework and custom weights created
    by the user in the processor or by configuration.

    It handles inclusive or bycategory weights for each sample.
    Weights can be inclusive or by category.
    Moreover, different samples can have different weights, as defined in the weights_configuration.
    The name of the weights available in the current workflow are defined in the class methods "available_weights"
     
    '''
    @classmethod
    def available_weights(cls):
        return set(['genWeight', 'lumi', 'XS', 'pileup',
                    'sf_ele_reco', 'sf_ele_id', 'sf_ele_trigger',
                    'sf_mu_id', 'sf_mu_iso',
                    'sf_btag', 'sf_btag_calib',
                    'sf_jet_puId'])

    @classmethod
    def available_variations(cls):
        out = ["nominal", "pileup","sf_ele_reco", "sf_ele_id",
                "sf_mu_id", "sf_mu_iso","sf_jet_puId"]
        for year, bvars in btag_variations.items():
            out += [ f"sf_btag_{var}" for var in bvars]
        return set(out)

    def __init__(self, weightsConf, size, events, metadata, storeIndividual=False):
        self._sample = metadata["sample"]
        self._year = metadata["year"]
        self._finalstate =metadata["finalstate"]
        self.weightsConf = weightsConf
        self.storeIndividual = storeIndividual
        self.size = size
        # looping on the weights configuration to create the
        # Weights object for the current sample        
        #Inclusive weights
        self._weightsIncl = Weights(size, storeIndividual)
        self._weightsByCat = {}
        # Dictionary keeping track of which modifier can be applied to which region
        self._available_modifiers_inclusive = []
        self._available_modifiers_bycat = defaultdict(list)

        _weightsCache = {}

        def __add_weight(w, weight_obj):
            installed_modifiers = []
            # If the Weight is a name look into the predefined weights
            if isinstance(w, str):
                if w not in WeightsManager.available_weights():
                    # it means that the weight is defined in a processor.
                    # The configurator has already checked that it is defined somewhere.
                    # DO nothing
                    return
                if w not in _weightsCache:
                    _weightsCache[w] = self._compute_weight(w, events)
                for we in _weightsCache[w]:
                    weight_obj.add(*we)
                    if len(we)> 2:
                        # the weights has variations
                        installed_modifiers += [we[0]+"Up", we[0]+"Down"]
            # If the Weight is a Custom weight just run the function
            elif isinstance(w, WeightCustom):
                if w.name not in _weightsCache:
                    _weightsCache[w.name] =  w.function(events, metadata)
                for we in _weightsCache[w.name]:
                    # print(we)
                    weight_obj.add(*we)
                    if len(we)> 2:
                        # the weights has variations
                        installed_modifiers += [we[0]+"Up", we[0]+"Down"]
            return installed_modifiers

        # Compute first the inclusive weights
        for w in self.weightsConf["inclusive"]:
            # print(f"Adding weight {w} inclusively")
            modifiers = __add_weight(w, self._weightsIncl)
            # Save the list of availbale modifiers
            self._available_modifiers_inclusive += modifiers

        # Now weights for dedicated categories
        if self.weightsConf["is_split_bycat"]:
            #Create the weights object only if for the current sample
            #there is a weights_by_category configuration
            for cat, ws in self.weightsConf["bycategory"].items():
                if len(ws) == 0: continue
                self._weightsByCat[cat] = Weights(size, storeIndividual)
                for w in ws:
                    # print(f"Adding weight {w} in category {cat}")
                    modifiers = __add_weight(w, self._weightsByCat[cat])
                    self._available_modifiers_bycat[cat] += modifiers

        # make the variations unique 
        self._available_modifiers_inclusive = set(self._available_modifiers_inclusive)
        self._available_modifiers_bycat = { k:set(v) for k,v in self._available_modifiers_bycat.items()}

        # print("Weights modifiers inclusive", self._available_modifiers_inclusive)
        # print("Weights modifiers bycat", self._available_modifiers_bycat)
        #Clear the cache once the Weights objects have been added
        _weightsCache.clear()
                       
    def _compute_weight(self, weight_name, events):
        '''
        Predefined common weights.
        The function return a list of tuples containing a
        weighs and its variations in each tuple.
        [("name", nominal, up, donw),
         ("name", nominal, up, down)]
        Each variation is then added to the Weights object by the caller
        in the constructor. 
        ''' 
        if weight_name == "genWeight":
            return [('genWeight', events.genWeight)]
        elif weight_name == 'lumi':
            return [('lumi', ak.full_like(events.genWeight, lumi[self._year]["tot"]))]
        elif weight_name == 'XS':
            return [('XS', ak.full_like(events.genWeight, samples_info[self._sample]["XS"]))]
        elif weight_name == 'pileup':
            # Pileup reweighting with nominal, up and down variations
            return [('pileup', *sf_pileup_reweight(events, self._year))]
        elif weight_name == 'sf_ele_reco':
            # Electron reco and id SF with nominal, up and down variations
            return [('sf_ele_reco', *sf_ele_reco(events, self._year))]
        elif weight_name == "sf_ele_id":
            return [('sf_ele_id',   *sf_ele_id(events, self._year))]
        elif weight_name == "sf_ele_trigger":
            return [('sf_ele_trigger', *sf_ele_trigger(events, self._year))]
        elif weight_name == 'sf_mu_id':
            # Muon id and iso SF with nominal, up and down variations
            return [('sf_mu_id',  *sf_mu(events, self._year, 'id'))]
        elif weight_name == "sf_mu_iso":
            return [('sf_mu_iso', *sf_mu(events, self._year, 'iso'))]
        elif weight_name == 'sf_btag':
            btag_vars = btag_variations[self._year]
            # Get all the nominal and variation SF
            btagsf = sf_btag(events.JetGood,btag[self._year]['btagging_algorithm'] ,
                             self._year, variations=["central"]+btag_vars,
                             njets = events.nJetGood)
            # BE AWARE --> COFFEA HACK FOR MULTIPLE VARIATIONS
            for var in btag_vars:
                # Rescale the up and down variation by the central one to
                # avoid double counting of the central SF when adding the weights
                # as separate entries in the Weights object.
                btagsf[var][1] = btagsf[var][1]/ btagsf["central"][0]
                btagsf[var][2] = btagsf[var][2] / btagsf["central"][0]

            # return the nominal and everything
            return [(f"sf_btag_{var}", *weights) for var, weights in btagsf.items()]

        elif weight_name == 'sf_btag_calib':
            # This variable needs to be defined in another method
            jetsHt = ak.sum(abs(events.JetGood.pt), axis=1)
            return [("sf_btag_calib", sf_btag_calib(self._sample, self._year, events.nJetGood, jetsHt ) )]

        elif weight_name == 'sf_jet_puId':
            return [('sf_jet_puId', *sf_jet_puId(events.JetGood, self._finalstate,
                                                       self._year, njets=events.nJetGood))]

                
    def add_weight(self, name, nominal, up=None, down=None, category=None):
        '''
        Add manually a weight to a specific category
        '''
        if category==None:
            # add the weights to all the categories (inclusive)
            self._weightsIncl.add(name, nominal, up, down)
        else:
            self._weightsBinCat[category].add(name, nominal, up, down)

    
    def get_weight(self, category=None, modifier=None):
        '''
        The function returns the total weights stored in the processor for the current sample.
        If category==None the inclusive weight is returned.
        If category!=None but weights_split_bycat=False, the inclusive weight is returned.
        Otherwise the inclusive*category specific weight is returned.
        The requested variation==modifier must be available or in the
        inclusive weights, or in the bycategory weights. 
        '''
        if category==None or self.weightsConf["is_split_bycat"] == False or category not in self._weightsByCat:
            # return the inclusive weight
            if modifier!=None and modifier not in self._available_modifiers_inclusive:
                raise ValueError(f"Modifier {modifier} not available in inclusive category")
            return self._weightsIncl.weight(modifier=modifier)
        
        elif category and self.weightsConf["is_split_bycat"] == True :
            # Check if this category has a bycategory configuration
            if modifier == None:
                # Get the nominal both for the inclusive and the split weights
                return self._weightsIncl.weight() * \
                    self._weightsByCat[category].weight()
            else:
                mod_incl = modifier in self._available_modifiers_inclusive
                mod_bycat = modifier in self._available_modifiers_bycat[category]

                if mod_incl and not mod_bycat:
                    # Get the modified inclusive and nominal bycat
                    return self._weightsIncl.weight(modifier=modifier) * \
                        self._weightsByCat[category].weight()
                elif not mod_incl and mod_bycat:
                    # Get the nominal by cat and modified inclusive
                    return self._weightsIncl.weight()*\
                        self._weightsByCat[category].weight(modifier=modifier)
                else:
                    raise ValueError(f"Modifier {modifier} not available in category {category}")
            


    

