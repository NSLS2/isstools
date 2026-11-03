# Standard library
import os
from datetime import datetime
from pathlib import Path

# Third-party libraries
import pkg_resources
import requests
from redis_json_dict import RedisJSONDict

# PyQt5 modules
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtWidgets import QListWidgetItem, QAbstractItemView, QMenu, QApplication
from PyQt5.QtGui import QColor
from PyQt5.Qt import Qt

# External packages (scientific/data handling)
from isstools.tiled_access import search_proposal_runs


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_processing.ui')
ROOT_PATH = '/nsls2/data/iss/legacy'
USER_PATH = 'processed'

class ProposalWorker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, year, cycle):
        super().__init__()
        self.year = year
        self.cycle = cycle

    def run(self):
        try:
            folder_path = Path(f'/nsls2/data/iss/legacy/processed/{self.year}/{self.cycle}')
            if not folder_path.exists():
                self.finished.emit([])
                return

            folders = [f for f in folder_path.iterdir() if f.is_dir() and f.name.isdigit()]
            folders_sorted = sorted(folders, key=lambda x: int(x.name))
            proposals = []

            for folder in folders_sorted:
                pi = 'Staff'
                headers = {'accept': 'application/json'}
                try:
                    response = requests.get(
                        f'https://api.nsls2.bnl.gov/v1/proposal/{folder.name}',
                        headers=headers,
                        timeout=2
                    )
                    proposal_info = response.json()
                    if 'proposal' in proposal_info:
                        for user in proposal_info['proposal'].get('users', []):
                            if user.get('is_pi'):
                                pi = f"{user.get('first_name', '')} {user.get('last_name', '')}"
                                break
                except Exception:
                    pi = 'Error'

                proposals.append(f'{folder.name} - {pi}')

            self.finished.emit(proposals)

        except Exception as e:
            self.error.emit(str(e))


