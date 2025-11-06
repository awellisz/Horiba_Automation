# take single spectrum experiment

from nspyre import InstrumentGateway
from nspyre import DataSink, DataSource, StreamingList, experiment_widget_process_queue, nspyre_init_logger

import logging
from pathlib import Path
import numpy as np
from rpyc.utils.classic import obtain
import os 

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

class SingleSpectraMeasurement:

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
		_logger.info('Created SingleSpectraMeasurement instance.')

	# TODO: ALLOW USER TO STOP ACQUISITION?
	def take_one_spectrum(self,
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
		Takes 1 spectrum. Saves it to a file and to a dataset
		"""

		self.queue_from_exp.put_nowait("Running acquisition...")


		# Construct the filename (including wildcards)

		w = kwargs.get('wavelength')
		g = kwargs.get('grating')
		n = 1 # TODO: IMPLEMENT FILE NUMBERING

		filename_params = filename.replace('%g', str(g)).replace('%t', str(exposure_s)).replace('%n', str(n)).replace('%w', str(w))
		full_path = folder + '\\' + filename_params + '.txt'

		try:
			with InstrumentGateway() as gw, DataSource(dataset) as ds:

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

				# Data gets saved to a file, so read it to also push to dataserv
				# For some reason the JY SDK always adds _0001_AREA1_1, rename first
				full_path_JY = full_path[:-len('.txt')] + '_0001_AREA1_1.txt'
				os.rename(full_path_JY, full_path)

				data_arr = np.loadtxt(full_path, delimiter = '\t')
				wavelengths = data_arr[:,0]
				counts = data_arr[:,1]

				
				spectrum_data = StreamingList()
				spectrum_data.append(np.stack([wavelengths, counts]))
				spectrum_plot_data = {
					'params': {'exposure_s': exposure_s, 'gain': gain, 'adc': adc, 'xstart': xstart, 'xend': xend, 'ystart': ystart, 'yend': yend},
					'title': 'Spectrum',
					'xlabel': 'Wavelength (nm)',
					'ylabel': 'Counts',
					'datasets': {
						'spectra': spectrum_data,
					},
				}

				ds.push(spectrum_plot_data)


			self.queue_from_exp.put_nowait("Acquisition complete.")
		except Exception as e:
			self.queue_from_exp.put_nowait(f"Error during acquisition: {e}")
		
		return