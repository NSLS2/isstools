
from PyQt5 import uic, QtGui, QtCore
import pkg_resources
import requests
import urllib.request
import numpy as np
import os
import re

from isstools.dialogs import UpdateUserDialog, SetEnergy, GetEmailAddress
from timeit import default_timer as timer
from isstools.dialogs.BasicDialogs import message_box
from isscloudtools.initialize import get_slack_service, get_dropbox_service, get_gmail_service
import bluesky.plan_stubs as bps
from PyQt5 import uic, QtWidgets

from xas.file_io import make_user_dir
from isscloudtools.slack import *
from isscloudtools.gmail import *
from isscloudtools.dropbox import *
import uuid

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_info_general.ui')

ROOT_PATH = '/nsls2/data/iss/legacy'
USER_PATH = 'processed'


class UIInfoGeneral(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE = None,
                 db = None,
                 parent = None,
                 cloud_dispatcher = None,
                 manager_dict = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        # Start QTimer to display current day and time
        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(1000)
        self.timer_update_time.timeout.connect(self.update_time)
        self.timer_update_time.start()

        self.timer_update_weather = QtCore.QTimer(self)
        self.timer_update_weather.singleShot(0, self.update_weather)
        self.timer_update_weather.setInterval(1000*60*5)
        self.timer_update_weather.timeout.connect(self.update_weather)
        self.timer_update_weather.start()
        self.db = db
        self.parent = parent
        self.cloud_dispatcher = cloud_dispatcher
        self.RE = RE
        self.manager_dict = manager_dict


        # if parent.gmail_service is None:
        #     try:
        #         self.push_cloud_setup.setEnabled(False)
        #         self.push_send_results.setEnabled(False)
        #     except:
        #         pass

        if self.RE is not None:
            self.RE.is_aborted = False
            self.timer_update_user_info = QtCore.QTimer()
            self.timer_update_user_info.timeout.connect(self.update_user_info)
            self.timer_update_user_info.start(60*1000)
            self.timer_update_user_info.singleShot(0, self.update_user_info)


        else:
            self.push_update_user.setEnabled(False)

        try:
            self.slack_client_bot, self.slack_client_oath = get_slack_service()
            self.gmail_service = get_gmail_service()
            self.dropbox_service = get_dropbox_service()
        except:
            pass
            # self.push_cloud_setup.setEnable(False)
            # self.push_send_results.setEnable(False)
            # self.push_send_to_dropbox.setEnable(False)



    def update_weather(self):
        weather = True
        if weather:
            try:
                current_weather = requests.get(
                    'http://api.openweathermap.org/data/2.5/weather?zip=11973&APPID=a3be6bc4eaf889b154327fadfd9d6532').json()
                string_current_weather  = current_weather['weather'][0]['main'] + ' in Upton, NY, it is {0:.0f} °F outside,\
                    humidity is {1:.0f}%'\
                    .format(((current_weather['main']['temp']-273)*1.8+32), current_weather['main']['humidity'])
                icon_url = 'http://openweathermap.org/img/w/' + current_weather['weather'][0]['icon'] + '.png'
                image = QtGui.QImage()
                image.loadFromData(urllib.request.urlopen(icon_url).read())
                self.label_current_weather_icon.setPixmap(QtGui.QPixmap(image))
            except:
                string_current_weather = 'Weather information not available'
            self.label_current_weather.setText(string_current_weather)

    def update_time(self):
        self.label_current_time.setText(
            'Today is {0}'.format(QtCore.QDateTime.currentDateTime().toString('MMMM d, yyyy, h:mm:ss ap')))

    def update_user_info(self):
        self.label_user_info.setText('{} is running  under Proposal {}/SAF {} '.
                                     format(self.RE.md['PI'], self.RE.md['proposal'], self.RE.md['saf']))
        self.cycle = ['', 'Spring', 'Summer', 'Fall']
        self.label_current_cycle.setText(
            'It is {} {} NSLS Cycle'.format(self.RE.md['year'], self.cycle[int(self.RE.md['cycle'])]))

    def set_user_info(self):
        dlg = UpdateUserDialog.UpdateUserDialog(self.RE.md['year'], self.RE.md['cycle'], self.RE.md['proposal'],
                                                self.RE.md['SAF'], self.RE.md['PI'], parent=self)
        if dlg.exec_():
            start = timer()
            self.RE.md['year'], self.RE.md['cycle'], self.RE.md['proposal'], self.RE.md['SAF'], self.RE.md[
                'PI'] = dlg.getValues()
            stop1 = timer()
            self.update_user_info()
            self.reset_managers()

    def reset_managers(self):
        path = self.manager_dict['sample_manager'].local_file_default_path
        folder_exists = make_user_dir(path)
        for item in self.manager_dict.values():
            item.reset()
            item.init_from_settings()
        self.parent.widget_scan_manager.scansChanged.emit()
        self.parent.widget_scan_manager.update_local_manager_list()

        self.parent.johann_emission.initialized = False
        self.parent.widget_info_beamline.push_set_emission_energy.setEnabled(0)


    def send_results(self):
        dlg = GetEmailAddress.GetEmailAddress('', parent=self)
        if dlg.exec_():
            email_address = dlg.getValue()
            regex = '^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
            if re.search(regex, email_address):
                 #print(f'email {email_address}')
                pass
            else:
                message_box('Error', 'Invaild email')
                return 0


        year=self.RE.md['year']
        cycle=self.RE.md['cycle']
        proposal = self.RE.md['proposal']
        PI = self.RE.md['PI']
        # working_directory = f'/nsls2/xf08id/users/{year}/{cycle}/{proposal}'
        working_directory = f'{ROOT_PATH}/{USER_PATH}/{year}/{cycle}/{proposal}'
        zip_file = f'{working_directory}/{proposal}.zip'

        id = str(uuid.uuid4())[0:5]

        zip_id_file = f'{proposal}-{id}.zip'

        if os.path.exists(zip_file):
            os.remove(zip_file)

        # os.system(f'zip {zip_file} {working_directory}/*.* ')
        os.system(f'zip {zip_file} {working_directory}/*.dat')

        folder = f'/{year}/{cycle}/'
        dropbox_upload_files(self.parent.dropbox_service, zip_file,folder,zip_id_file)

        link_url = dropbox_get_shared_link(self.parent.dropbox_service, f'{folder}{zip_id_file}' )
        print('Upload succesful')


        message = create_html_message(
            'staff08id@gmail.com',
            email_address,
            f'ISS beamline results Proposal {proposal}',
            f' <p> Dear {PI},</p> <p>You can download the result of your'
            f' experiment at ISS under proposal {proposal} here,</p> <p> {link_url} '
            f'</p> <p> Sincerely, </p> <p> ISS Staff </p>'
            )

        draft = upload_draft(self.parent.gmail_service, message)
        sent = send_draft(self.parent.gmail_service, draft)
        print('Email sent')
    #
    #
    # def cloud_setup(self):
    #     year = self.RE.md['year']
    #     cycle = self.RE.md['cycle']
    #     proposal = self.RE.md['proposal']
    #     PI = self.RE.md['PI']
    #     slack_channel = f'{year}-{cycle}-{proposal}'
    #     channel_id,channel_info = slack_channel_exists(self.parent.slack_client_bot,slack_channel)
    #     print(channel_id)
    #     if not channel_id:
    #         print('Slack channel not found, Creating new channel...')
    #         channel_id, channel_info = slack_create_channel(self.parent.slack_client_bot, slack_channel)
    #         slack_invite_to_channel(self.parent.slack_client_bot,channel_id)
    #
    #
    #     slack_url =  f'https://app.slack.com/client/T0178K9UAE6/{channel_id}'
    #     self.RE.md['slack_channel'] = channel_id
    #
    #     dropbox_folder =f'/{year}/{cycle}/{proposal}'
    #     if not dropbox_folder_exists(self.parent.dropbox_service,dropbox_folder):
    #         dropbox_create_folder(self.parent.dropbox_service, dropbox_folder)
    #
    #     dropbox_url = dropbox_get_shared_link(self.parent.dropbox_service, dropbox_folder)
    #
    #     dlg = GetEmailAddress.GetEmailAddress('', parent=self)
    #     if dlg.exec_():
    #         email_address = dlg.getValue()
    #         regex = '^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
    #         if re.search(regex, email_address):
    #              #print(f'email {email_address}')
    #             pass
    #         else:
    #             message_box('Error', 'Invaild email')
    #             return 0
    #
    #
    #     message = create_html_message(
    #         'staff08id@gmail.com',
    #         email_address,
    #         f'ISS beamline results Proposal {proposal}',
    #         f'<p> Dear {PI},</p> '
    #         f'<p>Slack channel to monitor yor experiemnt is {slack_url} </p>'
    #         f'<p>Data files will be uploaded to Dropbox folder at {dropbox_url} </p>'
    #         f'<p> Sincerely, </p> '
    #         f'<p> ISS Staff </p>'
    #         )
    #
    #     draft = upload_draft(self.parent.gmail_service, message)
    #     sent = send_draft(self.parent.gmail_service, draft)
    #     print('Email sent')

    # def send_to_dropbox(self):
    #     year = self.RE.md['year']
    #     cycle = self.RE.md['cycle']
    #     proposal = self.RE.md['proposal']
    #     working_directory = f'{ROOT_PATH}/{USER_PATH}/{year}/{cycle}/{proposal}'
    #     list_files_to_send = QtWidgets.QFileDialog.getOpenFileNames(directory = working_directory,
    #                                                        parent = self)[0]
    #     if list_files_to_send:
    #         for file in list_files_to_send:
    #             print(file)
    #             #self.cloud_dispatcher.load_to_dropbox(file)






