class UIProcessing(*uic.loadUiType(ui_path)):
    def __init__(self,
                 hhm,
                 tiled_client,
                 parent_gui,
                 redis_settings_client=None,
                 *args, **kwargs):
        '''
            hhm:
                the monochromator
            tiled_client: the ISS raw runs catalog
            det_dict:
                detector dictionary
            parent_gui:
                the parent gui

        '''
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent_gui = parent_gui
        self.hhm = hhm
        self.tiled_catalog = tiled_client
        self.redis_settings_client = redis_settings_client

        self.settings = parent_gui.settings

        self.push_populate_uids.clicked.connect(self.populate_uids)
        self.push_process_uids.clicked.connect(self.process_uids)
        self.intialize_combo_boxes()

        self.comboBox_cycle.currentIndexChanged.connect(self.refresh_combo_boxes)
        self.comboBox_year.currentIndexChanged.connect(self.refresh_combo_boxes)
        self.listWidget_acquired_uids.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.listWidget_acquired_uids.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listWidget_acquired_uids.customContextMenuRequested.connect(self.copy_selected_uids_to_clipboard)

        # Initialize 'processing' tab

        self.edge_found = -1
        # Disable buttons

        self.binned_datasets = []
        self.interpolated_datasets = []
        self.comments = []
        self.labels = []

        self.cycle_def = {'1': ['01','01','04','30'],
                          '2':['05','01','08','31'],
                          '3':['09','01','12','31'],}

        self.current_catalog = None

    def copy_selected_uids_to_clipboard(self, QPos):
        items = self.listWidget_acquired_uids.selectedItems()
        menu = QMenu(self)
        copy_action = menu.addAction('&Copy to clipboard')
        parentPosition = self.listWidget_acquired_uids.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition + QPos)
        action = menu.exec_()
        # action = menu.exec_(self.listWidget_acquired_uids.mapToGlobal(copy_action))

        if action == copy_action:
            lis = [item.text().split(' - ')[0] for item in items]
            QApplication.clipboard().setText(str(lis))



    def intialize_combo_boxes(self):
        # Block signals while updating
        self.comboBox_year.blockSignals(True)
        self.comboBox_cycle.blockSignals(True)
        self.comboBox_proposal.blockSignals(True)

        now = datetime.now()
        year = str(now.year)
        cycle = str((now.month - 1) // 4 + 1)

        self.populate_years(year)
        self.populate_cycles(cycle)
        self.refresh_combo_boxes()

        # Unblock signals
        self.comboBox_year.blockSignals(False)
        self.comboBox_cycle.blockSignals(False)
        self.comboBox_proposal.blockSignals(False)

    def refresh_combo_boxes(self):
        print('refreshing')

        year = self.comboBox_year.currentText()
        cycle = self.comboBox_cycle.currentText()

        self.comboBox_proposal.clear()
        self.comboBox_proposal.addItem("Loading...")

        self.thread = QThread()
        self.worker = ProposalWorker(year, cycle)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_proposals_loaded)
        self.worker.error.connect(self.on_proposals_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_proposals_loaded(self, proposals):
        self.comboBox_proposal.blockSignals(True)
        self.comboBox_proposal.clear()
        self.comboBox_proposal.addItems(proposals)
        if proposals:
            self.comboBox_proposal.setCurrentIndex(0)
        self.comboBox_proposal.blockSignals(False)

    def on_proposals_error(self, message):
        self.comboBox_proposal.clear()
        self.comboBox_proposal.addItem(f"Error: {message}")

    def populate_years(self, default_year):
        self.comboBox_year.clear()
        for _year in range(2016, 2035):
            self.comboBox_year.addItem(str(_year))
        self.comboBox_year.setCurrentText(default_year)

    def populate_cycles(self, default_cycle):
        self.comboBox_cycle.clear()
        for _cycle in range(1, 4):
            self.comboBox_cycle.addItem(str(_cycle))
        self.comboBox_cycle.setCurrentText(default_cycle)


    def populate_uids(self):
        if self.tiled_catalog is None:
            print('No Tiled catalog configured')
            return

        self.processed_uid_list = []
        self.not_processed_uid_list = []
        _uid_list = []

        self.listWidget_processed_uids.clear()
        self.listWidget_acquired_uids.clear()

        #get processed uids
        ROOT_PATH = '/nsls2/data/iss/legacy'
        USER_PATH = 'processed'
        self.proposal = str(self.comboBox_proposal.currentText()).split(' -')[0]
        self.year = str(self.comboBox_year.currentText())
        self.cycle = str(self.comboBox_cycle.currentText())

        redis_key = f'processing_log_{self.year}_{self.cycle}_{self.proposal}'
        _log_store = RedisJSONDict(self.redis_settings_client, prefix=redis_key)

        try:
            log_data = _log_store['log']
        except KeyError:
            log_data = []

        for entry in log_data:
            uid = entry.get('uid')
            timestamp = entry.get('timestamp', 'Unknown time')
            item_text = f"{uid}"
            self.listWidget_processed_uids.addItem(QListWidgetItem(item_text))
            self.processed_uid_list.append(uid)
        print(f"Loaded {len(log_data)} entries into list")


        self.current_catalog = search_proposal_runs(self.tiled_catalog, self.year, self.cycle, self.proposal)
        self.acquired_uid_list = list(self.current_catalog)

        self.not_processed_uid_list = []
        for uid in self.acquired_uid_list:
            hdr = self.current_catalog[uid].metadata['start']
            if 'experiment' in hdr and 'interp_filename' in hdr:
                name = os.path.splitext(os.path.basename(hdr['interp_filename']))[0]
                item = QListWidgetItem(f'{uid} - {name}')
                if uid not in self.processed_uid_list:
                    self.not_processed_uid_list.append(uid)
                    item.setForeground(QColor(255, 0, 0))  # Red text for unprocessed
                self.listWidget_acquired_uids.addItem(item)

    def process_uids(self):
        if self.checkBox_process_all.isChecked():
            list_to_process = self.not_processed_uid_list
        else:
            selected_items = self.listWidget_acquired_uids.selectedItems()
            list_to_process = [item.text().split(' -')[0] for item in selected_items]
        for uid in list_to_process:
            run = self.tiled_catalog[uid]
            run.refresh()
            stop = run.metadata.get('stop')
            if stop:
                self.parent_gui.processing_thread.add_doc(stop)
            else:
                print(f'Skipping unfinished run {uid}')
