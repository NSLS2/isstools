import re
import sys
import numpy as np
import pkg_resources
import math
import requests
import time as ttime
import uuid


from qtpy import uic, QtGui, QtCore, QtWidgets
from qtpy.QtGui import QPixmap, QCursor, QStandardItem
from qtpy.QtCore import QObject, Qt
from qtpy.QtCore import QThread, QSettings
from qtpy.QtWidgets import QMenu, QToolTip, QHBoxLayout, QWidget, QListWidgetItem
from isstools.elements.widget_motors import UIWidgetMotors, UIWidgetMotorsWithSlider
from ..elements.elements import remove_special_characters



from isstools.dialogs import UpdateUserDialog, SetEnergy, GetEmailAddress
from qtpy import uic, QtWidgets

from xas.file_io import make_user_dir
from isscloudtools.slack import *
from isscloudtools.gmail import *
from isscloudtools.dropbox import *


from qtpy.QtWidgets import QLabel, QPushButton, QLineEdit, QSizePolicy, QSpacerItem
from isstools.dialogs.BasicDialogs import question_message_box, error_message_box, message_box

from isstools.dialogs.BasicDialogs import message_box, question_message_box

import matplotlib.path as mpltPath

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_user_manager.ui')


ROOT_PATH = '/nsls2/data/iss/legacy'
USER_PATH = 'processed'

