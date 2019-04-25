import matplotlib.pyplot as plt
import numpy as np
import math

def parse_time(time_file):
    time_list = []
    with open(time_file, "r") as tf:
        line = tf.readlines()
        for l in line:
            time_list.append(float(l.split(",")[-1].strip()))
    return time_list

if __name__ == "__main__":
    tl = parse_time("exctime_2hop.csv")
    tl.sort()
    fig = plt.figure(0)
    plt.title("Time Until Failure")
    plt.plot(tl)
    plt.savefig( "ttf.png", bbox_inches="tight")



