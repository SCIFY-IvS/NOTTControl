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
        self.avg_ul = numpy.average(self.roidata_ul)
        shape = numpy.shape(self.roidata_ul)
        self.sum_ul = self.avg_ul * shape[0] * shape[1]
        
        self.min_ll = numpy.amin(self.roidata_ll)
        self.max_ll = numpy.amax(self.roidata_ll)
        self.avg_ll = numpy.average(self.roidata_ll)
        shape = numpy.shape(self.roidata_ll)
        self.sum_ll = self.avg_ll * shape[0] * shape[1]
        
        self.min_lr = numpy.amin(self.roidata_lr)
        self.max_lr = numpy.amax(self.roidata_lr)
        self.avg_lr = numpy.average(self.roidata_lr)
        shape = numpy.shape(self.roidata_lr)
        self.sum_lr = self.avg_lr * shape[0] * shape[1]
        
        self.min_ur = numpy.amin(self.roidata_ur)
        self.max_ur = numpy.amax(self.roidata_ur)
        self.avg_ur = numpy.average(self.roidata_ur)
        shape = numpy.shape(self.roidata_ur)
        self.sum_ur = self.avg_ur * shape[0] * shape[1]