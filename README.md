# Horiba Automation

This repo is a collection of some of the code used to automate data collection with a Horiba iHR-550 spectrometer. 

The meat of this is found in


## nspyre integration

All of the code in the nspyre folder is written to work with our [nspyre](https://nspyre.readthedocs.io/en/latest/) setup. The code is very ad hoc and will almost certainly not work out of the box.

Using this code with nspyre of course requires adding the driver to the instrument server:
`inserv.add('horiba', HERE / 'drivers' / 'horiba' / 'horiba_driver.py', 'Horiba')`
and adding the widgets to the MainWidget.