import sys
import awkward as ak
from coffea import hist
import numba

from .base import ttHbbBaseProcessor
from ..lib.fill import fill_column_accumulator
from ..lib.deltaR_matching import object_matching
from ..lib.parton_provenance import get_partons_provenance_ttHbb

class LHESignalStudies(ttHbbBaseProcessor):
    def __init__(self,cfg) -> None:
        super().__init__(cfg=cfg)
        self.dr_min = self.cfg.workflow_extra_options.get("lep_lhe_min_dR", 0.4)

        
    def define_common_variables_extra(self):
        # Define the lepton LHE part
         # Getting the LHE collections
        ele_lhe = self.events.LHEPart[(self.events.LHEPart.status == 1)&(abs(self.events.LHEPart.pdgId)==11)]
        self.events["LHE_Electron"] = ele_lhe[ak.argsort(ele_lhe.pt, ascending=False)]
        muon_lhe = self.events.LHEPart[(self.events.LHEPart.status == 1)&(abs(self.events.LHEPart.pdgId)==13)]
        self.events["LHE_Muon"] = muon_lhe[ak.argsort(muon_lhe.pt, ascending=False)]
        tau_lhe = self.events.LHEPart[(self.events.LHEPart.status == 1)&(abs(self.events.LHEPart.pdgId)==15)]
        self.events["LHE_Tau"] = tau_lhe[ak.argsort(tau_lhe.pt, ascending=False)]
        
        lhe_lep = ak.with_name(ak.concatenate((self.events.LHE_Electron,self.events.LHE_Muon, self.events.LHE_Tau),
                                              axis=1), name="PtEtaPhiMCandidate")
        self.events["LHE_Lepton"] = lhe_lep[ak.argsort(lhe_lep.pt, ascending=False)]
        #  Matching the objects with the leptons
        # We want the collection of leptons (not cleaned) matched to the collection of LHE leptons
        matched_ele, matched_lhe_ele, _ = object_matching(self.events.Electron, self.events.LHE_Electron, dr_min=self.dr_min)
        matched_mu, matched_lhe_mu, _ = object_matching(self.events.Muon, self.events.LHE_Muon, dr_min=self.dr_min)
        # Match the tau with the Jets 
        matched_tau, matched_lhe_tau, _ = object_matching(self.events.Jet, self.events.LHE_Tau, dr_min=self.dr_min)

        self.events["LHE_matched_ele"] = matched_ele
        self.events["LHE_matched_muon"] = matched_mu
        self.events["LHE_matched_tau"] = matched_tau
        # Count the number of partons at differenct 
        self.events["nLHE_Electron"] = ak.fill_none(ak.count(self.events.LHE_Electron.pt, axis=1) , 0.)
        self.events["nLHE_Muon"] = ak.fill_none(ak.count(self.events.LHE_Muon.pt, axis=1), 0.)
        self.events["nLHE_Tau"] = ak.fill_none(ak.count(self.events.LHE_Tau.pt, axis=1), 0.)
        self.events["nLHE_Lepton"] =  self.events["nLHE_Electron"] + self.events["nLHE_Muon"]+self.events["nLHE_Tau"]
        

