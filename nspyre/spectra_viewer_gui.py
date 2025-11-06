"""
Widget for viewing the spectra produced by SpectraPerXhairWidget
(currently hardcoded to find datasets (within the given sink)
 starting with "spec_")
"""

import logging
import time

import numpy as np
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from nspyre.data.sink import DataSink
from nspyre.gui.widgets.line_plot import LinePlotWidget

_logger = logging.getLogger(__name__)

class SpectraViewerWidget(QtWidgets.QWidget):
    """Qt widget for visualizing multiple spectra"""

    def __init__(self):
        super().__init__()

        self.sink = None
        self.sink_mutex = QtCore.QMutex()
        self.current_dataset = None
        self.spectra_data = {}
        self.visible_spectra = []

        # main layout
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        #plot widget
        self.plot_widget = LinePlotWidget(
            title='Spectrometer Data',
            xlabel='Wavelength (nm)',
            ylabel='Counts',
            legend=True
        )
        main_layout.addWidget(self.plot_widget, 4)  # Plot takes 4/5 of space

        # control panel
        control_panel = QtWidgets.QWidget()
        control_layout = QtWidgets.QVBoxLayout()
        control_panel.setLayout(control_layout)
        control_panel.setMaximumWidth(300)  # Limit width of control panel

        # Dataset selection
        dataset_layout = QtWidgets.QHBoxLayout()
        dataset_label = QtWidgets.QLabel('Dataset:')
        self.dataset_edit = QtWidgets.QLineEdit('spec_xhair0')
        self.connect_btn = QtWidgets.QPushButton('Connect')
        self.connect_btn.clicked.connect(self._connect_dataset)
        
        dataset_layout.addWidget(dataset_label)
        dataset_layout.addWidget(self.dataset_edit)
        dataset_layout.addWidget(self.connect_btn)
        control_layout.addLayout(dataset_layout)

        # Control buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.show_all_btn = QtWidgets.QPushButton('Show All')
        self.hide_all_btn = QtWidgets.QPushButton('Hide All')
        self.show_selected_btn = QtWidgets.QPushButton('Show Selected')
        self.hide_selected_btn = QtWidgets.QPushButton('Hide Selected')
        
        self.show_all_btn.clicked.connect(self._show_all)
        self.hide_all_btn.clicked.connect(self._hide_all)
        self.show_selected_btn.clicked.connect(self._show_selected)
        self.hide_selected_btn.clicked.connect(self._hide_selected)
        
        btn_layout.addWidget(self.show_all_btn)
        btn_layout.addWidget(self.hide_all_btn)
        control_layout.addLayout(btn_layout)
        
        btn_layout2 = QtWidgets.QHBoxLayout()
        btn_layout2.addWidget(self.show_selected_btn)
        btn_layout2.addWidget(self.hide_selected_btn)
        control_layout.addLayout(btn_layout2)

        # Spectra list
        spectra_label = QtWidgets.QLabel('Available Spectra:')
        control_layout.addWidget(spectra_label)
        
        self.spectra_list = QtWidgets.QListWidget()
        self.spectra_list.itemChanged.connect(self._spectrum_checkbox_changed)
        self.spectra_list.setSelectionMode(QtWidgets.QListWidget.SelectionMode.MultiSelection)
        control_layout.addWidget(self.spectra_list)

        # Status label
        self.status_label = QtWidgets.QLabel('Not connected')
        control_layout.addWidget(self.status_label)

        control_layout.addStretch()  # Push everything to the top

        # TODO: FIX SPACING! THIS DOESN'T WORK PROPERLY
        main_layout.addWidget(control_panel, 1)  # Controls take 1/5 of space
        self.setLayout(main_layout)

        # Start update timer
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_gui)
        self.update_timer.start(100)  # Update every 100ms

    def _connect_dataset(self):
        """Connect to the specified dataset."""
        dataset_name = self.dataset_edit.text().strip()
        if not dataset_name:
            return

        with QtCore.QMutexLocker(self.sink_mutex):
            # Clean up existing sink
            if self.sink is not None:
                try:
                    self.sink.stop()
                except Exception as e:
                    _logger.error(f"Error stopping previous sink: {e}")
                self.sink = None

            # Connect to new dataset
            try:
                self.sink = DataSink(dataset_name)
                self.sink.start()
                
                # Wait for connection
                start_time = time.time()
                while not self.sink.is_running and (time.time() - start_time) < 5.0:
                    time.sleep(0.1)
                
                if not self.sink.is_running:
                    _logger.warning(f"Timeout connecting to dataset {dataset_name}")
                    self.sink = None
                    self.current_dataset = None
                    self.status_label.setText('Connection timeout')
                    return
                    
                self.current_dataset = dataset_name
                self.status_label.setText(f'Connected to {dataset_name}')
                _logger.info(f"Connected to dataset: {dataset_name}")
                
            except Exception as e:
                _logger.error(f"Error connecting to dataset {dataset_name}: {e}")
                self.sink = None
                self.current_dataset = None
                self.status_label.setText(f'Connection failed: {e}')

    def _update_spectra_list(self, datasets: dict):
        """Update the list of available spectra."""
        # Find all spectrometer datasets (starting with "spec_")
        spec_datasets = [name for name in datasets.keys() if name.startswith('spec_')]
        spec_datasets.sort()

        current_items = {
            self.spectra_list.item(i).text() 
            for i in range(self.spectra_list.count())
        }

        # Add new items
        for spec_name in spec_datasets:
            if spec_name not in current_items:
                item = QtWidgets.QListWidgetItem(spec_name)
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                self.spectra_list.addItem(item)

        # Remove items that no longer exist
        for i in range(self.spectra_list.count() - 1, -1, -1):
            item = self.spectra_list.item(i)
            if item.text() not in spec_datasets:
                # Remove plot if it exists
                if item.text() in self.visible_spectra:
                    self.plot_widget.remove_plot(item.text())
                    self.visible_spectra.remove(item.text())
                self.spectra_list.takeItem(i)

    def _spectrum_checkbox_changed(self, item):
        """Handle checkbox state changes in the spectra list."""
        spectrum_name = item.text()
        is_checked = item.checkState() == QtCore.Qt.CheckState.Checked

        #print(f"DEBUG: _spectrum_checkbox_changed for {spectrum_name}")

        try:
            if is_checked and spectrum_name not in self.visible_spectra:
                # Show spectrum
                #print("DEBUG: Spec checked")
                if spectrum_name in self.spectra_data:
                    x_data = self.spectra_data[spectrum_name][0]
                    y_data = self.spectra_data[spectrum_name][1]
                    self.plot_widget.add_plot(spectrum_name)
                    self.plot_widget.set_data(spectrum_name, x_data, y_data, blocking = False)
                    self.visible_spectra.append(spectrum_name)

            elif not is_checked and spectrum_name in self.visible_spectra:
                # Hide spectrum
                #print("DEBUG: Spec UNchecked")

                self.plot_widget.remove_plot(spectrum_name)
                self.visible_spectra.remove(spectrum_name)
        except Exception as e:
                    _logger.debug(f"Error with checkbox: {e}")
        

    def _show_all(self):
        """Show all spectra."""
        self.spectra_list.blockSignals(True)
        for i in range(self.spectra_list.count()):
            item = self.spectra_list.item(i)
            item.setCheckState(QtCore.Qt.CheckState.Checked)
        self.spectra_list.blockSignals(False)
        
        # Update all plots
        for spectrum_name, data in self.spectra_data.items():
            if spectrum_name not in self.visible_spectra:
                self.plot_widget.add_plot(spectrum_name)
                self.plot_widget.set_data(spectrum_name, data[0], data[1], blocking = False)
                self.visible_spectra.append(spectrum_name)

    def _hide_all(self):
        """Hide all spectra."""
        self.spectra_list.blockSignals(True)
        for i in range(self.spectra_list.count()):
            item = self.spectra_list.item(i)
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.spectra_list.blockSignals(False)
        
        # Remove all plots
        for spectrum_name in self.visible_spectra[:]:
            self.plot_widget.remove_plot(spectrum_name)
            self.visible_spectra.remove(spectrum_name)

    def _show_selected(self):
        """Show only the selected spectra."""
        selected_items = self.spectra_list.selectedItems()
        if not selected_items:
            return

        self.spectra_list.blockSignals(True)
        # First uncheck all
        # TODO: MAYBE DONT DO THIS AND JUST SHOW SELECTED IN ADDITION
        for i in range(self.spectra_list.count()):
            item = self.spectra_list.item(i)
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        
        # Then check selected
        for item in selected_items:
            item.setCheckState(QtCore.Qt.CheckState.Checked)
            # Have to call this manually for some reason
            self._spectrum_checkbox_changed(item)
        self.spectra_list.blockSignals(False)

    def _hide_selected(self):
        """Hide the selected spectra."""
        selected_items = self.spectra_list.selectedItems()
        if not selected_items:
            return

        self.spectra_list.blockSignals(True)
        for item in selected_items:
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self._spectrum_checkbox_changed(item)
        self.spectra_list.blockSignals(False)

    def update_gui(self):
        """Update the spectra data and plots."""
        with QtCore.QMutexLocker(self.sink_mutex):
            if self.sink is None or not self.sink.is_running:
                return

            try:
                # Check for new data
                self.sink.pop(timeout=0.01)
                
                # Get datasets
                datasets = getattr(self.sink, 'datasets', {})
                if not datasets:
                    return

                # update titles/labels
                try:
                    title = getattr(self.sink, 'title', None)
                    xlabel = getattr(self.sink, 'xlabel', None)
                    ylabel = getattr(self.sink, 'ylabel', None)
                    
                    if title:
                        self.plot_widget.set_title(title)
                    if xlabel:
                        self.plot_widget.xaxis.setLabel(text=xlabel)
                    if ylabel:
                        self.plot_widget.yaxis.setLabel(text=ylabel)
                except Exception as e:
                    _logger.debug(f"Error updating plot labels: {e}")

                # Update spectra list
                self._update_spectra_list(datasets)

                # Update spectra data (datasets produced by SpectraPerXhairMeasurement
                #  all start with 'spec_' (e.g. spec_cross001))
                for spec_name in [name for name in datasets.keys() if name.startswith('spec_')]:
                    data_list = datasets[spec_name]
                    if data_list and len(data_list) > 0:
                        # Take the most recent data array
                        latest_data = data_list[-1]
                        if isinstance(latest_data, np.ndarray) and latest_data.shape[0] == 2:
                            self.spectra_data[spec_name] = latest_data
                            
                            # Update plot if this spectrum is visible
                            if spec_name in self.visible_spectra:
                                x_data = latest_data[0]
                                y_data = latest_data[1]
                                self.plot_widget.set_data(spec_name, x_data, y_data, blocking = False)

            except TimeoutError:
                pass  # No new data available
            except Exception as e:
                _logger.error(f"Error updating spectra: {e}")

    def teardown(self):
        """Clean up resources."""
        with QtCore.QMutexLocker(self.sink_mutex):
            if self.sink is not None:
                try:
                    self.sink.stop()
                except Exception as e:
                    _logger.error(f"Error stopping sink: {e}")
                self.sink = None
        
        if self.update_timer.isActive():
            self.update_timer.stop()