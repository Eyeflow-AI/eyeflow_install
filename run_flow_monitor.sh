#!/bin/bash

export LD_LIBRARY_PATH=/opt/eyeflow/lib:/usr/local/cuda/lib64:$LD_LIBRARY_PATH
export CUDA_MODULE_LOADING=LAZY

sudo python3 prepare_models.py
sudo ./eyeflow_edge --monitor
