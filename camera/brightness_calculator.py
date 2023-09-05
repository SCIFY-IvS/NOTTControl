# -*- coding: utf-8 -*-
"""
Created on Fri Mar 10 12:18:09 2023

@author: Kwinten
"""

from datetime import datetime
import numpy

class BrightnessCalculator():
    
    def __init__(self, img, roidata_ul, roidata_ll, roidata_lr, roidata_ur):
        self.roidata_ul = roidata_ul
        self.roidata_ll = roidata_ll
        self.roidata_lr = roidata_lr
        self.roidata_ur = roidata_ur
    
    def run(self):
        self.min_ul = numpy.amin(self.roidata_ul)
        self.max_ul = numpy.amax(self.roidata_ul)
        self.mean_ul = numpy.average(self.roidata_ul)
        
        self.min_ll = numpy.amin(self.roidata_ll)
        self.max_ll = numpy.amax(self.roidata_ll)
        self.mean_ll = numpy.average(self.roidata_ll)
        
        self.min_lr = numpy.amin(self.roidata_lr)
        self.max_lr = numpy.amax(self.roidata_lr)
        self.mean_lr = numpy.average(self.roidata_lr)
        
        self.min_ur = numpy.amin(self.roidata_ur)
        self.max_ur = numpy.amax(self.roidata_ur)
        self.mean_ur = numpy.average(self.roidata_ur)