class UIUserManager(*uic.loadUiType(ui_path)):

    sample_list_changed_signal = QtCore.Signal()

    def __init__(self,
                 RE=None,
                 parent=None,
                 sample_manager=None,
                 user_manager=None,
                 scan_manager=None,
                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.RE=RE
        self.scan_manager = scan_manager
        self.sample_manager=sample_manager
        self.user_manager=user_manager
        self.enable_fields(False)
        self.pushButton_setup_user.clicked.connect(self.setup_user)
        self.pushButton_find_proposal.clicked.connect(self.find_proposal)
        self.pushButton_select_saf.clicked.connect(self.select_saf)
        self.push_create_sample.clicked.connect(self.create_new_sample)
        self.pushButton_cancel_setup.clicked.connect(self.cancel_setup)
        self.pushButton_archive_samples.clicked.connect(self.archive_sample)
        self.pushButton_restore_samples.clicked.connect(self.restore_sample)

        self.pushButton_archive_scans.clicked.connect(self.archive_scans)
        self.pushButton_restore_scans.clicked.connect(self.restore_scans)

        self.pushButton_add_metadata_key.clicked.connect(self.add_metadata_key)
        self.pushButton_remove_metadata_key.clicked.connect(self.remove_metadata_key)

        self.sample_list_changed_signal.connect(self.update_sample_list)
        self.comboBox_affiliations.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_users.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_users.activated.connect(self.select_from_comboboxes)
        self.comboBox_affiliations.activated.connect(self.select_from_comboboxes)

        self.checkBox_show_archived_samples.toggled.connect(self.show_archives)

        self.initialize()
        self.populate_comboboxes()

        self.listWidget_samples_archived.hide()

        self.pushButton_create_zip.clicked.connect(self.create_zip)
        self.pushButton_restore_samples.hide()

        self.label_proposal_title.setText('')

    def initialize(self):
        _, _current_user =  self.user_manager.current_user()
        self.lineEdit_user_first.setText(_current_user['first_name'])
        self.lineEdit_user_last.setText(_current_user['last_name'])
        self.spinBox_saf.setValue(int(_current_user['runs'][-1]['saf']))
        self.spinBox_proposal.setValue(int(_current_user['runs'][-1]['proposal']))
        self.lineEdit_email.setText(_current_user['email'])
        self.lineEdit_affiliation.setText(_current_user['affiliation'])
        if 'metadata' in _current_user.keys():
            self.listWidget_metadata.clear()
            for _key in _current_user['metadata']:
                self.listWidget_metadata.addItem(_key)
        else:
             self.listWidget_metadata.clear()
        self.update_sample_list()
        self.update_scan_list()


    def add_metadata_key(self):
        _key = self.lineEdit_new_metadata_key.text()
        if _key !='':
            self.user_manager.add_metadata_key(_key)
            self.listWidget_metadata.addItems(_key)

    def remove_metadata_key(self):
        _key = self.lineEdit_new_metadata_key.text()
        if _key !='':
            pass

    def archive_sample(self):
        # for item in self.listWidget_samples.selectedItems():
        #     indx = self.sample_manager.uid_to_sample_index(item.toolTip())
        #     self.sample_manager.archive_at_index(indx)
        index_list = [qindex.row() for qindex in self.listWidget_samples.selectedIndexes()]
        # for index in index_list:
        self.sample_manager.archive_at_index(index_list)

    def restore_sample(self):
        # for item in self.listWidget_samples_archived.selectedItems():
        #     indx = self.sample_manager.uid_to_sample_index(item.toolTip())
        #     self.sample_manager.restore_at_index(indx)
        index_list = [qindex.row() for qindex in self.listWidget_samples_archived.selectedIndexes()]
        # for index in index_list:
        self.sample_manager.restore_at_index(index_list)

    def archive_scans(self):
        # for item in self.listWidget_samples.selectedItems():
        #     indx = self.sample_manager.uid_to_sample_index(item.toolTip())
        #     self.sample_manager.archive_at_index(indx)
        index_list = [qindex.row() for qindex in self.listWidget_scans.selectedIndexes()]
        # for index in index_list:
        # self.sample_manager.archive_at_index(index_list)

    def restore_scans(self):
        # for item in self.listWidget_samples_archived.selectedItems():
        #     indx = self.sample_manager.uid_to_sample_index(item.toolTip())
        #     self.sample_manager.restore_at_index(indx)
        index_list = [qindex.row() for qindex in self.listWidget_scans_archived.selectedIndexes()]
        # for index in index_list:
        # self.sample_manager.restore_at_index(index_list)

    def update_scan_list(self):
        self.listWidget_scans.clear()
        for scan in self.scan_manager.scan_list_local:
            item = QListWidgetItem(scan['scan_def'])
            item.setToolTip(scan['uid'])
            self.listWidget_scans.addItem(item)




    def update_sample_list(self):
        self.listWidget_samples.clear()
        self.listWidget_samples_archived.clear()
        for sample in self.sample_manager.all_samples:
            item = QListWidgetItem(f'{sample.name} - {sample.comment}')
            item.setToolTip(sample.uid)
            if sample.archived:
                self.listWidget_samples_archived.addItem(item)
            else:
                self.listWidget_samples.addItem(item)

    def populate_comboboxes(self):
        self.comboBox_affiliations.currentIndexChanged.disconnect(self.select_from_comboboxes)
        self.comboBox_users.currentIndexChanged.disconnect(self.select_from_comboboxes)
        self.comboBox_users.activated.disconnect(self.select_from_comboboxes)
        self.comboBox_affiliations.activated.disconnect(self.select_from_comboboxes)
        self.comboBox_users.clear()
        self.comboBox_affiliations.clear()
        users = [f"{u['first_name']} {u['last_name']}" for u in self.user_manager.users]
        affiliations = list(set([u['affiliation'] for u in self.user_manager.users]))
        users.sort()
        affiliations.sort()

        for i, user in enumerate(users):
            self.comboBox_users.addItem(user)
            if user == f"{self.lineEdit_user_first.text()} {self.lineEdit_user_last.text()}":
                idx_user = i
        for j, affiliation in enumerate(affiliations):
            self.comboBox_affiliations.addItem(affiliation)
            if affiliation == self.lineEdit_affiliation.text():
                idx_affiliation = j
        self.comboBox_users.setCurrentIndex(idx_user)
        self.comboBox_affiliations.setCurrentIndex(idx_affiliation)

        self.comboBox_affiliations.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_users.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_users.activated.connect(self.select_from_comboboxes)
        self.comboBox_affiliations.activated.connect(self.select_from_comboboxes)

    def show_archives(self):
        sender_object = QObject().sender()
        object_dict = {self.checkBox_show_archived_samples: [self.listWidget_samples_archived,
                                                             self.pushButton_restore_samples]}
        if sender_object.isChecked():
            for object in object_dict[sender_object]:
                object.show()
        else:
            for object in object_dict[sender_object]:
                object.hide()

    def enable_fields(self, enable):
        elements = ['comboBox_users',
                    'comboBox_affiliations',
                    'pushButton_find_proposal',
                    'spinBox_proposal',
                    'spinBox_saf',
                    'listWidget_safs',
                    'listWidget_experimenters',
                    'pushButton_select_saf']

        for element in elements:
            getattr(self, element).setEnabled(enable)
        elements = [
            'lineEdit_email',
            'lineEdit_user_first',
            'lineEdit_user_last',
            'lineEdit_affiliation',
            ]
        for element in elements:
            getattr(self, element).setReadOnly(not enable)

    def setup_user(self):
        if self.pushButton_setup_user.isChecked():
            self.current_first = self.lineEdit_user_first.text()
            self.current_last = self.lineEdit_user_last.text()
            self.current_affiliation = self.lineEdit_affiliation.text()
            self.current_email = self.lineEdit_email.text()
            self.enable_fields(True)
        else:
            self.enable_fields(False)
            _first = self.lineEdit_user_first.text()
            _last = self.lineEdit_user_last.text()
            _affiliation = self.lineEdit_affiliation.text()
            _email = self.lineEdit_email.text()
            self.user_manager.set_user(_first, _last,_affiliation,_email)
            _proposal = self.spinBox_proposal.value()
            _saf = self.spinBox_saf.value()
            _experimenters = []
            for j in range(self.listWidget_experimenters.count()):
                _experimenters.append(self.listWidget_experimenters.item(j).text())
            self.user_manager.add_run(_proposal, _saf, _experimenters)
            self.cloud_setup(email_address=_email)
            self.populate_comboboxes()
            self.parent.widget_scan_manager.update_local_manager_list()
            self.parent.widget_info_beamline.push_set_emission_energy.setEnabled(False)
            self.parent.widget_info_general.update_user_info()



    def select_from_comboboxes(self):
        sender_object = QObject().sender()
        sender_object_name = self.sender().objectName()
        if sender_object_name == 'comboBox_users':
            first_name, last_name = sender_object.currentText().split(' ')
            self.lineEdit_user_first.setText(first_name)
            self.lineEdit_user_last.setText(last_name)
            user_dict = self.user_manager.find_user(first_name, last_name)
            if user_dict is not None: # this is a bit paranoid, but so be it
                affiliation = user_dict['affiliation']
                self.lineEdit_affiliation.setText(affiliation)
                self.comboBox_affiliations.currentIndexChanged.disconnect(self.select_from_comboboxes)
                self.comboBox_affiliations.activated.disconnect(self.select_from_comboboxes)
                for i in range(self.comboBox_affiliations.count()):
                    if self.comboBox_affiliations.itemText(i) == affiliation:
                        self.comboBox_affiliations.setCurrentIndex(i)
                        break
                self.comboBox_affiliations.currentIndexChanged.connect(self.select_from_comboboxes)
                self.comboBox_affiliations.activated.connect(self.select_from_comboboxes)
                email = user_dict['email']
                self.lineEdit_email.setText(email)
        if sender_object_name == 'comboBox_affiliations':
            self.lineEdit_affiliation.setText(sender_object.currentText())

    def find_proposal(self):
        headers = {'accept': 'application/json',}
        proposal = str(self.spinBox_proposal.value())
        proposal_info = requests.get(f'https://api.nsls2.bnl.gov/v1/proposal/{proposal}', headers=headers).json()

        if 'error_message' in proposal_info.keys():
            error_message_box('Proposal not found')
        else:
            title = proposal_info['proposal']['title']
            if title is None: title = ''
            if len(title) > 100:
                title = title[:101]
            if  len(title) > 50:
                title = f'{title[:50]}\n{title[50]}'
            self.label_proposal_title.setText(title)
            self.listWidget_safs.clear()
            self.listWidget_experimenters.clear()
            safs = proposal_info['proposal']['safs']
            for saf in safs:
                item = QListWidgetItem(saf['saf_id'])
                if saf['status'] != 'APPROVED':
                    item.setForeground(Qt.red)
                self.listWidget_safs.addItem(item)
            users = proposal_info['proposal']['users']
            for user in users:
                item = QListWidgetItem(user['first_name']+ ' ' +user['last_name'])
                if user['is_pi']:
                    item.setForeground(Qt.blue)
                self.listWidget_experimenters.addItem(item)


    def select_saf(self):
        saf = self.listWidget_safs.currentItem().text()
        self.spinBox_saf.setValue(int(saf))


    def cloud_setup(self, email_address = None):
        year = self.RE.md['year']
        cycle = self.RE.md['cycle']
        proposal = self.RE.md['proposal']
        PI = self.RE.md['PI']
        slack_channel = f'{year}-{cycle}-{proposal}'
        # channel_id,channel_info = slack_channel_exists(self.parent.slack_client_bot,slack_channel)
        # print(channel_id)
        # if not channel_id:
        #     try:
        #         print('Slack channel not found, Creating new channel...')
        #         channel_id, channel_info = slack_create_channel(self.parent.slack_client_bot, slack_channel)
        #         print('Trying to invite user to the channel')
        #         slack_invite_to_channel(self.parent.slack_client_bot,channel_id)
        #     except Exception as e:
        #         print(f'Failed to invite user to channel. Error: {e}')
        #
        # slack_url =  f'https://app.slack.com/client/T0178K9UAE6/{channel_id}'
        # self.RE.md['slack_channel'] = channel_id

        dropbox_folder =f'/{year}/{cycle}/{proposal}'
        if not dropbox_folder_exists(self.parent.dropbox_service,dropbox_folder):
            dropbox_create_folder(self.parent.dropbox_service, dropbox_folder)

        dropbox_url = dropbox_get_shared_link(self.parent.dropbox_service, dropbox_folder)

        if email_address ==None:
            dlg = GetEmailAddress.GetEmailAddress('', parent=self)
            if dlg.exec_():
                email_address = dlg.getValue()

        regex = '^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
        if re.search(regex, email_address):
            # print(f'email {email_address}')
            pass
        else:
            message_box('Error', 'Invaild email')
            return 0


        message = create_html_message(
            'staff08id@gmail.com',
            email_address,
            f'ISS beamline results Proposal {proposal}',
            f'<p> Dear {PI},</p> '
            # f'<p>Slack channel to monitor yor experiemnt is {slack_url} </p>'
            f'<p>Data files will be uploaded to Dropbox folder at {dropbox_url} </p>'
            f'<p> Sincerely, </p> '
            f'<p> ISS Staff </p>'
            )

        draft = upload_draft(self.parent.gmail_service, message)
        sent = send_draft(self.parent.gmail_service, draft)
        print('Email sent')

    def create_new_sample(self):
        sample_name = self.lineEdit_sample_name.text()
        if (sample_name == '') or (sample_name.isspace()):
            message_box('Warning', 'Sample name is empty')
            return
        sample_name = remove_special_characters(sample_name)
        sample_comment = self.lineEdit_sample_comment.text()

        self.sample_manager._currently_selected_index = -1
        self.sample_manager.add_new_sample(sample_name, sample_comment, [])

    def cancel_setup(self):
        self.pushButton_setup_user.setChecked(False)
        self.lineEdit_user_first.setText(self.current_first)
        self.lineEdit_user_last.setText(self.current_last)
        self.lineEdit_affiliation.setText(self.current_affiliation)
        self.lineEdit_email.setText(self.current_email)
        self.enable_fields(False)
        self.populate_comboboxes() # this is a bit of an overkill, but it takes care of the correct indexes in comboboxes

    def create_zip(self):
        _, _current_user = self.user_manager.current_user()
        proposal =(_current_user['runs'][-1]['proposal'])

        year = self.RE.md['year']
        cycle = self.RE.md['cycle']
        proposal = self.RE.md['proposal']
        PI = self.RE.md['PI']
        email_address = self.lineEdit_email.text()
        # working_directory = f'/nsls2/xf08id/users/{year}/{cycle}/{proposal}'
        working_directory = f'{ROOT_PATH}/{USER_PATH}/{year}/{cycle}/{proposal}'
        zip_file = f'{working_directory}/{proposal}.zip'
        id = str(uuid.uuid4())[0:5]
        zip_id_file = f'{proposal}-{id}.zip'

        if os.path.exists(zip_file):
            os.remove(zip_file)

        # os.system(f'zip {zip_file} {working_directory}/*.* ')

        print('Creating a zip file')
        os.system(f"cd '{working_directory}'; zip '{zip_id_file}' *.dat")

        message = create_html_message(
            'staff08id@gmail.com',
            email_address,
            f'ISS beamline data for Proposal {proposal}\n',
            f' <p> Dear {PI},</p> <p>You can download the results of your experiment from JupyterHub by following the steps below: </p>'
            f'<p> 1. Go to https://jupyter.nsls2.bnl.gov and log in using your BNL credentials. </p>'
            f'<p> 2. Click on "Start My Server" to launch a new server or relaunch an already active server. </p>'
            f'<p> 3. In the "Server Options" window, select "Pluto Cluster" as the job profile, then click "Start".</p>'
            f'<p> 4. In the File menu, select "Open from Path..." </p>'
            f'<p> 5. Copy and paste the following path (without quotation marks): "{working_directory}" </p>'
            f'<p> 6. Right-click on the zip file named {zip_id_file} and download it to your PC. </p> '
            f'<p> Sincerely, </p> <p> ISS Staff </p>'
        )

        draft = upload_draft(self.parent.gmail_service, message)
        sent = send_draft(self.parent.gmail_service, draft)
        print('Email sent for zip files')
























