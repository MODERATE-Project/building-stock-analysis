#!/usr/bin/env python
# coding: utf-8


#----    settings    ----

import pandas as pd
import numpy as np
from pathlib import Path
import os
import re
import unidecode
import datetime

#----    in_python    ----

def in_ipython() -> bool: 
    """
    Check if in interactive session or not 
    https://stackoverflow.com/a/1212907/12481476
    """
    try:
        return __IPYTHON__
    except NameError:
        return False
    

#----    to_plain_str    ----

def to_plain_str(x:str) -> str:
    """
    Get a plain string by:
    - remove all accented by transliterates any unicode string into the closest 
      possible representation in ascii text.
    - remove all non non alphanumeric characters (including spaces)
    - all character to lower case
        
    Parameters
    ----------
    x: str
        A string
       
    Returns
    -------
    str
        A string
    """
    x = str(x)
    x = unidecode.unidecode(x)
    x = re.sub('[^0-9a-zA-Z]+', '', str(x))\
        .lower()

    return x

#----    now_str    ----

def now_str(format:str = "%Y-%m-%d_h%H_m%M_s%S") -> str:
    """
    Return the current datetime nicely formatted in a string, e.g., 
    '2022-10-19_h10_m07_s17'
    """
    now = datetime.datetime.now()
    now = now.strftime(format)

    return now

#---    kelvin2celsius    ----

def kelvin2celsius(x:pd.Series) -> float:
    res = x - 273.15

    return res 

#---    macro_f1_score    ----
#---