"""
GUI element for running SpectraPerXhairMeasurement.

Very similar to SpectrometerWidget but also takes in crosshairs.

TODO: FINISH THIS! FOR NOW IT'S JUST SPECTROM

A. Wellisz 2025-10
"""

from nspyre import InstrumentGateway, ExperimentWidget, experiment_widget_process_queue
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets, QtCore
import logging
from nspyre import FlexLinePlotWidget

import experiments.Spectra.take_xhair_spectra

_logger = logging.getLogger(__name__)


class SpectraPerXhairWidget(ExperimentWidget):
	def __init__(self):

		# Makes a more custom widget to set/get the wavelength/grating
		top_wl_gr_widget = self.create_wl_gr_widget()
		self.status_lbl = QtWidgets.QLabel("Status: --")
		self.status_lbl.setWordWrap(True)
		top_wl_gr_widget.addWidget(self.status_lbl)

		self.num_spectra = 0

		# QComboBoxes for later
		gain_combo = QtWidgets.QComboBox()
		gain_combo.addItems(["High Light", "Best Dynamic", "High Sens.", "Ultimate Sens."])
		gain_combo.setCurrentText("Ultimate Sens.") 

		adc_combo = QtWidgets.QComboBox()
		# NB: the leading space in " 50 kHz HS" is intentional
		adc_combo.addItems([" 50 kHz HS", "1.00 MHz HS", "3.00 MHz HS"])
		adc_combo.setCurrentText(" 50 kHz HS")

		# To store values
		self.wl = 0 
		self.wl_start = 0 
		self.wl_end = 0
		self.grating = 0

		params_config = {
			"xhairs": {
				"display_text": "Xhair source",
				"widget": QtWidgets.QLineEdit("xhair0"),
			},
			"dataset": {
				"display_text": "Save dataset",
				"widget": QtWidgets.QLineEdit("spec_xhair0"),
			},
			"folder": {
				"display_text": "Save Folder",
				"widget": QtWidgets.QLineEdit("C:\\Data\scratch"),
			},
			"filename": {
				"display_text": "Filename",
				"widget": QtWidgets.QLineEdit("%gg_%ts_%wnm_cross%n")
			},
			# capture settings
			"exposure_s": {
				"display_text": "Exp. Time",
				# Max time must be less than RPYC_SYNC_TIMEOUT 
				# Set RPYC_SYNC_TIMEOUT higher if necessary in nspyre.instrument.server
				"widget": SpinBox(value=1.0, suffix="s", siPrefix=True, bounds=(0.0, 300), dec=True),
			},
			"gain": {
				"display_text": "Gain",
				"widget": gain_combo,
			},
			"adc": {
				"display_text": "ADC",
				"widget": adc_combo,
			},
			# ROI (SynapsePlus sensor: x=1–2048, y=1–512)
			"xstart": {
				"display_text": "X start (px)",
				"widget": SpinBox(value=1, int=True, bounds=(1, 2048), dec=True),
			},
			"xend": {
				"display_text": "X end (px)",
				"widget": SpinBox(value=2048, int=True, bounds=(1, 2048), dec=True),
			},
			"ystart": {
				"display_text": "Y start (px)",
				"widget": SpinBox(value=116, int=True, bounds=(1, 512), dec=True),
			},
			"yend": {
				"display_text": "Y end (px)",
				"widget": SpinBox(value=136, int=True, bounds=(1, 512), dec=True),
			},
			# hardware binning
			"xbin": {
				"display_text": "X bin",
				"widget": SpinBox(value=1, int=True, bounds=(1, 2048), dec=True),
			},
			"ybin": {
				"display_text": "Y bin",
				"widget": SpinBox(value=512, int=True, bounds=(1, 512), dec=True),
			},
		}

		self.fun_kwargs = {
			'wavelength': 0,
			'grating': 0,
		}

		self.refresh_info()

		super().__init__(
			params_config = params_config,
			module = experiments.Spectra.take_xhair_spectra,
			cls = 'SpectraPerXhairMeasurement',
			fun_name = 'take_spectra_per_xhair',
			title="Spectra per Crosshair",
			layout=top_wl_gr_widget, # additional buttons and stuff
			fun_kwargs=self.fun_kwargs,
		)

		# Timer to poll for messages from the subprocess
		self._timer = QtCore.QTimer(self)
		self._timer.timeout.connect(self.check_status_queue)
		self._timer.start(50) # check every 50 ms


	def create_wl_gr_widget(self):

		#widget_master = QtWidgets.QWidget()
		#layout = QtWidgets.QVBoxLayout(widget_master)
		layout = QtWidgets.QVBoxLayout()

		# wavelength info/set
		wl_layout = QtWidgets.QHBoxLayout()
		wl_layout.addWidget(QtWidgets.QLabel("λ (nm):"))
		self.wl_value_lbl = QtWidgets.QLabel("--")  # current wavelength text
		#wl_layout.addWidget(self.wl_value_lbl)

		self.wl_set_spin = SpinBox(value=600.0, bounds=(0, 2000), dec=True) 
		self.wl_set_spin.setFixedWidth(120)
		wl_layout.addWidget(self.wl_set_spin)

		self.wl_set_btn = QtWidgets.QPushButton("Set Wavelength")
		self.wl_set_btn.clicked.connect(self.on_set_wavelength)
		wl_layout.addWidget(self.wl_set_btn)

		wl_layout.addStretch(1)

		# grating info/set
		gr_layout = QtWidgets.QHBoxLayout()
		gr_layout.addWidget(QtWidgets.QLabel("Grating:"))
		self.gr_value_lbl = QtWidgets.QLabel("--")  # current grating text
		gr_layout.addWidget(self.gr_value_lbl)

		self.gr_combo = QtWidgets.QComboBox()
		gr_layout.addWidget(self.gr_combo)

		self.gr_set_btn = QtWidgets.QPushButton("Set Grating")
		self.gr_set_btn.clicked.connect(self.on_set_grating)
		gr_layout.addWidget(self.gr_set_btn)
		gr_layout.addStretch(1)

		layout.addLayout(wl_layout)
		layout.addWidget(self.wl_value_lbl)
		layout.addLayout(gr_layout)

		return layout


	def refresh_info(self):
		try:

			with InstrumentGateway() as gw:
				horiba = gw.horiba
				info = horiba.get_spec_info()

				# print(info)

				wl = info.get("wavelength")
				wl_start = info.get("wl_start")
				wl_end = info.get("wl_end")
				wl_true_center = (wl_start + wl_end)/2

				if wl is not None:
					self.wl_value_lbl.setText(f"Center: {wl_true_center:.3f} | Range: {wl_start:.2f}-{wl_end:.2f}")
					#self.wl_set_spin.setValue(float(wl))

				cg = info.get("current_grating")
				self.grating = cg
				if cg is not None:
					self.gr_value_lbl.setText(str(int(cg)))

				# populate grating options
				self.gr_combo.clear()
				grs = info.get("gratings", [])
				for g in grs:
					self.gr_combo.addItem(str(int(g)))
				# select current grating in dropdown
				if cg is not None:
					idx = self.gr_combo.findText(str(int(cg)))
					if idx >= 0:
						self.gr_combo.setCurrentIndex(idx)

				# These kwargs are passed into the experiment just for naming purposes,
				# so nominal wavelength is fine? (off by up to ~0.2 nm)
				self.fun_kwargs = {
					'wavelength': self.wl_set_spin.value(),
					'grating': int(cg),
				}

				self.status_lbl.setText("Status: Spectrometer info loaded.")
		except Exception as e:
			self.status_lbl.setText(f"Status: Failed to get info: {e}")

	def on_set_wavelength(self):
		try:
			wl = float(self.wl_set_spin.value())

			with InstrumentGateway() as gw:
				gw.horiba.set_spec_wavelength(wl)

			self.status_lbl.setText(f"Status: Wavelength set to {wl:.3f} nm.")
			self.refresh_info()
		except Exception as e:
			self.status_lbl.setText(f"Error setting wavelength: {e}")

	# TODO: MAKE THIS THREADED, OR MAYBE MAKE IT AN EXPERIMENT EXPLICITLY?
	# FOR NOW THIS FREEZES NSPYRE
	def on_set_grating(self):
		try:
			gr = self.gr_combo.currentText()

			with InstrumentGateway() as gw:
				gw.horiba.set_spec_grating(gr)
				
			self.status_lbl.setText(f"Status: Grating set to {gr} g/mm.")
			self.refresh_info()
		except Exception as e:
			self.status_lbl.setText(f"Error setting grating: {e}")

	def check_status_queue(self):
		# Checks the queue from the experiment, built into ExperimentWidget
		msg = experiment_widget_process_queue(self.queue_from_exp)
		if not msg:
			return
		self.status_lbl.setText(f"Status: {msg}")

class FlexLinePlotWidgetForXhairSpectra(FlexLinePlotWidget):

	def __init__(self):
		super.__init__(data_processing_func= None)

		# show latest spectrum by default
		self.add_plot('latest', series='latest', scan_i='-1', scan_j = '', processing='Average')

		# show first xhair by default
		self.add_plot('cross001', series = 'spec_cross0001', scan_i='', scan_j='', processing='Average')

		# TODO: FIGURE OUT HOW TO HAVE ALL OF THE AVAILABLE SPECTRA SHOW UP HERE?

		legend=self.line_plot.plot_widget.addLegend()
		legend.setOffset((-10, -50))

		self.datasource_lineedit.setText('spec_xhair0')

