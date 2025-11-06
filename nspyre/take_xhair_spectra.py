"""
Takes one spectrum for each crosshair in a list of crosshairs.
A. Wellisz 2025-10

Limitations:
	- Maximum integration time is limited by RPYC_SYNC_TIMEOUT which 
	  has to be manually changed in nspyre/instrument/server.py. (For 
	  some reason setting sync_timeout in the inserv constructor doesn't 
	  work). Current max is 300 s (5 min). 
	- You can't add xhairs mid-experiment (a local copy of existing xhairs
	  in the given dataset is created at the start of the experiment).
	- You can stop the experiment, but it will only stop after the
	  current acquisition is finished.
	- Uses hardcoded fsm1 to move between xhairs

See drivers/horiba/horiba_driver.py to see limitations of the driver.
"""

from nspyre import DataSink, DataSource, StreamingList, InstrumentGateway
from nspyre import experiment_widget_process_queue, nspyre_init_logger

import os
import logging
from pathlib import Path
import numpy as np
from rpyc.utils.classic import obtain

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

class SpectraPerXhairMeasurement:

	def __init__(self, queue_to_exp=None, queue_from_exp=None):
		self.queue_to_exp = queue_to_exp
		self.queue_from_exp = queue_from_exp

	def __enter__(self):
		nspyre_init_logger(
			log_level = logging.INFO,
			log_path = _HERE / '../../Logs',
			log_path_level = logging.DEBUG,
			prefix=Path(__file__).stem,
			file_size=10_000_000,
			)
		_logger.info('Created SpectraPerXhairMeasurement instance.')

	def take_spectra_per_xhair(self,
		xhairs: str,
		dataset: str,
		folder: str,
		filename: str,
		exposure_s: float,
		gain: str,
		adc: str,
		xstart: int, xend: int,
		ystart: int, yend: int,
		xbin: int, ybin: int,
		**kwargs):
		"""
		Takes 1 spectrum per xhair in a given xhair dataset.

		xhairs: crosshair dataset name
		dataset: dataset name to save spectra to
		folder: folder to save spectra to
		filename: filename for the spectra
		exposure_s: exposure time per spectrum in seconds
		gain: gain settings
		adc: adc setting
		x/y start/end: start and end values for CCD ROI
		x/y bin: binning (should be ybin=512 for spectra)
		kwargs: should include wavelength + grating info for filename
		"""

		local_xhairs = self.get_copy_of_xhairs(xhairs)
		num_xhairs = len(local_xhairs)

		print(f"DEBUG: {num_xhairs} found")

		w = kwargs.get('wavelength')
		g = kwargs.get('grating')

		# make the destination folder if it doesn't exist yet
		os.makedirs(folder, exist_ok=True)

		# connect to instrument server
		# connect to data server + create/connect to spectra data set
		with InstrumentGateway() as gw, DataSource(dataset) as spec_data:

			# A dictionary that will contain all spectrometer datasets within it.
			# Each key corresponds to a crosshair
			# Each value is a StreamingList of 2x2048 arrays (assuming using the whole chip)
			spec_xhair_datasets = {}

			# push a header immediately so the plot can connect (but no data yet)
			spec_data.push({
				'params': {'exposure_s': exposure_s, 'gain': gain, 'adc': adc, 'roi': (xstart, xend, ystart, yend), 'bin': (xbin, ybin)},
				'title': 'Spectrum per crosshair',
				'xlabel': 'Wavelength (nm)',
				'ylabel': 'Counts',
				'datasets': spec_xhair_datasets
			})

			# For each xhair, move to the xhair and take 1 spectrum
			for n in range(num_xhairs):

				# stop if GUI asks us to (NB: can only happen between acquisitions, not during one!)
				if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
					return
				
				# cross001, cross002, etc
				#xhair_label = f'cross{n+1:03d}'
				xhair_label = 'cross' + str(n+1).zfill(3)
				self.queue_from_exp.put_nowait(f"Running acquisition ({xhair_label})...")
				# coords is a 2-element list
				coords = local_xhairs[xhair_label]['cord']

				# Move FSM to the xhair
				# TODO: ADD DROPDOWN TO SELECT FSM?
				gw.fsm1.move((coords[0], coords[1]))

				# Prepare filename for saving
				filename_with_params = (filename
										.replace('%g', str(g))
										.replace('%t', str(exposure_s))
										.replace('%n', str(n+1))
										.replace('%w', str(w)))
				
				full_path = folder + '\\' + filename_with_params + '.txt'

				# Take one spectrum with the given settings
				gw.horiba.capture_spectrum(
					exposure_s=exposure_s,
					outfile=full_path,
					spectra=True,
					gain=gain,
					adc=adc,
					xstart=xstart, xend=xend,
					ystart=ystart, yend=yend,
					xbin=xbin, ybin=ybin,
				)

				# Data gets saved to a file, so we read it to also push to dataserv
				# For some reason the JY SDK always adds _0001_AREA1_1; rename first
				full_path_JY = full_path[:-len('.txt')] + '_0001_AREA1_1.txt'
				os.rename(full_path_JY, full_path)

				data_from_file = np.loadtxt(full_path, delimiter = '\t')
				wavelengths = data_from_file[:,0]
				counts = data_from_file[:,1]
				# Reshape to be what FlexLinePlot expects
				data_arr = np.vstack([wavelengths, counts])

				spec_xhair_dataset_name = f"spec_{xhair_label}"
				if spec_xhair_dataset_name not in spec_xhair_datasets:
					spec_xhair_datasets[spec_xhair_dataset_name] = StreamingList()
				spec_xhair_datasets[spec_xhair_dataset_name].append(data_arr)

				# Maintain a 'latest' series for plotting
				if 'latest' not in spec_xhair_datasets:
					spec_xhair_datasets['latest'] = StreamingList()
				spec_xhair_datasets['latest'].append(data_arr)

				spec_data.push({
					'params': {
						'exposure_s': exposure_s, 
						'gain': gain, 
						'adc': adc, 
						'roi': (xstart, xend, ystart, yend), 
						'bin': (xbin, ybin),
						'wavelength': w,
						'grating': g,
						},
					'title': 'Spectrum',
					'xlabel': 'Wavelength (nm)',
					'ylabel': 'Counts',
					'datasets': spec_xhair_datasets
				})

		self.queue_from_exp.put_nowait(f"Acqusition on {num_xhairs} xhairs complete.")
		return
	
	def get_copy_of_xhairs(self, xhairs: str):
		"""
		Returns a local copy of the xhairs dataset.
		"""

		with DataSink(xhairs) as sink:
			sink.pop()
			return sink.datasets