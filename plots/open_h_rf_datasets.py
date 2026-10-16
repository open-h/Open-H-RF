"""The short name of each dataset, which the website shows and links it by.

DATASETS maps a short name for every dataset card on the Hub (nvidia/Open-H-RF) to its
hf:// path. Collections with sub-cards (oslo, resolvestroke) count once per sub-card;
their parent cards are not listed.
"""

from __future__ import annotations

HF_ROOT = "hf://nvidia/Open-H-RF"

DATASETS = {
    "colorado-boulder": {"hf": f"{HF_ROOT}/colorado-boulder"},
    "concordia": {"hf": f"{HF_ROOT}/concordia"},
    "dartmouth-uct": {"hf": f"{HF_ROOT}/dartmouth-uct"},
    "kaist-snubh-barreleye": {"hf": f"{HF_ROOT}/kaist-snubh-barreleye"},
    "mosaic-nuevosono": {"hf": f"{HF_ROOT}/mosaic-nuevosono"},
    "nv-raw2insights-us": {"hf": f"{HF_ROOT}/nv-raw2insights-us"},
    "oslo-cardiac": {"hf": f"{HF_ROOT}/oslo/A_cardiac"},
    "oslo-carotid": {"hf": f"{HF_ROOT}/oslo/B_carotid"},
    "oslo-verasonics-phantom": {"hf": f"{HF_ROOT}/oslo/C_verasonics_phantom"},
    "oslo-alpinion-phantom": {"hf": f"{HF_ROOT}/oslo/D_alpinion_phantom"},
    "oslo-simulation": {"hf": f"{HF_ROOT}/oslo/E_simulation"},
    "oslo-motion": {"hf": f"{HF_ROOT}/oslo/F_motion"},
    "politorino": {"hf": f"{HF_ROOT}/politorino"},
    "resolvestroke-clinical": {"hf": f"{HF_ROOT}/resolvestroke/clinical"},
    "resolvestroke-flow-phantom": {"hf": f"{HF_ROOT}/resolvestroke/phantom_flow"},
    "resolvestroke-tissue-phantom": {"hf": f"{HF_ROOT}/resolvestroke/phantom_mp"},
    "resolvestroke-saddle": {"hf": f"{HF_ROOT}/resolvestroke/saddle"},
    "siemens-healthineers": {"hf": f"{HF_ROOT}/siemens-healthineers"},
    "stanford-murine": {"hf": f"{HF_ROOT}/stanford-murine"},
    "strasbourg-basel": {"hf": f"{HF_ROOT}/strasbourg-basel"},
    "technion-bladder": {"hf": f"{HF_ROOT}/technion/bladder"},
    "technion-cardiac": {"hf": f"{HF_ROOT}/technion/cardiac"},
    "technion-phantom": {"hf": f"{HF_ROOT}/technion/phantom"},
    "tel-aviv": {"hf": f"{HF_ROOT}/tel-aviv"},
    "tue-aaa": {"hf": f"{HF_ROOT}/tue-aaa"},
    "tue-cardiac": {"hf": f"{HF_ROOT}/tue-cardiac"},
    "tue-carotid": {"hf": f"{HF_ROOT}/tue-carotid"},
    "tumunich": {"hf": f"{HF_ROOT}/tumunich"},
    "twente-cavitation": {"hf": f"{HF_ROOT}/twente-cavitation"},
    "twente-microbubblesim": {"hf": f"{HF_ROOT}/twente-microbubblesim"},
    "twente-vortexflow": {"hf": f"{HF_ROOT}/twente-vortexflow"},
    "ubc-swave": {"hf": f"{HF_ROOT}/ubc/module_A"},
    "ubc-fetal": {"hf": f"{HF_ROOT}/ubc/module_C"},
    "ulmshare": {"hf": f"{HF_ROOT}/ulmshare"},
    "unc-liver": {"hf": f"{HF_ROOT}/unc-liver"},
    "unc-openpros": {"hf": f"{HF_ROOT}/unc-openpros"},
    "us4us": {"hf": f"{HF_ROOT}/us4us"},
    "vanderbilt": {"hf": f"{HF_ROOT}/vanderbilt"},
    "waterloo-carotid": {"hf": f"{HF_ROOT}/waterloo-carotid"},
    "waterloo-femoralvein": {"hf": f"{HF_ROOT}/waterloo-femoralvein"},
    "waterloo-muscle": {"hf": f"{HF_ROOT}/waterloo-muscle"},
    "weillcornell": {"hf": f"{HF_ROOT}/weillcornell"},
    "weizmann-sampl": {"hf": f"{HF_ROOT}/weizmann-sampl"},
    "wpi": {"hf": f"{HF_ROOT}/wpi"},
}
