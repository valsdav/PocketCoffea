import os
import copy
import argparse

import awkward as ak
import numpy as np
import math
import uproot
import correctionlib
from vector import MomentumObject4D

from coffea import hist, lookup_tools
from coffea.nanoevents.methods import nanoaod

from parameters.preselection import object_preselection
from parameters.jec import JECjsonFiles, JECversions

ak.behavior.update(nanoaod.behavior)
    
def lepton_selection(events, Lepton, finalstate):

    leptons = events[Lepton]
    cuts = object_preselection[finalstate][Lepton]
    # Requirements on pT and eta
    passes_eta = (np.abs(leptons.eta) < cuts["eta"])
    passes_pt = (leptons.pt > cuts["pt"])

    if Lepton == "Electron":
        # Requirements on SuperCluster eta, isolation and id
        etaSC = np.abs(leptons.deltaEtaSC + leptons.eta)
        passes_SC = np.invert((etaSC >= 1.4442) & (etaSC <= 1.5660))
        passes_iso = leptons.pfRelIso03_all < cuts["iso"]
        passes_id = (leptons[cuts['id']] == True)

        good_leptons = passes_eta & passes_pt & passes_SC & passes_iso & passes_id

    elif Lepton == "Muon":
        # Requirements on isolation and id
        passes_iso = leptons.pfRelIso04_all < cuts["iso"]
        passes_id = (leptons[cuts['id']] == True)

        good_leptons = passes_eta & passes_pt & passes_iso & passes_id

    return leptons[good_leptons]


def init_jec_correctors():
    '''
    All the possible JEC correctors are initialized and returned as a dictionary
    '''
    jec_correctors = {}
    for year, files in JECjsonFiles.items():
        for jetType, jsonfile in files.items():
            if jetType == "AK8PFpuppi": continue #not implemented yet
            JECfile = correctionlib.CorrectionSet.from_file(jsonfile)
            # TODO: This is not working with data (list of eras)
            corrMC = JECfile.compound[f'{JECversions[year]["MC"]}_L1L2L3Res_{jetType}']
            # TODO Do the same for data with eras
            jec_correctors[(year, jetType, "MC")] = corrMC
    return jec_correctors

# example here: https://gitlab.cern.ch/cms-nanoAOD/jsonpog-integration/-/blob/master/examples/jercExample.py
def jet_correction(events, Jet, corrector, verbose=False):
    # until correctionlib handles jagged data natively we have to flatten and unflatten
    jets = events[Jet]
    jets['pt_raw'] = (1 - jets['rawFactor']) * jets['pt']
    jets['mass_raw'] = (1 - jets['rawFactor']) * jets['mass']
    jets['rho'] = ak.broadcast_arrays(events.fixedGridRhoFastjetAll, jets.pt)[0]
    j, nj = ak.flatten(jets), ak.num(jets)
    flatCorrFactor = corrector.evaluate( np.array(j['area']), np.array(j['eta']), np.array(j['pt_raw']), np.array(j['rho']) )
    corrFactor = ak.unflatten(flatCorrFactor, nj)

    corrected_jets = copy.copy(jets)
    corrected_jets['pt'] = jets['pt_raw']* corrFactor
    corrected_jets['mass'] = jets['mass_raw']* corrFactor

    if verbose:
        print()
        print(events.event[0], 'starting columns:',ak.fields(jets), end='\n\n')

        print(events.event[0], 'untransformed pt ratios',jets.pt/jets.pt_raw)
        print(events.event[0], 'untransformed mass ratios',jets.mass/jets.mass_raw)

        print(events.event[0], 'transformed pt ratios',corrected_jets.pt/corrected_jets.pt_raw)
        print(events.event[0], 'transformed mass ratios',corrected_jets.mass/corrected_jets.mass_raw)

        print()
        print(events.event[0], 'transformed columns:', ak.fields(corrected_jets), end='\n\n')

        #print('JES UP pt ratio',corrected_jets.JES_jes.up.pt/corrected_jets.pt_raw)
        #print('JES DOWN pt ratio',corrected_jets.JES_jes.down.pt/corrected_jets.pt_raw, end='\n\n')

    return corrected_jets



# N.B.: This function works only with awkward v1.5.1 & coffea v0.7.9, it doesn't work with awkward 1.7.0 & coffea v0.7.11
def jet_selection(events, Jet, finalstate, btag=None):

    jets = events[Jet]
    cuts = object_preselection[finalstate][Jet]
    # Only jets that are more distant than dr to ALL leptons are tagged as good jets
    leptons = events["LeptonGood"]
    # Mask for  jets not passing the preselection
    presel_mask = (jets.pt > cuts["pt"]) & (np.abs(jets.eta) < cuts["eta"]) & (jets.jetId >= cuts["jetId"])
    # Lepton cleaning
    dR_jets_lep = jets.metric_table(leptons)
    lepton_cleaning_mask = ak.prod(dR_jets_lep> cuts["dr"], axis=2) == 1

    if Jet == "Jet":
       jetpuid_mask  =  ( (jets.pt < cuts["puId_ptlim"]) & (jets.puId >= cuts["puId"]) ) | (jets.pt >= 50) 
       good_jets_mask = presel_mask & lepton_cleaning_mask & jetpuid_mask
       
    elif Jet == "FatJet":
        raise NotImplementedError

    return jets[good_jets_mask], good_jets_mask


