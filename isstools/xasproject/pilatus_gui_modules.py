# print(ttime.ctime() + ' >>>> ' + __file__)
# from xas.pid import PID
# from xas.image_analysis import determine_beam_position_from_fb_image
#
# import sys
# sys.path.append('/home/xf08id/Repos/xas/')

# import xas.handlers

from ophyd import EpicsMotor as _EpicsMotor
from ophyd import Component as Cpt, Device, EpicsSignalRO, Kind

from ophyd import (ProsilicaDetector, SingleTrigger, Component as Cpt, Device,
                   EpicsSignal, EpicsSignalRO, ImagePlugin, StatsPlugin, ROIPlugin,
                   DeviceStatus, Signal)
from nslsii.devices import TwoButtonShutter
import bluesky.plans as bp
from ophyd.status import SubscriptionStatus

class EpicsMotorWithTweaking(_EpicsMotor):
    # set does not work in this class; use put!
    twv = Cpt(EpicsSignal, '.TWV', kind='omitted')
    twr = Cpt(EpicsSignal, '.TWR', kind='omitted')
    twf = Cpt(EpicsSignal, '.TWF', kind='omitted')

# EpicsMotor = _EpicsMotor
EpicsMotor = EpicsMotorWithTweaking


class StuckingEpicsMotor(EpicsMotor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stuck_check_delay = 2

    def _stuck_check(self, value, old_value, **kwargs):
        if value == 1: # here value == self.motor_is_moving
            cur_sp = self.user_setpoint.get()
            old_pos = self.user_readback.get()

            while self.motor_is_moving.get() == 1:
                ttime.sleep(self._stuck_check_delay)
                new_pos = self.user_readback.get()
                if new_pos == old_pos:
                    print_to_gui(f'[Debug message]: {ttime.ctime()}: {self.name} motor got stuck ... unstucking it')
                    self.stop()
                    self.move(cur_sp, wait=True, **kwargs)
                else:
                    old_pos = new_pos


    def move(self, position, wait=True, **kwargs):
        cid = self.motor_is_moving.subscribe(self._stuck_check)
        status = super().move(position, wait=wait, **kwargs)
        self.motor_is_moving.unsubscribe(cid)
        return status


class StuckingEpicsMotorThatFlies(StuckingEpicsMotor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flying = None

    def append_flying_status_pv(self, pv):
        self.flying = pv

    def _stuck_check(self, value, old_value, **kwargs):
        if value == 1:  # here value == self.motor_is_moving
            cur_sp = self.user_setpoint.get()
            old_pos = self.user_readback.get()
            if self.flying is not None:
                is_flying = bool(self.flying.get())
            else:
                is_flying = False

            while self.motor_is_moving.get() == 1:
                ttime.sleep(self._stuck_check_delay)
                new_pos = self.user_readback.get()
                if new_pos == old_pos and (not is_flying):
                    print(f'[Debug message]: {ttime.ctime()}: {self.name} motor got stuck ... unstucking it')
                    self.stop()
                    self.move(cur_sp, wait=True, **kwargs)
                else:
                    old_pos = new_pos


class InfirmStuckingEpicsMotor(StuckingEpicsMotor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dwell_time = 2
        self.n_tries = 5
        self.low_lim = None

    def set_low_lim(self, low_lim=8.5):
        self.low_lim = low_lim

    def check_position_vs_low_lim(self, position):
        if self.low_lim is not None:
            if position < self.low_lim:
                position = self.low_lim
        return position


    def append_homing_pv(self, homing):
        self.homing = homing

    def one_move_attempt(self, position, wait=True, attempt_num=None, **kwargs):
        print_to_gui(f'(attempt_num={attempt_num}) moving hhm_y_precise to {position}', add_timestamp=True, tag='Debug')
        status = super().move(position, wait=wait, **kwargs)
        status.wait()
        print_to_gui(f'(attempt_num={attempt_num}) user readback value of hhm_y_precise before homing is {self.user_readback.value}', add_timestamp=True, tag='Debug')
        self.homing.put('1')
        ttime.sleep(self.dwell_time)
        print_to_gui(f'(attempt_num={attempt_num}) user readback value of hhm_y_precise after homing is {self.user_readback.value}', add_timestamp=True, tag='Debug')
        # self.user_setpoint.set(self.position)

        return status

    def move(self, new_position, wait=True, max_attempts=20, **kwargs):
        wait=True
        new_position = self.check_position_vs_low_lim(new_position)

        for idx in range(20):
            status = self.one_move_attempt(new_position, wait=wait, attempt_num=idx, **kwargs)
            if abs(new_position - self.position) < 0.0075:
                break
            if idx == 19:
                print('exceeded the maximum number of attempts (20) to bring the motor to requested position')
        ttime.sleep(1)
        return status

    def set(self, *args, **kwargs):
        if 'wait' in kwargs.keys():
            print_to_gui(f'{self.name} set kwargs = {kwargs}', add_timestamp=True, tag='Debug')
            kwargs.pop('wait')
        return super().set(*args, wait=True, **kwargs)



class HHMTrajDesc(Device):
    filename = Cpt(EpicsSignal, '-Name')
    elem = Cpt(EpicsSignal, '-Elem')
    edge = Cpt(EpicsSignal, '-Edge')
    e0 = Cpt(EpicsSignal, '-E0')




class HHM(Device):
    _default_configuration_attrs = ('pitch', 'roll', 'theta', 'y', 'energy')
    _default_read_attrs = ('pitch', 'roll', 'theta', 'y', 'energy')
    "High Heat Load Monochromator"
    ip = '10.66.58.106'

    pitch = Cpt(EpicsMotor, 'Mono:HHM-Ax:P}Mtr', kind='hinted')
    roll = Cpt(EpicsMotor, 'Mono:HHM-Ax:R}Mtr', kind='hinted')
    y = Cpt(StuckingEpicsMotor, 'Mono:HHM-Ax:Y}Mtr', kind='hinted')
    theta = Cpt(EpicsMotor, 'Mono:HHM-Ax:Th}Mtr', kind='hinted')
    # theta_speed = Cpt(EpicsSignal, 'Mono:HHM-Ax:Th}Mtr.VMAX', kind='hinted')
    # theta_speed_max = Cpt(EpicsSignal, 'Mono:HHM-Ax:Th}Mtr.VELO', kind='hinted')
    energy = Cpt(StuckingEpicsMotorThatFlies, 'Mono:HHM-Ax:E}Mtr', kind=Kind.hinted)

    main_motor_res = Cpt(EpicsSignal, 'Mono:HHM-Ax:Th}Mtr.MRES')

    # The following are related to trajectory motion
    lut_number = Cpt(EpicsSignal, 'MC:06}LUT-Set')
    lut_number_rbv = Cpt(EpicsSignal, 'MC:06}LUT-Read')
    lut_start_transfer = Cpt(EpicsSignal, 'MC:06}TransferLUT')
    lut_transfering = Cpt(EpicsSignal, 'MC:06}TransferLUT-Read')
    trajectory_loading = Cpt(EpicsSignal, 'MC:06}TrajLoading')
    traj_mode = Cpt(EpicsSignal, 'MC:06}TrajFlag1-Set')
    traj_mode_rbv = Cpt(EpicsSignal, 'MC:06}TrajFlag1-Read')
    enable_ty = Cpt(EpicsSignal, 'MC:06}TrajFlag2-Set')
    enable_ty_rbv = Cpt(EpicsSignal, 'MC:06}TrajFlag2-Read')
    cycle_limit = Cpt(EpicsSignal, 'MC:06}TrajRows-Set')
    cycle_limit_rbv = Cpt(EpicsSignal, 'MC:06}TrajRows-Read')
    enable_loop = Cpt(EpicsSignal, 'MC:06}TrajLoopFlag-Set')
    enable_loop_rbv = Cpt(EpicsSignal, 'MC:06}TrajLoopFlag')

    prepare_trajectory = Cpt(EpicsSignal, 'MC:06}PrepareTraj')
    trajectory_ready = Cpt(EpicsSignal, 'MC:06}TrajInitPlc-Read')
    start_trajectory = Cpt(EpicsSignal, 'MC:06}StartTraj')
    stop_trajectory = Cpt(EpicsSignal, 'MC:06}StopTraj')
    trajectory_running = Cpt(EpicsSignal,'MC:06}TrajRunning', write_pv='MC:06}TrajRunning-Set')
    trajectory_progress = Cpt(EpicsSignal,'MC:06}TrajProgress')
    trajectory_name = Cpt(EpicsSignal, 'MC:06}TrajFilename')

    traj1 = Cpt(HHMTrajDesc, 'MC:06}Traj:1')
    traj2 = Cpt(HHMTrajDesc, 'MC:06}Traj:2')
    traj3 = Cpt(HHMTrajDesc, 'MC:06}Traj:3')
    traj4 = Cpt(HHMTrajDesc, 'MC:06}Traj:4')
    traj5 = Cpt(HHMTrajDesc, 'MC:06}Traj:5')
    traj6 = Cpt(HHMTrajDesc, 'MC:06}Traj:6')
    traj7 = Cpt(HHMTrajDesc, 'MC:06}Traj:7')
    traj8 = Cpt(HHMTrajDesc, 'MC:06}Traj:8')
    traj9 = Cpt(HHMTrajDesc, 'MC:06}Traj:9')

    fb_status = Cpt(EpicsSignal, 'Mono:HHM-Ax:P}FB-Sts')
    fb_center = Cpt(EpicsSignal, 'Mono:HHM-Ax:P}FB-Center')
    fb_line = Cpt(EpicsSignal, 'Mono:HHM-Ax:P}FB-Line')
    fb_nlines = Cpt(EpicsSignal, 'Mono:HHM-Ax:P}FB-NLines')
    fb_nmeasures = Cpt(EpicsSignal, 'Mono:HHM-Ax:P}FB-NMeasures')
    fb_pcoeff = Cpt(EpicsSignal, 'Mono:HHM-Ax:P}FB-PCoeff')
    fb_hostname = Cpt(EpicsSignal, 'Mono:HHM-Ax:P}FB-Hostname')
    fb_heartbeat = Cpt(EpicsSignal, 'Mono:HHM-Ax:P}FB-Heartbeat')
    fb_status_err = Cpt(EpicsSignal, 'Mono:HHM-Ax:P}FB-Err')
    fb_status_msg = Cpt(EpicsSignal, 'Mono:HHM-Ax:P}FB-StsMsg', string=True)

    # fb_status = Signal(name='fb_status')
    # fb_center = Signal(name='fb_center')
    # fb_line = Signal(name='fb_line')
    # fb_nlines = Signal(name='fb_nlines')
    # fb_nmeasures = Signal(name='fb_nmeasures')
    # fb_pcoeff = Signal(name='fb_pcoeff')
    # fb_hostname = Signal(name='fb_hostname')
    # fb_heartbeat = Signal(name='fb_heartbeat')
    # fb_status_err = Signal(name='fb_status_err')
    # fb_status_msg = Signal(name='fb_status_msg')

    angle_offset = Cpt(EpicsSignal, 'Mono:HHM-Ax:E}Offset', limits=True)
    home_y = Cpt(EpicsSignal, 'MC:06}Home-HHMY')
    y_precise = Cpt(InfirmStuckingEpicsMotor, 'Mono:HHM-Ax:Y}Mtr', kind='hinted')

    servocycle = 16000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.pulses_per_deg = 1 / self.main_motor_res.get()
        except ZeroDivisionError:
            self.pulses_per_deg = -1

        # self.enc = enc
        self._preparing = None
        self._starting = None
        self.y_precise.append_homing_pv(self.home_y)
        # self.y_precise.set_low_lim(low_lim=8.5)

        self.energy.append_flying_status_pv(self.trajectory_running)

        self.flying_status = None


    # def stage(self):
    #     print(f'{ttime.ctime()} >>>>> HHM STAGED')
    #     return super().stage()

    def _ensure_mono_faces_down(self):
        _, emax = trajectory_manager.read_trajectory_limits()
        hhm.energy.move(emax + 50)

    def prepare(self):
        def callback(value, old_value, **kwargs):
            if int(round(old_value)) == 1 and int(round(value)) == 0:
                if self._preparing or self._preparing is None:
                    self._preparing = False
                    return True
                else:
                    self._preparing = True
            return False

        status = SubscriptionStatus(self.trajectory_ready, callback)

        # print_to_gui(f'Mono trajectory prepare starting...', add_timestamp=True, ntabs=2)

        self._ensure_mono_faces_down()
        self.prepare_trajectory.set('1')  # Yes, the IOC requires a string.
        status.wait()
        # print_to_gui(f'Ensuring mono faces down (starting)', add_timestamp=True, ntabs=2)
        # self._ensure_mono_faces_down()
        # print_to_gui(f'Mono trajectory prepare done', add_timestamp=True, ntabs=2)
        self.flying_status = None

    def kickoff(self):
        def callback(value, old_value, **kwargs):

            if int(round(old_value)) == 1 and int(round(value)) == 0:
                if self._starting or self._starting is None:
                    self._starting = False
                    return True
                else:
                    self._starting = True
                return False

        self.flying_status = SubscriptionStatus(self.trajectory_running, callback)
        self.start_trajectory.set('1')
        return self.flying_status

    def complete(self):
        self.flying_status = None

    def abort_trajectory(self):
        is_flying = (self.flying_status is not None) and (not self.flying_status.done)
        self.stop_trajectory.put('1')
        if is_flying:
            print_to_gui('Stopping trajectory ... ', tag='HHM')
            if not self.flying_status.done:
                self.flying_status.set_finished()
            print_to_gui('Stopped trajectory', tag='HHM')
        return is_flying


    def home_y_pos(self):
        self.home_y.put('1')


    def set_new_angle_offset(self, value, error_message_func=None):
        try:
            self.angle_offset.put(float(value))
            return True
        except Exception as exc:
            if type(exc) == ophyd_utils.errors.LimitError:
                msg = 'HHM limit error'
                print_to_gui(f'[Energy calibration] {msg}.'.format(exc))
                if error_message_func is not None:
                    error_message_func(msg)
            else:
                msg = f'HHM error. Something went wrong, not the limit: {exc}'
                print_to_gui(f'[Energy calibration] {msg}')
                if error_message_func is not None:
                    error_message_func(msg)
            return False

    def calibrate(self, energy_nominal, energy_actual, error_message_func=None):
        offset_actual = xray.energy2encoder(energy_actual, hhm.pulses_per_deg) / hhm.pulses_per_deg
        offset_nominal = xray.energy2encoder(energy_nominal, hhm.pulses_per_deg) / hhm.pulses_per_deg
        angular_offset_shift = offset_actual - offset_nominal
        new_angular_offset = self.angle_offset.value - angular_offset_shift
        return self.set_new_angle_offset(new_angular_offset, error_message_func=error_message_func)

    def get_angle_offset_deg_str(self):
        return f'{np.round(hhm.angle_offset.get() * 180 / np.pi, 3)} deg'

    def get_mono_encoder_resolution_str(self):
        return f'{(np.round(hhm.main_motor_res.get() * np.pi / 180 * 1e9))} nrad'


hhm = HHM('XF:08IDA-OP{', name='hhm')
# TODO: move to the HHM class definition.
hhm_z_home = Cpt(EpicsSignal,'XF:08IDA-OP{MC:06}Home-HHMY')

# Try to read it first time to avoid the generic 'object' to be returned
# as an old value from hhm.trajectory_running._readback.
try:
    hhm.wait_for_connection()
    _ = hhm.trajectory_ready.read()
    _ = hhm.trajectory_running.read()
except:
    pass


# hhm.hints = {'fields': ['hhm_energy', 'hhm_pitch', 'hhm_roll', 'hhm_theta', 'hhm_y']}
# hinted also is automatically set as read so no need to set read_attrs
hhm.energy.kind = 'hinted'
hhm.pitch.kind = 'hinted'
hhm.roll.kind = 'hinted'
hhm.theta.kind = 'hinted'
hhm.y.kind = 'hinted'

hhm.read_attrs = ['pitch', 'roll', 'theta', 'y', 'energy']


import time as ttime

print(ttime.ctime() + ' >>>> ' + __file__)


from ophyd import (Component as Cpt, Device,
                   EpicsSignal, ROIPlugin, OverlayPlugin,
                   Signal, HDF5Plugin)
from ophyd.areadetector.plugins import ROIStatPlugin_V34,  ImagePlugin_V33

from ophyd.areadetector.filestore_mixins import FileStoreTIFFIterativeWrite, FileStoreHDF5IterativeWrite
from ophyd.areadetector.cam import PilatusDetectorCam
from ophyd.areadetector.detectors import PilatusDetector
from ophyd.areadetector.base import EpicsSignalWithRBV as SignalWithRBV
from ophyd.areadetector import TIFFPlugin
from ophyd.sim import NullStatus
from nslsii.ad33 import StatsPluginV33
from nslsii.ad33 import SingleTriggerV33
from ophyd.areadetector.base import DDC_SignalWithRBV, DDC_EpicsSignalRO
import itertools
from collections import deque, OrderedDict
from ophyd.areadetector.plugins import ImagePlugin_V33

ROOT_PATH_SHARED = '/nsls2/data/iss/legacy/xf08id'
ROOT_PATH = '/nsls2/data/iss/legacy'
RAW_PATH = 'raw'
USER_PATH = 'processed'


class AnalogPizzaBoxTrigger(Device):
    freq = Cpt(EpicsSignal,'Frequency-SP')
    duty_cycle = Cpt(EpicsSignal,'DutyCycle-SP')
    max_counts = Cpt(EpicsSignal,'MaxCount-SP')

    acquire = Cpt(EpicsSignal, 'Mode-SP')
    acquiring = Cpt(EpicsSignal, 'Status-I')
    filename = Cpt(EpicsSignal,'Filename-SP', string=True)
    filebin_status = Cpt(EpicsSignalRO,'File:Status-I')
    stream = Cpt(EpicsSignal,'Stream:Mode-SP')


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._acquiring = None

        self._asset_docs_cache = deque()
        self._resource_uid = None
        self._datum_counter = None

    def prepare_to_fly(self, traj_duration):
        self.num_points = int(self.freq.get() * (traj_duration + 1))

    # Step-scan interface
    def stage(self):
        staged_list = super().stage()

        file_uid = new_uid()
        self.fn = f'{ROOT_PATH}/{RAW_PATH}/apb/{dt.datetime.strftime(dt.datetime.now(), "%Y/%m/%d")}/{file_uid}.bin'
        self.filename.set(self.fn).wait()
        # self.poke_streaming_destination()
        self._resource_uid = new_uid()
        resource = {'spec': 'APB_TRIGGER', #self.name.upper(),
                    'root': ROOT_PATH,  # from 00-startup.py (added by mrakitin for future generations :D)
                    'resource_path': self.fn,
                    'resource_kwargs': {},
                    'path_semantics': os.name,
                    'uid': self._resource_uid}
        self._asset_docs_cache.append(('resource', resource))
        self._datum_counter = itertools.count()
        self.max_counts.set(self.num_points).wait()
        self.stream.set(1).wait()
        return staged_list

    def unstage(self):
        self._datum_counter = None
        self.stream.set(0).wait()
        return super().unstage()

    def kickoff(self):
        return self.acquire.set(2)

    def complete(self):
        self.acquire.set(0).wait()
        self._datum_ids = []
        datum_id = '{}/{}'.format(self._resource_uid, next(self._datum_counter))
        datum = {'resource': self._resource_uid,
                 'datum_kwargs': {},
                 'datum_id': datum_id}
        self._asset_docs_cache.append(('datum', datum))
        self._datum_ids.append(datum_id)
        return NullStatus()


    def collect(self):
        print_to_gui(f'{ttime.ctime()} >>> {self.name} collect starting')
        now = ttime.time()
        for datum_id in self._datum_ids:
            data = {self.name: datum_id}
            yield {'data': data,
                   'timestamps': {key: now for key in data}, 'time': now,
                   'filled': {key: False for key in data}}
            # print(f'yield data {ttime.ctime(ttime.time())}')
        print_to_gui(f'{ttime.ctime()} >>> {self.name} collect complete')

        # self.unstage()


    def describe_collect(self):
        return_dict = {self.name:
                           {f'{self.name}': {'source': self.name.upper(),
                                             'dtype': 'array',
                                             'shape': [-1, -1],
                                             'filename': f'{self.fn}',
                                             'external': 'FILESTORE:'}}}
        return return_dict


    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item


    # def calc_num_points(self):
    #     # tr = trajectory_manager(hhm)
    #     info = trajectory_manager.read_info(silent=True)
    #     lut = str(int(hhm.lut_number_rbv.get()))
    #     traj_duration = int(info[lut]['size']) / 16000
    #     acq_num_points = traj_duration * self.acq_rate.get() * 1000 * 1.3
    #     self.num_points = int(round(acq_num_points, ndigits=-3))

apb_trigger = AnalogPizzaBoxTrigger(prefix="XF:08IDB-CT{PBA:1}:Pulse:1:", name="apb_trigger")
apb_trigger_xs = AnalogPizzaBoxTrigger(prefix="XF:08IDB-CT{PBA:1}:Pulse:1:", name="apb_trigger_xs")
apb_trigger_pil100k = AnalogPizzaBoxTrigger(prefix="XF:08IDB-CT{PBA:1}:Pulse:2:", name="apb_trigger_pil100k")

from databroker.assets.handlers_base import HandlerBase

class APBTriggerFileHandler(HandlerBase):
    "Read APB trigger *.bin files"
    def __init__(self, fpath):
        raw_data = np.fromfile(fpath, dtype=np.int32)
        raw_data = raw_data.reshape((raw_data.size // 3, 3))
        columns = ['timestamp', 'transition']
        derived_data = np.zeros((raw_data.shape[0], 2))
        derived_data[:, 0] = raw_data[:, 1] + raw_data[:, 2]  * 8.0051232 * 1e-9  # Unix timestamp with nanoseconds
        derived_data[:, 1] = raw_data[:, 0]

        self.df = pd.DataFrame(data=derived_data, columns=columns)
        self.raw_data = raw_data

    def __call__(self):
        return self.df




class PilatusDetectorCamV33(PilatusDetectorCam):
    '''This is used to update the Pilatus to AD33.'''

    wait_for_plugins = Cpt(EpicsSignal, 'WaitForPlugins',
                           string=True, kind='config')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs['wait_for_plugins'] = 'Yes'

    def ensure_nonblocking(self):
        self.stage_sigs['wait_for_plugins'] = 'Yes'
        for c in self.parent.component_names:
            cpt = getattr(self.parent, c)
            if cpt is self:
                continue
            if hasattr(cpt, 'ensure_nonblocking'):
                cpt.ensure_nonblocking()

    file_path = Cpt(SignalWithRBV, 'FilePath', string=True)
    file_name = Cpt(SignalWithRBV, 'FileName', string=True)
    file_template = Cpt(SignalWithRBV, 'FileName', string=True)
    file_number = Cpt(SignalWithRBV, 'FileNumber')
    set_energy = Cpt(SignalWithRBV, 'Energy')


class PilatusDetectorCam(PilatusDetector):
    cam = Cpt(PilatusDetectorCamV33, 'cam1:')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cam.ensure_nonblocking()



class HDF5PluginWithFileStore(HDF5Plugin, FileStoreHDF5IterativeWrite):
    """Add this as a component to detectors that write HDF5s."""
    def get_frames_per_point(self):
        return 1
        # if not self.parent.is_flying:
        #     return self.parent.cam.num_images.get()
        # else:
        #     return 1



# Making ROIStatPlugin that is actually useful
class ISSROIStatPlugin(ROIStatPlugin_V34):
    for i in range(1,5):
        _attr = f'roi{i}'
        _attr_min_x = f'min_x'
        _attr_min_y = f'min_y'
        _pv_min_x = f'{i}:MinX'
        _pv_min_y = f'{i}:MinY'
        _attr_size_x = f'size_x'
        _attr_size_y = f'size_y'
        _pv_size_x = f'{i}:SizeX'
        _pv_size_y = f'{i}:SizeY'

        # this does work:
        vars()[_attr] = DDC_SignalWithRBV(
            (_attr_min_x, _pv_min_x),
            (_attr_min_y, _pv_min_y),
            (_attr_size_x, _pv_size_x),
            (_attr_size_y, _pv_size_y),
            doc='ROI position and size in XY',
            kind='normal',
        )

        _attr = f'stats{i}'
        _attr_total = f'total'
        _pv_total = f'{i}:Total_RBV'
        _attr_max = f'max_value'
        _pv_max = f'{i}:MaxValue_RBV'
        vars()[_attr] = DDC_EpicsSignalRO(
            (_attr_total, _pv_total),
            (_attr_max, _pv_max),
            doc='ROI stats',
            kind='normal',
        )



class PilatusBase(SingleTriggerV33, PilatusDetectorCam):
    roi1 = Cpt(ROIPlugin, 'ROI1:')
    roi2 = Cpt(ROIPlugin, 'ROI2:')
    roi3 = Cpt(ROIPlugin, 'ROI3:')
    roi4 = Cpt(ROIPlugin, 'ROI4:')

    stats1 = Cpt(StatsPluginV33, 'Stats1:', read_attrs=['total', 'max_value'])
    stats2 = Cpt(StatsPluginV33, 'Stats2:', read_attrs=['total'])
    stats3 = Cpt(StatsPluginV33, 'Stats3:', read_attrs=['total'])
    stats4 = Cpt(StatsPluginV33, 'Stats4:', read_attrs=['total'])
    image = Cpt(ImagePlugin_V33, 'image1:')

    roistat = Cpt(ISSROIStatPlugin, 'ROIStat1:')
    # roistat = Cpt(ROIStatPlugin_V34, 'ROIStat1:')

    over1 = Cpt(OverlayPlugin, 'Over1:')

    readout = 0.0025 # seconds; actually it is 0.0023, but we are conservative

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hint_channels()
        # self._is_flying = False

    def hint_channels(self):
        self.stats1.kind = 'hinted'
        self.stats1.total.kind = 'hinted'
        self.stats2.kind = 'hinted'
        self.stats2.total.kind = 'hinted'
        self.stats3.kind = 'hinted'
        self.stats3.total.kind = 'hinted'
        self.stats4.kind = 'hinted'
        self.stats4.total.kind = 'hinted'

    def read_exposure_time(self):
        return self.cam.acquire_period.get()

    def set_exposure_time(self, exp_t):
        self.cam.acquire_time.put(np.floor((exp_t - self.readout) * 1000) / 1000)
        self.cam.acquire_period.put(exp_t)

    def set_num_images(self, num):
        self.cam.num_images.put(num)
        self.hdf5.num_capture.put(num)

    # def det_next_file(self, n):
    #     self.cam.file_number.put(n)

    def enforce_roi_match_between_plugins(self):
        for i in range(1,5):
            _attr = getattr(self, f'roi{i}')
            _x = _attr.min_xyz.min_x.get()
            _y = _attr.min_xyz.min_y.get()
            _xs = _attr.size.x.get()
            _ys = _attr.size.y.get()
            _attr2 = getattr(self.roistat, f'roi{i}')
            _attr2.min_x.set(_x)
            _attr2.min_y.set(_y)
            _attr2.size_x.set(_xs)
            _attr2.size_y.set(_ys)

    def stage(self):
        self.enforce_roi_match_between_plugins()
        return super().stage()

    def get_roi_coords(self, roi_num):
        x = getattr(self, f'roi{roi_num}').min_xyz.min_x.get()
        y = getattr(self, f'roi{roi_num}').min_xyz.min_y.get()
        dx = getattr(self, f'roi{roi_num}').size.x.get()
        dy = getattr(self, f'roi{roi_num}').size.y.get()
        return x, y, dx, dy

    @property
    def roi_metadata(self):
        md = {}
        key_table = {'x': 'min_x',
                     'dx': 'size_x',
                     'y': 'min_y',
                     'dy': 'size_y'}
        for i in range(1, 5):
            k_roi = f'roi{i}'
            roi_md = {}
            for k_md, k_epics in key_table.items():
                roi_md[k_md] = getattr(self.roistat, f'{k_roi}.{k_epics}').value
            md[k_roi] = roi_md
        return md

    def read_config_metadata(self):
        md = {}
        md['device_name'] = self.name
        md['roi'] = self.roi_metadata
        return md

    # @property
    # def is_flying(self):
    #     return self._is_flying
    #
    # @is_flying.setter
    # def is_flying(self, is_flying):
    #     self._is_flying = is_flying








class PilatusHDF5(PilatusBase):
    hdf5 = Cpt(HDF5PluginWithFileStore,
               suffix='HDF1:',
               root='/',
               write_path_template=f'{ROOT_PATH}/{RAW_PATH}/pil100k/%Y/%m/%d')#,
               # write_path_template=f'/nsls2/xf08id/data/pil100k/%Y/%m/%d')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_primary_roi(1)
        # self.set_primary_roi(2)
        # self.set_primary_roi(3)
        # self.set_primary_roi(4)

    def set_primary_roi(self, num):
        st = f'stats{num}'
        # self.read_attrs = [st, 'tiff']
        self.read_attrs = [st, 'hdf5']
        getattr(self, st).kind = 'hinted'


class PilatusStreamHDF5(PilatusHDF5):

    def __init__(self, *args, ext_trigger_device=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ext_trigger_device = ext_trigger_device
        self._asset_docs_cache = deque()
        self._datum_counter = None


        self.datum_keys = [{"data_type": "image", "roi_num" : 0}]
        for i in range(4):
            self.datum_keys.append({"data_type" : "roi",
                                    "roi_num" : i + 1})

    def format_datum_key(self, input_dict):
        output =f'pil100k_{input_dict["data_type"]}'
        if input_dict["data_type"] == 'roi':
            output += f'{input_dict["roi_num"]:01d}'
        return output

    def prepare_to_fly(self, traj_duration):
        self.acq_rate = self.ext_trigger_device.freq.get()
        self.num_points = int(self.acq_rate * (traj_duration + 1))
        self.ext_trigger_device.prepare_to_fly(traj_duration)


    # TODO: change blocking to NO upon staging of this class !!!
    def stage(self):
        staged_list = super().stage()
        self._datum_counter = itertools.count()
        # self.is_flying = True
        self.hdf5._asset_docs_cache[0][1]['spec'] = 'PIL100k_HDF5'  # This is to make the files to go to correct handler
        self.hdf5._asset_docs_cache[0][1]['resource_kwargs'] = {}  # This is to make the files to go to correct handler

        self.set_num_images(self.num_points)
        self.set_exposure_time(1 / self.acq_rate)
        self.cam.array_counter.put(0)
        self.cam.trigger_mode.put(3)
        self.cam.image_mode.put(1)

        # self.hdf5.blocking_callbacks.put(1)

        staged_list += self.ext_trigger_device.stage()
        return staged_list

    def unstage(self):
        self._datum_counter = None

        unstaged_list = super().unstage()
        self.cam.trigger_mode.put(0)
        self.cam.image_mode.put(0)
        self.set_num_images(1)
        self.set_exposure_time(1)
        # self.hdf5.blocking_callbacks.put(0)
        unstaged_list += self.ext_trigger_device.unstage()
        return unstaged_list

    def kickoff(self):
        self.cam.acquire.set(1).wait()
        return self.ext_trigger_device.kickoff()

    def complete(self):
        print_to_gui(f'Pilatus100k complete is starting...', add_timestamp=True)
        acquire_status = self.cam.acquire.set(0)
        capture_status = self.hdf5.capture.set(0)
        (acquire_status and capture_status).wait()

        ext_trigger_status = self.ext_trigger_device.complete()
        for resource in self.hdf5._asset_docs_cache:
            self._asset_docs_cache.append(('resource', resource[1]))
        self._datum_ids = []
        # num_frames = self.hdf5.num_captured.get()
        _resource_uid = self.hdf5._resource_uid
        self._datum_ids = {}

        for datum_key_dict in self.datum_keys:
            datum_key = self.format_datum_key(datum_key_dict)
            datum_id = f'{_resource_uid}/{datum_key}'
            self._datum_ids[datum_key] = datum_id
            doc = {'resource': _resource_uid,
                    'datum_id': datum_id,
                    'datum_kwargs': datum_key_dict}
            self._asset_docs_cache.append(('datum', doc))

        # datum_kwargs = [{'frame': i} for i in range(num_frames)]
        # doc = compose_bulk_datum(resource_uid=_resource_uid,
        #                          counter=self._datum_counter,
        #                          datum_kwargs=datum_kwargs)
        # self._asset_docs_cache.append(('bulk_datum', doc))
        # _datum_id_counter = itertools.count()
        # for frame_num in range(num_frames):
        #     datum_id = '{}/{}'.format(_resource_uid, next(_datum_id_counter))
        #     self._datum_ids.append(datum_id)

        print_to_gui(f'Pilatus100k complete is done.', add_timestamp=True)
        return NullStatus() and ext_trigger_status


    def collect(self):
        print_to_gui(f'Pilatus100k collect is starting...', add_timestamp=True)
        ts = ttime.time()
        yield {'data': self._datum_ids,
               'timestamps': {self.format_datum_key(key_dict): ts for key_dict in self.datum_keys},
               'time': ts,  # TODO: use the proper timestamps from the mono start and stop times
               'filled': {self.format_datum_key(key_dict): False for key_dict in self.datum_keys}}

        # num_frames = len(self._datum_ids)
        #
        # for frame_num in range(num_frames):
        #     datum_id = self._datum_ids[frame_num]
        #     data = {self.name: datum_id}
        #
        #     ts = ttime.time()
        #
        #     yield {'data': data,
        #            'timestamps': {key: ts for key in data},
        #            'time': ts,  # TODO: use the proper timestamps from the mono start and stop times
        #            'filled': {key: False for key in data}}
        print_to_gui(f'Pilatus100k collect is complete', add_timestamp=True)
        yield from self.ext_trigger_device.collect()

    def describe_collect(self):
        pil100k_spectra_dicts = {}
        for datum_key_dict in self.datum_keys:
            datum_key = self.format_datum_key(datum_key_dict)
            if datum_key_dict['data_type'] == 'image':
                value = {'source': 'PIL100k_HDF5',
                         'dtype': 'array',
                         # 'shape': [self.cam.num_images.get(),
                         'shape': [self.hdf5.num_capture.get(),
                                   self.hdf5.array_size.height.get(),
                                   self.hdf5.array_size.width.get()],
                         'dims': ['frames', 'row', 'col'],
                         'external': 'FILESTORE:'}
            elif datum_key_dict['data_type'] == 'roi':
                value = {'source': 'PIL100k_HDF5',
                         'dtype': 'array',
                         # 'shape': [self.cam.num_images.get()],
                         'shape': [self.hdf5.num_capture.get()],
                         'dims': ['frames'],
                         'external': 'FILESTORE:'}
            else:
                raise KeyError(f'data_type={datum_key_dict["data_type"]} not supported')
            pil100k_spectra_dicts[datum_key] = value

        return_dict_pil100k = {self.name: pil100k_spectra_dicts}

        # return_dict_pil100k = {self.name:
        #                    {f'{self.name}': {'source': 'PIL100k_HDF5',
        #                                      'dtype': 'array',
        #                                      'shape': [self.cam.num_images.get(),
        #                                                #self.settings.array_counter.get()
        #                                                self.hdf5.array_size.height.get(),
        #                                                self.hdf5.array_size.width.get()],
        #                                     'filename': f'{self.hdf5.full_file_name.get()}',
        #                                      'external': 'FILESTORE:'}}}
        #
        return_dict_trig = self.ext_trigger_device.describe_collect()
        return {**return_dict_pil100k, **return_dict_trig}

    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item
        yield from self.ext_trigger_device.collect_asset_docs()




    # def set_expected_number_of_points(self, acq_rate, traj_time):



pil100k = PilatusHDF5("XF:08IDB-ES{Det:PIL1}:", name="pil100k")  # , detector_id="SAXS")
pil100k_stream = PilatusStreamHDF5("XF:08IDB-ES{Det:PIL1}:", name="pil100k_stream", ext_trigger_device=apb_trigger_pil100k)

pil100k.set_primary_roi(1)
pil100k.stats1.kind = 'hinted'
pil100k.stats2.kind = 'hinted'
pil100k.stats3.kind = 'hinted'
pil100k.stats4.kind = 'hinted'



# pil100k.cam.ensure_nonblocking()

def take_pil100k_test_image_plan():
    yield from shutter.open_plan()
    pil100k.cam.acquire.set(1)
    yield from bps.sleep(pil100k.cam.acquire_time.value + 0.1)
    yield from shutter.close_plan()


def pil_count(acq_time:int = 1, num_frames:int =1, open_shutter:bool=True):
    if open_shutter: yield from shutter.open_plan()
    yield from bp.count([pil100k, apb_ave])
    if open_shutter: yield from shutter.close_plan()



from itertools import product
import pandas as pd
from databroker.assets.handlers import HandlerBase, PilatusCBFHandler, AreaDetectorTiffHandler, Xspress3HDF5Handler





# PIL100k_HDF_DATA_KEY = 'entry/instrument/NDAttributes'
# class ISSPilatusHDF5Handler(Xspress3HDF5Handler): # Denis: I used Xspress3HDF5Handler as basis since it has all the basic functionality and I more or less understand how it works
#     specs = {'PIL100k_HDF5'} | HandlerBase.specs
#     HANDLER_NAME = 'PIL100k_HDF5'
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, key=PIL100k_HDF_DATA_KEY, **kwargs)
#         self._roi_data = None
#         self.hdfrois = [f'ROI{i + 1}' for i in range(4)]
#         self.chanrois = [f'pil100k_ROI{i + 1}' for i in range(4)]
#
#
#     def _get_dataset(self):
#         if self._dataset is not None:
#             return
#
#         _data_columns = [self._file[self._key + f'/_{chanroi}Total'][()] for chanroi in self.hdfrois]
#         self._roi_data = np.vstack(_data_columns).T
#         self._image_data = self._file['entry/data/data'][()]
#         # self._roi_data = pd.DataFrame(data_columns, columns=self.chanrois)
#         # self._dataset = data_columns
#
#     def __call__(self, data_type:str='image', roi_num=None):
#         # print(f'{ttime.ctime()} XS dataset retrieving starting...')
#         self._get_dataset()
#
#         if data_type=='image':
#             # print(output.shape, output.squeeze().shape)
#             return self._image_data
#
#         elif data_type=='roi':
#             return self._roi_data[:, roi_num - 1].squeeze()
#
#         else:
#             raise KeyError(f'data_type={data_type} not supported')

    # def __call__(self, *args, frame=None,  **kwargs):
    #     self._get_dataset()
    #     return_dict = {chanroi: self._roi_data[chanroi][frame] for chanroi in self.chanrois}
    #     # return_dict['image'] = self._image_data[frame, :, :].squeeze()
    #     return return_dict
    #     # return self._roi_data


# from xas.handlers import ISSPilatusHDF5Handler
# db.reg.register_handler('PIL100k_HDF5',
#                          ISSPilatusHDF5Handler, overwrite=True)

