
def correction(pos, centre_roue, centre_rot):
    centre_roue = np.array(centre_roue)
    pb = np.array(pos - centre_roue)
    vec = np.array(centre_roue-centre_rot)
    theta = np.arctan(pb[1]/pb[0])
    rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    centre_roue = centre_rot +rot.dot(vec)
    pb = np.array(pos - centre_roue)
    return pb

