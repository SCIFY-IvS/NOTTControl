# -*- coding: utf-8 -*-
"""
Created on Fri Mar 10 12:18:09 2023

@author: Kwinten
"""

from datetime import datetime
import numpy
from camera.utils.utils import BrightnessResults

class BrightnessCalculator():
    
    def __init__(self, rois):
        self.rois = rois
    
    def run(self):
        self.results = []

        for roi in self.rois:
            min = numpy.amin(roi)
            max = numpy.amax(roi)
            avg = numpy.average(roi)
            shape = numpy.shape(roi)
            sum = avg * shape[0] * shape[1]
            self.results.append(BrightnessResults(min, max, avg, sum))