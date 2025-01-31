import numpy as np

def correction(pos, centre, ordre):
    c = np.array(centre)
    pb = np.array(pos - c)
    thet = np.arctan2(pb[0]/pb[1])
    for i in range(ordre):
        rot = np.array([[np.cos(thet), -np.sin(thet)], [np.sin(thet), np.cos(thet)]])
        c = rot.dot(c)
        pb = pos - c
        thet = np.arctan2(pb[0]/pb[1])
    return pb,
