# TeresIA
TeresIA is a research project on Spanish terminology and artificial intelligence, aiming to develop a metasearch engine for terms as well as technologies for the extraction and processing of neologisms.

The metasearch engine will serve as a single access point to existing specialized Spanish terminologies. Its goal is to address the dispersion of terminological resources and the need for validated and high-quality Spanish terminologies.

## CONTENT
* gold_standard1: annotations of the different pre-annotation layers on the Workers' Statute. Version 01. These annotations include:
    - Diccionario Panhispánico del Español Jurídico (DPEJ)
    - Hohfeld
    - mREBEL
    - LabourLaw
    - ...

The folder contains subfolders: "articles", which includes each of the articles from the Workers' Statute; "terms", which contains the extracted terms; and "rels", which contains the Hohfeld relations between the extracted terms. These three folders are sourced from the repository "https://github.com/pmchozas/estatuto_goldstandard.git".

Also, termcat over tributario1 can be added, but it is not. 

* gold_standard2: it is the same as gold_standard1, but this time with Version 02. This includes tributario. 

* server1: contains everything related to the pre-annotation layers and server tests, aimed at visualizing the results in BRAT. Version 01 and parse from gold_standard1.

* server1: Version 02 and parse from gold_standard2.

