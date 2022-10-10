from PocketCoffea.lib.cut_definition import Cut
import awkward as ak

def n_lhe_leptons(events, params, **kargs):
    return (ak.sum( (abs(events.LHEPart.pdgId) >=11)&(abs(events.LHEPart.pdgId) <19), axis=1)==params["N"])

def n_lhe_semileptons_notau(events, params, **kwargs):
    return (ak.sum( (abs(events.LHEPart.pdgId) >=15)&(abs(events.LHEPart.pdgId) <=19), axis=1)==0)&\
           (ak.sum( (abs(events.LHEPart.pdgId) >=11)&(abs(events.LHEPart.pdgId) <=14), axis=1)==2)

def n_lhe_dilepton_notau(events, params, **kwargs):
    return (ak.sum( (abs(events.LHEPart.pdgId) >=15)&(abs(events.LHEPart.pdgId) <=19), axis=1)==0)&\
           (ak.sum( (abs(events.LHEPart.pdgId) >=11)&(abs(events.LHEPart.pdgId) <=14), axis=1)==4)

def n_lhe_dilepton_onetau(events, params, **kwargs):
    return (ak.sum( (abs(events.LHEPart.pdgId) >=11)&(abs(events.LHEPart.pdgId) <=14), axis=1)==2)&\
        (ak.sum( (abs(events.LHEPart.pdgId) >=15)&(abs(events.LHEPart.pdgId) <=16), axis=1)==2)

def n_lhe_leptons_twotau(events, params, **kwargs):
    return  (ak.sum( (abs(events.LHEPart.pdgId) >=15)&(abs(events.LHEPart.pdgId) <=16), axis=1)==4)

semilep_lhe = Cut(
    name="semilep_lhe",
    params = {"N":2},
    function= n_lhe_leptons
)

semilep_notau_lhe = Cut(
    name="semilep_notau_lhe",
    params = {"N":2},
    function= n_lhe_semileptons_notau
)

dilep_lhe = Cut(
    name="dilep_lhe",
    params = {"N":4},
    function= n_lhe_leptons
)

dilep_notau_lhe = Cut(
    name="dilep_notau_lhe",
    params = {"N":4},
    function= n_lhe_dilepton_notau
)

dilep_onetau_lhe = Cut(
    name="dilep_onetau_lhe",
    params ={},
    function = n_lhe_dilepton_onetau
)
dilep_twotau_lhe = Cut(
    name="dilep_twotau_lhe",
    params ={},
    function = n_lhe_leptons_twotau
)

had_lhe = Cut(
    name="had_lhe",
    params = {"N":0},
    function= n_lhe_leptons
)


### Dilepton selection

def get_dilep(events, params, **kwargs):
    lep_pt = ak.pad_none(events.LeptonGood.pt, 2)
    mask = ( (events.nLeptonGood >=2) &
             (lep_pt[:,0] > params["pt1"] )&
             (lep_pt[:,1] >params["pt2"]))
    return ak.where(ak.is_none(mask), False, mask)

dilep_custom_selection = Cut(
    name="dilep_30_15",
    params={"pt1":30., "pt2":15.},
    function = get_dilep
)
