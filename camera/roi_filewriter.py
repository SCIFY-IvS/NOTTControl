# -*- coding: utf-8 -*-
"""
Created on Wed Mar 22 14:23:15 2023

@author: Kwinten
"""

from PyQt5.QtCore import QThread
import os
from datetime import datetime
from configparser import ConfigParser

class ROIFileWriter(QThread):
    def __init__(self, max_times, max_values_1, max_values_2, max_values_3, max_values_4):
        QThread.__init__(self)
        self.max_times = max_times
        self.max_values_1 = max_values_1
        self.max_values_2 = max_values_2
        self.max_values_3 = max_values_3
        self.max_values_4 = max_values_4
    
    def run(self):
        output = ''
        nbValues = len(self.max_times)
        
        for i in range(nbValues):
            time = self.max_times[i]
            max1 = self.max_values_1[i]
            max2 = self.max_values_2[i]
            max3 = self.max_values_3[i]
            max4 = self.max_values_4[i]
            line = f'{str(time)}, {str(max1)}, {str(max2)}, {str(max3)}, {str(max4)}\n'
            output = output + line
            
        
        now = datetime.utcnow()
        
        config = ConfigParser()
        config.read('config.ini')
        
        filepath = config['DEFAULT']['logfilepath']
        print(filepath)
        
        file_name = filepath + 'CameraROI_' + now.strftime(r'%Y-%m-%d') + '.csv'
        
        if not os.path.isfile(file_name):
            headers = 'Time, ROI1_Max, ROI2_Max, ROI3_Max, ROI4_Max\n'
        else:
            headers = ''
        
        f = open(file_name, 'a')
        f.write(headers + output)
