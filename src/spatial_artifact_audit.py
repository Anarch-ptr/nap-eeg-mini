"""Pre-registered spatial masking and noise interventions for Phase 2B."""

from __future__ import annotations
import numpy as np

CHANNEL_NAMES = ("Fz","FC3","FC1","FCz","FC2","FC4","C5","C3","C1","Cz","C2","C4","C6","CP3","CP1","CPz","CP2","CP4","P1","Pz","P2","POz")
GROUP_SEED = 20260718
CHANNEL_GROUPS = {
    "frontal": (0,1,2,3,4,5),
    "matched_nonfrontal": (13,14,15,16,17,19),
    "random_01": (1,10,11,13,14,18),
    "random_02": (2,6,9,13,17,21),
    "random_03": (5,6,10,11,15,16),
    "random_04": (0,3,7,8,11,20),
    "random_05": (0,4,12,13,18,20),
}
WINDOWS = {"full":(0.0,4.0),"early":(0.0,1.0),"middle":(1.5,2.5),"late":(3.0,4.0)}
SIGMAS = (0.25,0.5,1.0)

def validate_channel_names(names):
    if tuple(names) != CHANNEL_NAMES: raise RuntimeError("Dataset channel names/order differ from frozen Phase 2B registration.")

def group_names(group): return tuple(CHANNEL_NAMES[i] for i in CHANNEL_GROUPS[group])

def window_slice(window,sfreq,n_samples):
    lo,hi=WINDOWS[window]; result=slice(round(lo*sfreq),round(hi*sfreq)+1)
    if result.stop>n_samples: raise ValueError("Window exceeds epoch.")
    return result

def mask_channels(x,indices,window="full",sfreq=250.0):
    result=x.copy(); selected=window_slice(window,sfreq,x.shape[2]); result[:,indices,selected]=0; return result

def base_group_noise(shape,sigma,seed):
    return np.random.default_rng(seed).normal(0,sigma,size=(shape[0],6,shape[2])).astype(np.float32)

def inject_group_noise(x,indices,noise):
    if len(indices)!=noise.shape[1]: raise ValueError("Noise/group channel count mismatch.")
    result=x.copy(); result[:,indices,:]+=noise; return result

def inject_global_noise(x,sigma,seed):
    noise=np.random.default_rng(seed).normal(0,sigma,size=x.shape).astype(np.float32); return x+noise,noise

def perturbation_stats(clean,intervened):
    p=intervened-clean; rms=float(np.sqrt(np.mean(p*p))); eeg=float(np.sqrt(np.mean(clean*clean)))
    return rms,rms/eeg

def paired_delta(clean,intervened): return intervened-clean
def frontal_matched_contrast(frontal_delta,matched_delta): return frontal_delta-matched_delta

def random_summary(frontal_delta,random_deltas):
    values=np.asarray(random_deltas,float)
    return {"random_mean":float(values.mean()),"random_min":float(values.min()),"random_max":float(values.max()),"frontal_minus_random_mean":float(frontal_delta-values.mean()),"frontal_rank_most_negative_first":int(1+np.sum(values<frontal_delta))}