def btagging(Jet, btag):
    return  Jet[Jet[btag["btagging_algorithm"]] > btag["btagging_WP"]]


def get_dilepton(electrons, muons, transverse=False):

    fields = {
            "pt": None,
            "eta": None,
            "phi": None,
            "mass": None,
            "charge": None,
    }

    electrons = ak.pad_none(electrons, 2)
    muons = ak.pad_none(muons, 2)

    nelectrons = ak.num(electrons[~ak.is_none(electrons, axis=1)])
    nmuons = ak.num(muons[~ak.is_none(muons, axis=1)])

    ee = electrons[:,0] + electrons[:,1]
    mumu = muons[:,0] + muons[:,1]
    emu = electrons[:,0] + muons[:,0]

    for var in fields.keys():
        fields[var] = ak.where( ((nelectrons + nmuons) == 2) & (nelectrons == 2), getattr(ee, var), getattr(ee, var) )
        fields[var] = ak.where( ((nelectrons + nmuons) == 2) & (nmuons == 2), getattr(mumu, var), fields[var] )
        fields[var] = ak.where( ((nelectrons + nmuons) == 2) & (nelectrons == 1) & (nmuons == 1), getattr(emu, var), fields[var] )

    if transverse:
        fields["eta"] = ak.zeros_like(fields["pt"])
    dileptons = ak.zip(fields, with_name="PtEtaPhiMCandidate")

    return dileptons

def get_diboson(dileptons, MET, transverse=False):

    fields = {
            "pt": MET.pt,
            "eta": ak.zeros_like(MET.pt),
            "phi": MET.phi,
            "mass": ak.zeros_like(MET.pt),
            "charge": ak.zeros_like(MET.pt),
    }

    METs = ak.zip(fields, with_name="PtEtaPhiMCandidate")
    if transverse:
        dileptons_t = dileptons[:]
        dileptons_t["eta"] = ak.zeros_like(dileptons_t.eta)
        dibosons = (dileptons_t + METs)
    else:
        dibosons = (dileptons + METs)

    return dibosons

def get_charged_leptons(electrons, muons, charge, mask):

    fields = {
            "pt": None,
            "eta": None,
            "phi": None,
            "mass": None,
            "energy": None,
            "charge": None,
            "x": None,
            "y": None,
            "z": None,
    }

    nelectrons = ak.num(electrons)
    nmuons = ak.num(muons)
    mask_ee = mask & ((nelectrons + nmuons) == 2) & (nelectrons == 2)
    mask_mumu = mask & ((nelectrons + nmuons) == 2) & (nmuons == 2)
    mask_emu = mask & ((nelectrons + nmuons) == 2) & (nelectrons == 1) & (nmuons == 1)

    for var in fields.keys():
        if var in ["eta", "phi"]:
            default = ak.from_iter(len(electrons)*[[-9.]])
        else:
            default = ak.from_iter(len(electrons)*[[-999.9]])
        if not var in ["energy", "x", "y", "z"]:
            fields[var] = ak.where( mask_ee, electrons[var][electrons.charge == charge], default )
            fields[var] = ak.where( mask_mumu, muons[var][muons.charge == charge], fields[var] )
            fields[var] = ak.where( mask_emu & ak.any(electrons.charge == charge, axis=1), electrons[var][electrons.charge == charge], fields[var] )
            fields[var] = ak.where( mask_emu & ak.any(muons.charge == charge, axis=1), muons[var][muons.charge == charge], fields[var] )
            fields[var] = ak.flatten(fields[var])
        else:
            fields[var] = ak.where( mask_ee, getattr(electrons, var)[electrons.charge == charge], default )
            fields[var] = ak.where( mask_mumu, getattr(muons, var)[muons.charge == charge], fields[var] )
            fields[var] = ak.where( mask_emu & ak.any(electrons.charge == charge, axis=1), getattr(electrons, var)[electrons.charge == charge], fields[var] )
            fields[var] = ak.where( mask_emu & ak.any(muons.charge == charge, axis=1), getattr(muons, var)[muons.charge == charge], fields[var] )
            fields[var] = ak.flatten(fields[var])

    charged_leptons = ak.zip(fields, with_name="PtEtaPhiMCandidate")

    return charged_leptons

def jet_nohiggs_selection(jets, mask_jets, fatjets, dr=1.2):

    #nested_mask = jets.p4.match(fatjets.p4[mask_fatjets,0], matchfunc=pass_dr, dr=dr)
    nested_mask = jets.match(fatjets, matchfunc=pass_dr, dr=dr)
    jets_pass_dr = nested_mask.all()

    return mask_jets & jets_pass_dr

