#
# Python Script to perform for running the full process using load leveler
#
# Murray Cadzow 
# July 2013
# University Of Otago
#
# James Boocock
# July 2013
# University Of Otago
# 

import os
import sys
import re

#For matching the file names
import fnmatch

from run_pipeline import CommandTemplate

from optparse import OptionParser

## Subprocess import clause required for running commands on the shell##
import subprocess
import logging
#For giving steps unique names
from datetime import datetime
#Import standard run 

logging.basicConfig(format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)

SUBPROCESS_FAILED_EXIT=10
load_leveler_template="""
        #@ shell = /bin/bash
        #@ group = {0}
        #@ class = {1}
        #@ output = $(jobid).out
        #@ error = $(jobid).err 
"""
load_leveler_step="""
        #@ step_name = {0}
        #@ wall_clock_limit = {1}
        #@ resources = ConsumableMemory({2}gb) ConsumableVirtualMemory({2}gb)
"""

load_leveler_account_no="""
        #@ account_no = {0}
"""

# serial_task_with_threads
load_leveler_serial ="""
        #@ job_type = serial
        #@ parallel_threads = {0}
"""
# mpi_task
load_leveler_mpi = """
        #@ job_type = parallel
        #@ total_tasks_threads = {0}
        #@ blocking = {1}
"""
load_leveler_dependency = """
        #@ dependency = ({0})
""" 
# Queue jobs on load leveler
load_leveler_queue ="""
        #@ queue
    """

# ulimit load leveler ulimit
load_leveler_ulimit ="""
            ulimit -v {0} -m {0}
    """



class LoadLevelerRun(object):
    
    """ Load leveler class takes the pipeline and runs the PHD on the nesi pan 
        cluster.
    """
    def __init__(self,options,config):
        logger.debug('Running the script on nesi')
        self.group=config['nesi']['group'] 
        self.nesi_class=config['nesi']['class']
        self.account_no=config['nesi']['account_no']
        self.load_leveler_script = open('level_the_load.ll','wb')
        #The template for every script
        self.script_template=load_leveler_template.format(self.group,self.nesi_class)
        if(self.account_no is not None):
             self.script_template = self.script_template + (load_leveler_account_no.format(self.account_no))
        self.create_load_leveler_script(options,config)
        self.load_leveler_script.close()
    def create_load_leveler_script(self,options,config):
        if(options.phased_vcf): 
            (dependecies,haps) = self.ancestral_annotation_vcf(options,config)
            (dependencies,haps) = self.run_multi_coreihh(options,config,haps,dependencies)
        else:
            (dependencies,ped,map) = self.run_vcf_to_plink(options,config)
            (dependencies,ped,map) = self.run_plink_filter(options,config,ped,map,dependencies)
            (dependencies,haps) = self.run_shape_it(options,config,ped,map,dependencies) 
        if(options.imputation):
            (dependencies,haps)= self.run_impute2(options,config,haps,dependencies)
        (dependencies,haps) = self.indel_filter(options,config,haps,dependencies)
        #tajimas = run_tajimas_d(options,config,haps)
        (dependencies,haps) = self.run_aa_annotate_haps(options,config,haps,dependencies)
        (dependencies,ihh) = self.run_multi_coreihh(options,config,haps,dependencies)
        logger.info("Pipeline completed successfully")
        logger.info(haps)
        logger.info(ihh)
        logger.info("Goodbye :)")

     
    def run_vcf_to_plink(self,options,config):
        logger.debug("Preparing vcf_to_plink for running on pan")
        (cmd,prefix) = CommandTemplate.run_vcf_to_plink(self,options,config)
        print(self.script_template)
        self.load_leveler_script.write(bytes(self.script_template,'UTF-8'))
        self.load_leveler_script.write(bytes(load_leveler_serial.format(1),'UTF-8'))
        # Set up wall time and memory required
        memory_required="4"
        ulimit=str(int(memory_required) * 1024 * 1024)
        step_name=prefix+self.get_date_string()
        self.load_leveler_script.write(bytes(load_leveler_step.format(step_name,"11:59:00",memory_required),'UTF-8'))
        self.load_leveler_script.write(bytes(load_leveler_queue,'UTF-8'))
        self.load_leveler_script.write(bytes(load_leveler_ulimit.format(ulimit),'UTF-8'))
        self.load_leveler_script.write(bytes(' '.join(cmd),'UTF-8'))
        self.load_leveler_script.write(self.string_to_bytes('\n'))
        logger.debug("Finished preparing vcf_to_plink for running on pan")
        return(step_name + '>= 0',prefix + '.ped', prefix+'.map',) 
        
          
    def run_plink_filter(self,options, config,ped,map,dependencies):
        logger.debug("Preparing plink filtering for running on pan")
        (cmd,prefix) = CommandTemplate.run_plink_filter(self,options,config,ped,map)
        self.load_leveler_script.write(self.string_to_bytes(self.script_template))
        self.load_leveler_script.write(self.string_to_bytes(load_leveler_serial.format(1)))
        memory_required="4"
        ulimit=str(int(memory_required) * 1024 * 1024)
        step_name=prefix + self.get_date_string()
        self.load_leveler_script.write(self.string_to_bytes(load_leveler_step.format(step_name,"11:59:00",memory_required)))
        self.load_leveler_script.write(self.string_to_bytes(load_leveler_dependency.format(dependencies)))
        self.load_leveler_script.write(self.string_to_bytes(load_leveler_queue))
        self.load_leveler_script.write(self.string_to_bytes(load_leveler_ulimit.format(ulimit)))
        self.load_leveler_script.write(self.string_to_bytes(' '.join(cmd)))
        self.load_leveler_script.write(self.string_to_bytes('\n'))
        logger.debug("Finished preparing plink filtering for running on pan")
    
    # Utility functions used for setting up the job step names
    def string_to_bytes(self,input):
        return bytes(input,'UTF-8')

    def get_date_string(self):
        return str(datetime.now()).replace(' ','').replace(':','').replace('.','').replace('-','')
