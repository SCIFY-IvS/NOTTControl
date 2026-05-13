import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from time import sleep, time
from tqdm import tqdm
from copy import copy
from datetime import datetime,timedelta,timezone
from xaosim.shmlib import shm
from scipy.linalg import hadamard

import sys
sys.path.append("/home/labo/src/NOTTControl/")
sys.path.append("/home/labo/src/NOTTControl/script/lib/")

dburl = "redis://nott-server.ster.kuleuven.be:6379"

x_filter = np.array([0.000003332231310433949, 0.000003359090941083894, 0.0000033818181178322115, 0.0000033962809146615277, 0.000003416942128401158, 0.000003431404925230474, 0.0000034438015830896854, 0.0000034561982409488967, 0.000003474793315718422, 0.0000034975206684281573, 0.0000035285124010568945, 0.0000035574379947155264, 0.000003604958663143684, 0.000003640082497751213, 0.000003664875989431053, 0.0000037082643799190013, 0.000003741322251517843, 0.000003784710642005791, 0.000003823966930514947, 0.0000038528925241735795, 0.000003919008091409845, 0.000003943801583089685, 0.000003966528759838003, 0.000003978925593658632, 0.000003989256112547738, 0.0000040037189093770535, 0.00000401404942826616, 0.000004032644503035686, 0.000004047107299865002, 0.0000040760328935236335, 0.0000042206610377782125])
y_filter = np.array([0.0017543387818981376, 0.004561388410207326, 0.014385942578987246, 0.036842100544856524, 0.2277192639592904, 0.45789470381399533, 0.6599999760939395, 0.7863157750042266, 0.8508771992735247, 0.8705263076110844, 0.9028070197457336, 0.89017544583122, 0.8873684260854863, 0.9056140394914672, 0.9014035098728668, 0.8410526451047448, 0.8410526451047448, 0.8621052782564592, 0.916842103533114, 0.9210526331517145, 0.8957894703813994, 0.8957894703813994, 0.9028070197457336, 0.8803508916624401, 0.7975438539871611, 0.4761403471025518, 0.2726315201258773, 0.07473679240582154, 0.028420951659928514, 0.005964793694059473, 0.0017543387818981376])
mean_wl = np.sum(x_filter*y_filter) / np.sum(y_filter)

from nottcontrol.opcua import OPCUAConnection
from nottcontrol.components.shutter import Shutter
from nottcontrol.camera.frame import Frame
from nottcontrol.lucid.lib.lucid_utils import LucidUtils
from nottcontrol.script.lib.nott_database import get_field
from configparser import ConfigParser
from nottcontrol import config 

opcuad = config["DEFAULT"]["opcuaaddress"]

# Time stamping functions

def unix_to_datetime(unix_stamp):
    # Converting unix_stamp (milliseconds since 01/01/1970 00:00:00) to a datetime object (time in UTC)
    epoch = datetime.fromtimestamp(0,timezone.utc)
    dt = timedelta(milliseconds=unix_stamp)
    utc_stamp = epoch + dt
    return utc_stamp

def datetime_to_id(utc_stamp):
    # Converting datetime object utc_stamp to frame_id (Y%m%d_H%M%S formatted string, date and time separated by an underscore)
    Ymd = utc_stamp.strftime("%Y%m%d")
    HMS = utc_stamp.strftime("%H%M%S%f")[:-3]
    frame_id = Ymd+"_"+HMS
    return frame_id

# Classes for transfer to shm object, wrapping shmlib.py

class RollingShm(object):
    def __init__(self, fname="/dev/shm/rtdisp/default.plt.shm",
                    depth=10, width=8, dim=None):
        """
        Dimension "depth" should be set to span the amount of entries that are simultaneously kept in the buffer.
        Dimensions "width" and "dim" should be set depending on the use case, i.e. what data is transferred. Examples include:
            - To offer separate plotting of the dispersed readout of each output (ROI), set "width" to an amount of ROIs and "dim" to "nwls", an amount of wavelength bins.
            - To offer a waterfall plot of dispersed readouts instead, leave "dim" as None and reshape "width" to # ROIs * nwls
            - To offer errors with passed values (flux/null), set "dim" to 2; index 0 of dimension "dim" will then be the value, index 1 its error.
            Note: Currently not supporting transferring errors for separated dispersed readout, as this would constitute a 4D (# readouts, # ROIs, # wls, 2) array (not supported by shmlib)
                  Passing such dataframes by two buffers instead (see disp_initialize)
            TBD: Alternatively, could double the size of the # wls dimension to include both the value and error (wl1, wl1_err, ..., wlN, wlN_err)
            - ...
        """
        if dim is None:
            self.shape = (depth, width)
        else:
            self.shape = (depth, dim, width)
        self.buffer = np.zeros(shape=self.shape, dtype=float)
        self.shm = shm(fname, data=self.buffer, verbose=False,)


    def get_data(self, *args, **kwargs):
        """
            Loads data from the shm object
        """
        self.buffer = self.shm.get_data(*args, **kwargs)
        return self.buffer

    def push(self, data):
        """
            Push new data at the back of the buffer, then
        writes to the shm. The oldest data is erased.
        """
        self.buffer = np.roll(self.buffer, -1, axis=0)
        self.buffer[-1] = data
        self.shm.set_data(self.buffer)

    def close(self):
        """
            Is used to remove the shm
        """
        self.shm.close()

class SimpleShm(object):
    def __init__(self, fname="/dev/shm/rtdisp/default.plt.shm",
                    shape=None, dtype=float):
        """
        Non-rolling, simple shm. Shape should be set depending on the use case.
        """
        if shape is None:
            shape = (10,10)
        self.shape = shape
        self.buffer = np.zeros(shape=self.shape, dtype=dtype)
        self.shm = shm(fname, data=self.buffer, verbose=False,)


    def get_data(self, *args, **kwargs):
        """
            Loads data from the shm object
        """
        self.buffer = self.shm.get_data(*args, **kwargs)
        return self.buffer

    def push(self, data):
        """
            This is not a rolling buffer, so just set the data
        """

        self.shm.set_data(data)

    def close(self):
        """
            Is used to remove the shm
        """
        self.shm.close()

# Functions to construct probes:


def full_hadamard_probe(ntel, amp, steps=5, bidir=False):
    mod_shutters = shutter_probe(ntel)
    base_probe = hadamard_modulation(ntel, amp)
    grad_probe = graduify(base_probe, steps, bidir=bidir)
    return mod_shutters, grad_probe


def hadamard_modulation(ntel, amp, drop_common=True):
    """
    Returns a hadamard matrix of given
    """
    mat = hadamard(4)
    if drop_common:
        mat = mat[1:,:]
    return mat*amp


def shutter_probe(ntel):
    mod_shutters = np.eye(ntel+1, ntel)
    mod_shutters = np.roll(mod_shutters, 1, axis=0)
    return mod_shutters


def graduify(matrix, nsteps, bidir=False, append_zeros=0):
    if bidir:
        multipliers = np.linspace(-1, 1, nsteps)
    else:
        multipliers = np.linspace(0, 1, nsteps)
    newrows = []
    for arow in matrix:
        for amult in multipliers:
            newrow = amult * arow
            newrows.append(newrow)
    return np.array(newrows)


def randomized_probe(n, ntel=4, scale=1.0e-6, func=np.random.normal):
    mat = func(size=(n, ntel), scale=scale)
    return mat


class HumInt(object):
    def __init__(self, lam_mean=mean_wl,
                pad=0.15,
                shutter_pad=5.5,
                interf=None,
                act_index=0,
                non_motorized=0,
                nb_beams=4,
                offset=8.0,
                db_server=None,
                rois_interest=np.arange(1,10),
                opcuad=opcuad,
                snr_thresh=5,
                verbose=False):
        # self.lamb_min = lam_range[0]
        # self.lamb_max = lam_range[-1]
        self.lam_mean = lam_mean
        self.pad = pad
        self.shutter_pad = shutter_pad
        self.interf = interf
        self.act_index = act_index
        self.non_motorized = non_motorized # Index of the non-motorized beam
        self.nb_beams = nb_beams
        self.offset = offset * np.ones(self.nb_beams)
        self.offset[self.non_motorized] = 0
        self.ts = db_server
        self.rois_old = [f"roi{n}_sum" for n in rois_interest]
        self.rois = rois_interest
        self.dark = None
        self.bg_noise = None
        self.opcua_conn = OPCUAConnection(opcuad)
        self.opcua_conn.connect()
        self.shutters = [
            Shutter(self.opcua_conn,
                f"ns=4;s=MAIN.nott_ics.Shutters.NSH{shutterid+1}",
                f"NSH{shutterid+1}",
                speed=15.0*1e3,
                open_pos=5.0,
                close_pos=35.0)\
             for shutterid in range(4)
        ]
        self.frame_VIS_pup = None
        self.frame_VIS_im = None

        # Getting link between outputs and ROI indices from config
        channel_labels = config.getarray('CAMERA', 'channel_labels', str)
        roi_indices = config.getarray('CAMERA', 'roi_indices', np.int32)
        self.channel_roi_link = dict(zip(channel_labels,roi_indices))
        
        self.move(np.array([0., 0., 0., 0.]))
        self.auto_display = False

        self.disp_roi_mask = np.ones(self.rois.shape, dtype=bool)
        self.disp_waterfall_broad = False,
        self.disp_waterfall_dispersed = False
        self.disp_depth = 30
        self.disp_calls = []
        
    #---------------------#
    # Auxiliary functions |
    # --------------------#
    
    def __del__(self):
        self.opcua_conn.disconnect()
        if hasattr(self, "buffer_im_IR"):
            self.buffer_im_IR.close()
        if hasattr(self, "buffer_im_VIS_pup"):
            self.buffer_im_VIS_pup.close()
        if hasattr(self, "buffer_im_VIS_im"):
            self.buffer_im_VIS_im.close()
        if hasattr(self, "buffer_broad"):
            self.buffer_broad.close()
        if hasattr(self, "buffer_broad_null"):
            self.buffer_broad_null.close()
        if hasattr(self, "buffer_disp"):
            self.buffer_disp.close()
        if hasattr(self, "buffer_disp_err"):
            self.buffer_disp_err.close()
        if hasattr(self, "buffer_disp_last"):
            self.buffer_disp_last.close()
        if hasattr(self, "buffer_disp_null"):
            self.buffer_disp_null.close()
        if hasattr(self, "buffer_disp_null_err"):
            self.buffer_disp_null_err.close()
        if hasattr(self, "buffer_disp_null_last"):
            self.buffer_disp_null_last.close()

    # Initialization of shm buffers

    def disp_initialize_shm_IR_cam(self):
        """
        Function that initializes a buffer for real-time transfer (shm) and display (shmview) of IR & visible camera images.
            - buffer_im_IR; (IR frame shape); Infrared camera view of the latest readout. 
        """
        self.buffer_im_IR = SimpleShm("/dev/shm/rtdisp/nott_window.im.shm",
                                        shape=self.dark.master_full[0].shape)
        
    def disp_initialize_shm_VIS_cam(self):
        """
        Function that initializes a buffer for real-time transfer (shm) and display (shmview) of IR & visible camera images.
            - buffer_im_VIS_pup; (VIS pupil frame shape); Pupil plane visible camera view of the latest readout.
            - buffer_im_VIS_im; (VIS image frame shape); Image plane visible camera view of the latest readout. 
        """
        # Snapping camera views
        with LucidUtils() as myut:
            frame_pup = self.get_pupil_view(ut=myut, refresh=True)
            frame_im = self.get_image_view(ut=myut, refresh=True)
         
        self.buffer_im_VIS_pup = SimpleShm("/dev/shm/rtdisp/vis_cam_pupil.im.shm",
                                        shape=self.frame_VIS_pup.shape, dtype=frame_pup.dtype)
        self.buffer_im_VIS_im = SimpleShm("/dev/shm/rtdisp/vis_cam_image.im.shm",
                                        shape=self.frame_VIS_im.shape, dtype=frame_im.dtype)

    def disp_initialize_shm_broadband(self, depth=30, width=None):
        """
        Function that initializes buffers for real-time transfer (shm) and display (shmview) of broadband data, deduced from the ROIs defined on the IR camera frame.
            - buffer_broad; (depth, 2, width); Broadband flux and error in selected ROIs (# ROIs = "width"), for the latest "depth" amount of readouts.
            - buffer_broad_null; (depth, 2, 3); Broadband null depths (N2, N3, Ndiff) and errors, for the latest "depth" amount of readouts.
        
        """
        if width is None:
            width = np.count_nonzero(self.disp_roi_mask)
        dummy_data = np.nan * np.zeros((depth, width, 2), dtype=float)
        self.buffer_broad = RollingShm("/dev/shm/rtdisp/nott_buffer_broad.im.shm",
                                        depth=depth, width=width, dim=2)

        dummy_data_null = np.nan * np.zeros((depth, 3, 2), dtype=float)
        self.buffer_broad_null = RollingShm("/dev/shm/rtdisp/nott_buffer_broad_null.im.shm",
                                        depth=depth, width=3, dim=2)

    def disp_initialize_shm_dispersed(self, depth=30, width=None,
                                        nwls=None):
        """
        Function that initializes buffers for real-time transfer (shm) and display (shmview) of dispersed data, deduced from the ROIs defined on the IR camera frame.
                buffer name           buffer dim.          buffer content
            - buffer_disp; (depth, 2, width*nwls); Dispersed flux and errors in selected ROIs, for the latest "depth" amount of readouts. Waterfall style, ROIs and wavelengths are glued together ("width" = # ROIs * nwls) 
            - buffer_disp_null(_err); (depth, nwls, 3);  Dispersed null depths (N2, N3, Ndiff) and errors, for the latest "depth" amount of readouts.
            - buffer_disp_last; (width, nwls); Buffer to store and visualize latest entry of buffer_disp
            - buffer_disp_null_last; (3, nwls);  Buffer to store and visualize latest entry of buffer_disp_null
        """
        if width is None:
            width = np.count_nonzero(self.disp_roi_mask)
        if nwls is None:
            nwls = np.count_nonzero(self.sc_mask)
        initial_shape = (depth, width, nwls)
        dummy_raw = np.nan * np.zeros(initial_shape, dtype=float)
        dummy_data_reshaped = dummy_raw.reshape(depth, width * nwls, 2)
        self.buffer_disp = RollingShm("/dev/shm/rtdisp/nott_buffer_disp.im.shm",
                                        depth=dummy_data_reshaped.shape[0],
                                        width=dummy_data_reshaped.shape[1],
                                        dim=dummy_data_reshaped.shape[2])

        # To be added: buffer to pass ROI-specific flux values and errors
        
        null_shape = (depth, 3, nwls)
        dummy_data_null = np.nan * np.zeros(null_shape, dtype=float)
        dummy_data_null_err = np.nan * np.zeros(null_shape, dtype=float)
        self.buffer_disp_null = RollingShm("/dev/shm/rtdisp/nott_buffer_disp_null.im.shm",
                                        depth=null_shape[0], width=null_shape[1], dim=null_shape[2])
        self.buffer_disp_null_err = RollingShm("/dev/shm/rtdisp/nott_buffer_disp_null_err.im.shm",
                                        depth=null_shape[0], width=null_shape[1], dim=null_shape[2])

        # Buffers with latest entries
        self.buffer_disp_last = SimpleShm("/dev/shm/rtdisp/nott_buffer_disp_last.im.shm", shape=(width,nwls))
        self.buffer_disp_null_last = SimpleShm("/dev/shm/rtdisp/nott_buffer_null_last.im.shm", shape=(3,nwls))
        
        spacers = nwls * np.arange(width+1)
        np.save("/dev/shm/spacers.npy", spacers)

    # Wavelength calibration

    def solve_spectral_cal_linear(self):
        """
            This simple spectral calibration writes to `self.lambs` the 
        wavelength value [m] of each roi pixel. Relies on `low_lamb` ...
        `low_index` ... from config file. This method creates a *linear*
        range based on these values for basic correspondance to pixels.
            Also creates a mask corresponding to the science wavelengths.
        """
        lamb_low =   config.config_parser.getfloat("CAMERA","low_lamb")
        lamb_high =  config.config_parser.getfloat("CAMERA","up_lamb")
        index_low =  config.config_parser.getfloat("CAMERA","low_index")
        index_high = config.config_parser.getfloat("CAMERA","up_index")
        roi_len = int(round(config.getarray("CAMERA","ROI 1")[3]))
        lamb_per_pix = (lamb_high-lamb_low) / (index_high - index_low)
        lamb_0 = lamb_low - index_low * lamb_per_pix
        lamb_max = lamb_0 + roi_len * lamb_per_pix
        calibration = np.linspace( lamb_0, lamb_max, roi_len)
        self.lambs = 1.0e-6 * calibration
        self.sc_mask = np.logical_and(self.lambs >= 1.0e-6 * lamb_low,
                                            self.lambs <= 1.0e-6 * lamb_high)

    @property
    def sc_lambs(self):
        """
            This is the array of wavelengths limited to the science mask.
        """
        return self.lambs[self.sc_mask]

    # Time stamping

    def db_time(self):
        aresp = self.ts.ts.get(f"cam_integtime")
        return aresp[0]

    # Piezo control

    def four2three(self, position):
        return position - position[self.non_motorized]

    def deltaval2p(self, deltaval, frac, amp=800.):
        lam_micron = 1.0e6 * self.lam_mean
        deltap = lam_micron * frac
        inner = -deltaval / (amp * 2 * np.sin(2*np.pi/lam_micron * deltap))
        p = lam_micron /(2*np.pi) * np.arcsin(inner)
        return p

    #---------------------------#
    # Shutter control functions |
    # --------------------------#
    
    class ShutterError(OSError):
        pass
    
    @property
    def shutter_state(self):
        
        # Shutters' (treated like motors) status
        motor_status = np.array([ashutter.getStatusInformation()[0] for ashutter in self.shutters])
        standing = (motor_status == 'STANDING')

        shutter_state = np.zeros(len(self.shutters),dtype=np.int32)
        for i, ashutter in enumerate(self.shutters):
            # Throw error if a shutter is still moving.
            if not standing[i]:
                raise self.ShutterError("Shutter " + str(ashutter.name) + " is still moving.")
            # Throw error if a shutter is neither moving, neither standing still in an open/closed position. 
            if not (ashutter.is_open or ashutter.is_closed):
                raise self.ShutterError("Shutter " + str(ashutter.name) + " is neither moving, nor in an open/closed position.")
            if ashutter.is_open:
                shutter_state[i] = 1
        return shutter_state
    
    def shutter_set(self, values, wait=True, verbose=False):
        
        # Shutters state on motor level : operational?
        motor_state = np.array([ashutter.getStatusInformation()[1] for ashutter in self.shutters])
        operational = (motor_state == 'OPERATIONAL')
        
        # Shutter state on surface level : open/closed?
        shutter_state = self.shutter_state
        # Input shutter state
        if not isinstance(values, np.ndarray):
            thevalues = np.array(values)
        else:
            thevalues = values
        shutter_change = np.invert(shutter_state == thevalues)
            
        for i, ashutter in enumerate(self.shutters):
            # Throw error if a shutter is not operational.
            if not operational[i]:
                raise self.ShutterError("Shutter " + str(ashutter.name) + " is not in operational state.")
            values_bool = thevalues.astype(bool)
            # Only move if current and input state differ
            if shutter_change[i]:
                if values_bool[i]:
                    ashutter.open()
                else:
                    ashutter.close()
        if wait and shutter_change.any():
            sleep(self.shutter_pad)
        if verbose:
            for i, ashutter in enumerate(self.shutters):
                print(i, ashutter.getStatusInformation()[1], ashutter.getPositionAndSpeed()[0])

    #------------------------------#
    # Delay line control functions |
    # -----------------------------#

    # WIP

    #-------------------------#
    # Piezo control functions |
    #-------------------------#

    def get_position(self):
        pos = self.interf.values.copy()
        pos -= self.offset
        return pos

    def move(self, position ):
        # print(f"moving to {position:.3e}")
        values = self.four2three(position) + self.offset
        self.interf.send(any_values=values)

    def relative_move(self, motion):
        thepos = self.get_position()
        thepos[self.act_index] += motion 
        self.interf.send(any_values=thepos)

    #--------------------------------------#
    # Visible camera interfacing functions |
    # -------------------------------------#
    
    # WIP

    def get_image_view(self, ut=None, refresh=False):
        if ut is None:
            with LucidUtils() as ut:
                frame_im = ut.snap("im_cam")
        else:
            frame_im = ut.snap("im_cam")

        if refresh:
            self.frame_VIS_im = frame_im
        return frame_im

    def get_pupil_view(self, ut=None, refresh=False):
        if ut is None:
            with LucidUtils() as ut:
                frame_pup = ut.snap("pup_cam")
        else:
            frame_pup = ut.snap("pup_cam")
            
        if refresh:
            self.frame_VIS_pup = frame_pup
        return frame_pup

    def configure_vis_cam_readout(self, name, params):
        with LucidUtils() as ut:
            ut.configure_camera_readout(name, params)
            if name == "im_cam":
                _ = self.get_image_view(ut, True)
            elif name == "pup_cam":
                _ = self.get_pupil_view(ut, True)

        # WIP: Upon change of camera pixelformat/datatype, refresh VIS_cam buffer dtypes
        #      and find a way to propagate the new dtype to the shm level (see shmlib methods)

    def configure_vis_cam_stream(self, name, params):
        with LucidUtils() as ut:
            ut.configure_camera_stream(name, params)

    def push_to_shm(self, name, frame):
        # Callback function passed to lucid_utils.start_thread() for visible camera streaming

        # WIP

        # Based on camera name {name}, push the frame data {frame} to the right buffer.
        # return nothing
        return
        

    def start_stream_vis_cam(self, name, ut):
        # Visible camera streaming, on camera {name}

        # WIP

        # Pass ut as parameter so you can call stop_streaming_callback on it from outside!!
        # 1) Create a thread, passing the camera name and above callback function
        # 2) Deprecate w,h in start_thread
        # 3) Complete documentation: "call stop_streaming_callback" to stop the stream. Or wrap it in a method, your call.
        # 4) ! Note: the callback function, passed to start_thread and thus called "inside lucid_utils", remembers where it comes from - where it is defined (here).
        # hence you can call functions/fields/whatever defined in this script on it.
        return

    #------------------#
    # Sample functions |
    # -----------------#

    def sample(self):
        mes = np.array([self.ts.ts.get(akey) for akey in self.rois])
        return mes.T[1]

    def sample_cal(self):
        return self.sample() - self.dark

    def sample_long(self, dt=1.0):
        # start = int(np.round(time()*1000).astype(int))
        start = self.db_time()
        sleep(dt)
        # end = int(np.round(time()*1000).astype(int))
        end = self.db_time()
        mes = np.array([self.ts.ts.range(akey, start, end) for akey in self.rois])
        return mes.T[1]

    def sample_long_cal(self, dt):
        return self.sample_long(dt=dt) - self.dark

    def move_and_sample(self, position, dt=None, move_back=True, dark=None):
        if dark is None:
            dark = self.dark
        orig_pos = self.get_position()
        self.move(position)
        sleep(self.pad)
        if dt is None:
            raise ValueError("single frames are no longer supported")
            # res = self.sample_cal()
        else:
            # res = self.sample_long_cal(dt)
            cal_disp_stack, cal_broad_stack = self.get_frames_cal(dt=dt, dark=dark, sequence=False)
            res, std = cal_disp_stack[0], cal_disp_stack[1]
        if move_back:
            print(f"moving_back to {orig_pos}")
            self.move(orig_pos)
            sleep(self.pad)
        return res, std

    #-----------------------------#
    # Image calibration functions |
    #-----------------------------#

    def get_dark(self, dt):
        print("Taking darks")
        measurement = self.sample_long(dt=dt)
        self.dark = measurement.mean(axis=0)
        self.bg_noise = measurement.std(axis=0)/np.sqrt(measurement.shape[0])
        print("You can remove the shutters")

    def get_frames(self,dt):
        # Timespan dt in seconds
        
        # db_time returns stamps in unix_time_ms since 01/01/1970 00:00:00, as registered in redis
        start = self.db_time()
        sleep(dt)
        end = self.db_time()
        # Fetching (timestamp,integration time) pairs, for each camera frame captured in this timeframe dt, from redis.
        pairs = get_field("cam_integtime", start, end, False)
        # Fetching InfraTec timestamps registered in this timeframe        
        unix_stamps = pairs[:,0]
        ids = []
        for unix_stamp in unix_stamps:
            utc_stamp = unix_to_datetime(unix_stamp)
            frame_id = datetime_to_id(utc_stamp)
            ids.append(frame_id)
        # Fetching integration time, as registered in redis for each frame
        integtimes = pairs[:,1] # microseconds
        # Creating a Frame object by given ids
        frames = Frame(ids, integtimes)
        
        return frames

    def frame_sequence(self, dt, shutter_state=None, verbose=False):
        """
        Identical to get_frames but adding shutter control.
        Brings the shutters to given shutter_state (if not None), takes frames in that state, brings shutters back to initial state.
        """
        if shutter_state is None:
            frames = self.get_frames(dt)
            return frames
        else:
            # Current shutter state
            shutter_state_pre = self.shutter_state
            # Bring shutters to input state
            self.shutter_set(shutter_state, wait=True, verbose=verbose)
            # Take sequence
            frames = self.get_frames(dt)
            # Bring shutters back
            self.shutter_set(shutter_state_pre, wait=True, verbose=verbose)
            return frames
    
    def get_frames_cal(self, dt, dark=None, sequence=False, frames=None):
        """
        Gets a calibrated master science frame (dark- and background-subtracted) and calculates broadband and dispersed data from that.
        Returns:
            1) cal_disp_stack; (2, nwls, nROIs); value and error (axis 1) of/on the dispersed readout (axis 2) in all ROIs (axis 3)
            2) cal_broad_stack; (2, nROIs); value and error (axis 1) of/on the broadband readout in all ROIs (axis 2)
        """
        if dark is None:
            dark = self.dark
        if frames is None:
            frames = self.get_frames(dt)
        if not sequence:
            # Get calibrated master science frame
            cal_mean, cal_mean_std = frames.calib_master_nifits_format(dark)
            # Calculate broadband values and errors
            cal_broad = cal_mean[self.sc_mask,:].sum(axis=0)
            cal_broad_std = np.linalg.norm(cal_mean_std[self.sc_mask,:], axis=0) / len(self.sc_mask)
            # Stack values and errors
            cal_broad_stack = np.stack((cal_broad,cal_broad_std),axis=0)
            cal_disp_stack = np.stack((cal_mean,cal_mean_std),axis=0)
            
            if self.auto_display is not False:
                # Push data to corresponding buffers
                self.buffer_im_IR.push(frames.master_full[0] - dark.master_full[0])
                self.buffer_broad.push(cal_broad_stack)
                # Dispersed data in waterfall format
                cal_disp_stack_waterfall= cal_disp_stack.transpose((0,2,1)).reshape(cal_disp_stack.shape[0],cal_disp_stack.shape[1]*cal_disp_stack.shape[2])
                self.buffer_disp.push(cal_disp_stack_waterfall)
                self.buffer_disp_last.push(cal_mean.transpose((1,0)))
            return cal_disp_stack, cal_broad_stack
        else:
            cal_seq, cal_seq_std = frames.calib_seq_nifits_format(dark)
            return cal_seq, cal_seq_std

    def get_frames_cal_to_np(self, dt, dark=None, sequence=False):
        cal_disp_stack, cal_broad_stack = self.get_frames_cal(dt=dt, dark=dark, sequence=False)
        np.save("cal_disp", cal_disp_stack[0])
        np.save("cal_disp_err", cal_disp_stack[1])
        np.save("cal_broad", cal_broad_stack[0])
        np.save("cal_broad_err", cal_broad_stack[1])
        return

    def science_frame_sequence(self, dt, verbose=False):
        return self.frame_sequence(dt, shutter_state=[1,1,1,1], verbose=verbose)
    
    def dark_frame_sequence(self, dt, verbose=False):
        return self.frame_sequence(dt, shutter_state=[0,0,0,0], verbose=verbose)

    def dark_sequence(self, dt=0.5, verbose=False):
        self.shutter_set(np.array([0,0,0,0]), wait=True, verbose=verbose)
        mydark = self.get_dark(dt=dt)
        self.shutter_set(np.array([1,1,1,1]), wait=True, verbose=verbose)
        return mydark

    def identify_outputs(self,data,rois_crop,rois_data,use_geom=True,snr_thresh=5):
        # 'data' : numpy array containing the calibrated image data of the full master frame
        # 'rois_crop' : list of Roi objects, as defined in the windowed master frame
        # 'rois_data': numpy array containing the calibrated image data of each ROI in the full master frame
        # 'use_geom': If True, define the entire ROI as output. If False, identify output pixels by SNR criterion.
        # 'snr_thresh' : SNR threshold for identification of outputs.
        # ! Limiting calculations to data within the ROIs for efficiency
        # Returns a numpy array of booleans, indicating True for output pixels.
        
        if use_geom:
            outputs_pos = np.ones_like(rois_data,dtype=bool)
        else:
            outputs_pos = (rois_data >= snr_thresh)
            
        fig,ax = plt.subplots(nrows=1,ncols=1,figsize=(8,8))
        fig.suptitle("Please verify correct matching of ROIs to chip outputs.")
        
        ax.imshow(data)
        
        for roi_crop in rois_crop:
            x,y,w,h = roi_crop.x,roi_crop.y,roi_crop.w,roi_crop.h
            rect = patches.Rectangle((x, y), w, h, linewidth=1, edgecolor='r', facecolor='none')
            # Add the patch to the axis
            ax.add_patch(rect)
        
        plt.tight_layout()
        plt.show()
            
        return outputs_pos

    #-------------------------#
    # Surface level functions |
    #-------------------------#

    def characterize_null(self, dt, dark=None, sequence=False, frames=None):
        """
        This function calculates the broadband & dispersed null depths N2, N3 (bright outputs) and Ndiff (differential). Corresponding errors are also calculated.
        Calculated dataframes are pushed to the corresponding buffers for visualization (shmview).
                              are returned by this function.
        If "frames" is left unspecified, the function will fetch frames for this characterization.
        This function does not control any hardware (shutters, DLs, piezos, TTMs ...) on the bench.
        """
        # Fetch data products of a master science frame
        cal_disp_stack, cal_broad_stack = self.get_frames_cal(dt, dark, sequence, frames)
        broad, broad_err = cal_broad_stack[0], cal_broad_stack[1]
        disp, disp_err = cal_disp_stack[0], cal_disp_stack[1]
        # Fetching ROI indices of interferometric outputs
        roi_idx = np.zeros(4)
        for i in range(0,4):
            roi_idx[i] = self.channel_roi_link["I"+str(i+1)]
        idx_I1, idx_I2, idx_I3, idx_I4 = roi_idx[0], roi_idx[1], roi_idx[2], roi_idx[3]

        # Calculating null depths and propagating errors
        # 1) Summing the bright outputs (I1, I4):
        brightsum_broad = broad[idx_I1] + broad[idx_I4]
        brightsum_broad_err = np.hypot(broad_err[idx_I1], broad_err[idx_I4])
        brightsum_disp = disp[:,idx_I1] + disp[:,idx_I4]
        brightsum_disp_err = np.hypot(disp_err[:,idx_I1], disp_err[:,idx_I4])
        # 2) Calculating relative errors
        # a) Relative error sum of brights
        brightsum_broad_rel_err = np.divide(brightsum_broad_err, brightsum_broad)
        brightsum_disp_rel_err = np.divide(brightsum_disp_err, brightsum_disp)
        # b) Relative error individual outputs
        broad_rel_err = np.divide(broad_err, broad)
        disp_rel_err = np.divide(disp_err, disp)
        # 3) Calculating null depths, propagating errors
        N2_broad, N2_disp = np.divide(broad[idx_I2], brightsum_broad), np.divide(disp[:,idx_I2], brightsum_disp)
        N2_broad_err, N2_disp_err = np.multiply(N2_broad, np.hypot(broad_rel_err[idx_I2], brightsum_broad_rel_err)), np.multiply(N2_disp, np.hypot(disp_rel_err[idx_I2], brightsum_disp_rel_err))
        N3_broad, N3_disp = np.divide(broad[idx_I3], brightsum_broad), np.divide(disp[:,idx_I3], brightsum_disp)
        N3_broad_err, N3_disp_err = np.multiply(N3_broad, np.hypot(broad_rel_err[idx_I3], brightsum_broad_rel_err)), np.multiply(N3_disp, np.hypot(disp_rel_err[idx_I3], brightsum_disp_rel_err))
        Ndiff_broad, Ndiff_broad_err = N3_broad - N2_broad, np.hypot(N2_broad_err, N3_broad_err)
        Ndiff_disp, Ndiff_disp_err = N3_disp - N2_disp, np.hypot(N2_disp_err, N3_disp_err)

        # Bundling data
        broad_null = np.stack([N2_broad, N3_broad, Ndiff_broad], [N2_broad_err, N3_broad_err, Ndiff_broad_err], axis=0)
        disp_null = np.stack([N2_disp, N3_disp, Ndiff_disp], axis=1)
        disp_null_err = np.stack([N2_disp_err, N3_disp_err, Ndiff_disp_err], axis=1)

        # Pushing to buffers
        self.buffer_broad_null.push(broad_null)
        self.buffer_disp_null.push(disp_null)
        self.buffer_disp_null_err.push(disp_null_err)
        self.buffer_disp_null_last.push(disp_null.transpose((1,0)))

        return broad_null, disp_null, disp_null_err

    def characterize_null_nifits_format(self, dt, dark=None, sequence=False, frames=None):
        broad_null, disp_null, disp_null_err = self.characterize_null(dt, dark, sequence, frames)

        # WIP

    def modulate_piezo(self, beam_index=None, beam=None, parameters=None):
        default_params = np.array([100,50,1900,2000])
        if isinstance(parameters, str):
            if parameters == "?":
                print(f"Parameters for a triangle wave (all integers):")
                print(f"1. Period multiplier")
                print(f"2. Period multiplier")
                print(f"3. a : half-amplitude (result will be 2a peak-to-peak)")
                print(f"4. offset : Raw value 0-4000")
                return default_params
        elif parameters is None:
            parameters = default_params
        elif isinstance(parameters, np.ndarray):
            pass
        else:
            raise KeyError("Make a valide parameter array")
        beam_index2letter = {
            1:"t",
            2:"y",
            3:"u"
        }
        beam2letter = {
            2:"t",
            3:"y",
            4:"u"
            
        }
        if beam_index is not None:
            self.interf.ser.write(self.interf.vals2bytes(beam_index2letter[beam_index], parameters))


    def find_dark(self, frac=0.25, dt=0.5, gain=0.1,
                 roi_index=3, verbose=True,
                 amp=800.0):
        current_pos = self.get_position()
        pos_a = current_pos[self.act_index] + 1e6 * frac*self.lam_mean
        pos_b = current_pos[self.act_index] - 1e6 * frac*self.lam_mean
        if verbose:
            print(f"Trying {pos_a:.3f} and {pos_b:.3f}")
        a = self.move_and_sample(pos_a, dt=dt, move_back=False)
        b = self.move_and_sample(pos_b, dt=dt, move_back=False)
        # self.move(current_pos[self.act_index])
        a_val = a[:,roi_index].mean(axis=0)
        a_std = a[:,roi_index].std(axis=0)
        b_val = b[:,roi_index].mean(axis=0)
        b_std = b[:,roi_index].std(axis=0)
        raw_offset = a_val - b_val
        p = self.deltaval2p(raw_offset, frac, amp=amp)
        # offset = (raw_offset) * gain
        offset = (p ) * gain
        newpos = current_pos[self.act_index] + offset
        if verbose:
            print(f"a = {a_val:.1f} pm{a_std:.1f},   b = {b_val:.1f} pm{b_std:.1f}")
            print(f"Raw offset : {raw_offset:.3f},  p = {p:.3f}")
            print(f"Moving to {newpos:.3f}")
            import matplotlib.pyplot as plt
            # plt.figure(dpi=70)
            # plt.plot(a[:,roi_index], label="a")
            # plt.plot(b[:,roi_index], label="b")
            # plt.legend(fontsize=6)
            # plt.show()
        self.move(newpos)

    def do_scan(self, beam_index, start=-3.0, end=3.0, nsteps=1000, dt=0.1):
        step_vals = np.linspace(start, end, nsteps)
        starting_pos = self.get_position()
        steps = starting_pos[None,:] * np.ones_like(step_vals)[:,None]
        steps[:,beam_index] = step_vals
        mask = np.zeros(self.nb_beams)
        mask[beam_index] = 1
        step_full = steps[:,None] * mask[None,:]
        if dt is None:
            test_sample = self.sample_long_cal(1.0)
            rms = np.std(test_sample, axis=0)
        print("Starting a scan")
        results = []
        stds = []
        for n, astep in enumerate(tqdm(steps)):
            ares = self.move_and_sample(astep, move_back=False, dt=dt)
            results.append(np.mean(ares, axis=0))
            if dt is not None:
                stds.append(np.std(ares, axis=0) / np.sqrt(ares.shape[0]))
            else:
                stds.append(rms)
        results = np.array(results)
        stds = np.array(stds)
        self.move(starting_pos)
        print("Scan ended")
        return steps, results, stds

    def evaluate_lag(self, act_index, n=10, lag_min=0.05, lag_max=0.15, amplitude=0.5, roi_index=3):
        start_pos = self.get_position()
        lags = np.linspace(lag_min,lag_max, n)
        signal_amplitudes = []
        signal_stds = []
        for i, alag in enumerate(lags):
            measurements = []
            for i in range(8):
                newpos = copy(start_pos)
                newpos[act_index] += amplitude
                self.move(newpos)
                sleep(alag)
                val1 = self.sample()[roi_index]
                self.move(start_pos)
                sleep(alag)
                val2 = self.sample()[roi_index]
                measurements.append(val1 - val2)
            measurements = np.array(measurements)
            signal_amplitudes.append(measurements.mean())
            signal_stds.append(measurements.std())
        signal_amplitudes = np.array(signal_amplitudes)
        signal_stds = np.array(signal_stds)
        plt.figure()
        plt.plot(lags, signal_amplitudes)
        plt.errorbar(lags, signal_amplitudes, yerr=signal_stds)
        plt.xlabel("Lag [s]")
        plt.ylabel("Amplitude of light variation")
        plt.show()

    def chip_calib_direct(self, mode_series, dt=0.5,
                    kappa=None, kappa_std=None,
                    mode_shutter_probe=None,
                    offset_scan=0.,
                    saveto="/dev/shm/cal_dir.fits",
                    overwrite=True,
                    dn_object=None, bidir=True, verbose=False,
                    kappa_threshold = 1e-2):
        from astropy.time import Time
        if saveto is not None:
            prefix = "HIERARCH NOTT "
            import astropy.io.fits as fits
            hdulist = fits.HDUList()
            myheader = fits.Header([(prefix+"co2_ppm", 1e6),
                                 (prefix+"temp", 25.0),
                                 (prefix+"rhum", 0.3),
                                 (prefix+"pres", 1e3),
                                 (prefix+"co2" , 450),
                                 (prefix+"co2" , 450),
                                 (prefix+"exptime", dt),
                                 ("DATE-OBS", Time.now().isot)])
            hdulist.append(fits.PrimaryHDU(header=myheader))
        test_conditions = {
            "co2_ppm": 1e6,
            "temp": 25.0,
            "rhum": 0.3,
            "pres": 1e3,
            "co2" : 450,
        }
        ntel = 4
        print("Kappa matrix")
        #m = self.get_dark(dt)   #Darks are defined at the beginning (to check)

        if dt is None:
            cal_disp_stack, cal_broad_stack = self.get_frames_cal(1.0)
            test_sample, rms = cal_disp_stack[0], cal_disp_stack[1] 

        if kappa is None:
            inherit_kappa = False
            if verbose:
                print("Making a new kappa matrix")
            myprobe = shutter_probe(ntel)
            shutter_state = np.abs(myprobe[0]).astype(bool)
            self.shutter_set(shutter_state)
            kappa = []
            std_kappa = []
            for beam in myprobe:
                shutter_state = np.abs(beam).astype(bool)
                self.shutter_set(shutter_state)
                cal_disp_stack, cal_broad_stack = self.get_frames_cal(dt)
                a, a_std = cal_disp_stack[0], cal_disp_stack[1]
                kappa.append(a)
                if dt is not None:
                    std_kappa.append(a_std)
                else:
                    std_kappa.append(rms)
            kappa = np.array(kappa)
            std_kappa = np.array(std_kappa)
    
            sleep(2.0)
    
            #Compute the element of the kappa matrix
            print(f"Shape: ", kappa.shape)
            # (5, 106, 10)
            # (frame, wl, output)
            n_wl = kappa.shape[1]
            kappa_new = []
            for kappa_line in kappa[1:]:
                kappa_new.append(kappa_line-kappa[0])  #Background correction
            kappa_new = np.array(kappa_new)
            kappa_new = kappa_new[:,:,:-2]   #Removes the background ROI values
            for i, akrow in enumerate(kappa_new):
                kappa_new[i,:,:] = akrow / (np.sum(akrow) / n_wl)
            for k, acell in np.ndenumerate(kappa_new):
                if kappa_new[k] <= kappa_threshold:
                    kappa_new[k] = 0.
            kappa_old = np.copy(kappa)
            kappa = np.copy(kappa_new)
        else: # kappa is provided
            inherit_kappa = True
            if verbose: print("Reusing kappa")
            pass
        print("Transfer matrix")   
        if mode_shutter_probe is None:
            self.shutter_set(np.ones(4).astype(bool))
        else:
            raise NotImplementedError("Not implemented direct calib with shutters: Do your kappa matrix separately")
        mode_set = offset_scan + mode_series
        f0 = 0.5/self.lam_mean * 1e-6
        test_conditions["stepseries"] = mode_set
        all_pistons = []
        all_fringes = []
        all_fringes_std = []
        for amodesteps in mode_set:
            # self.shutter_set(shutter_state)
            # sleep(self.shutter_pad)
            # mysequence = amode[None,:] * stepseries[:,None]
            fringes, fringes_std = [], []
            pistons = []
            if verbose : print("Scan of mode: ", amodesteps)
            for apos in amodesteps:
                a, a_std = self.move_and_sample(apos, dt=dt, move_back=False)
                fringes.append(a)
                fringes_std.append(a_std)
                if dt is not None:
                    fringes_std.append(a_std)
                else:
                    fringes_std.append(rms)
                pistons.append(apos)
            pistons = np.array(pistons)
            fringes_std = np.array(fringes_std)
            fringes = np.array(fringes)
            all_fringes.append(fringes)
            all_fringes_std.append(fringes_std)
            all_pistons.append(pistons)
            # phases = 2*np.pi/(self.lambs[None,:]*1e6) * relsteps[:,None]
        all_fringes = np.array(all_fringes)
        all_fringes_std = np.array(all_fringes_std)
        all_pistons = np.array(all_pistons)
        self.move(np.array([0., 0., 0., 0.]))
        self.shutter_set(np.ones(4).astype(bool))
        phases = 2*np.pi / (self.sc_lambs[None,None,:,None]*1.0e6) * all_pistons[:,:,None,:]

        if saveto is not None:
            if inherit_kappa:
                hdulist.append(fits.hdu.ImageHDU(data=kappa, name="KAPPA", header=None))
                hdulist.append(fits.hdu.ImageHDU(data=kappa_std, name="KAPPAE", header=None))
            else:
                hdulist.append(fits.hdu.ImageHDU(data=kappa.T[:,self.sc_mask,:], name="KAPPA", header=None))
                hdulist.append(fits.hdu.ImageHDU(data=std_kappa.T[:,self.sc_mask,:], name="KAPPAE", header=None))
            # hdulist.append(fits.hdu.ImageHDU(data=A, name="A", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=mode_series, name="MODE-SER", header=None,))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes[:,:,self.sc_mask,:-2], name="FRINGES", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes_std[:,:,self.sc_mask,:-2], name="FRINGESE", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes[:,:,self.sc_mask,-2:], name="BG", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes_std[:,:,self.sc_mask,-2:], name="BGE", header=None))
            # hdulist.append(fits.hdu.ImageHDU(data=PHI_dft, name="PHI", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_pistons, name="PISTONS", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=self.sc_lambs, name="WAVELENGTHS", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=phases, name="PHASES", header=None))
            hdulist.writeto(saveto, overwrite=overwrite)
        return fringes

    def chip_calib_pairwise(self, amp, steps=10, dt=0.5,
                    offset_scan=0., saveto="/dev/shm/cal_raw.fits",
                    overwrite=True,
                    dn_object=None, bidir=True, verbose=False,
                    kappa_threshold = 1e-2):
        from astropy.time import Time
        if saveto is not None:
            prefix = "HIERARCH NOTT "
            import astropy.io.fits as fits
            hdulist = fits.HDUList()
            myheader = fits.Header([(prefix+"co2_ppm", 1e6),
                                 (prefix+"temp", 25.0),
                                 (prefix+"rhum", 0.3),
                                 (prefix+"pres", 1e3),
                                 (prefix+"co2" , 450),
                                 (prefix+"co2" , 450),
                                 (prefix+"exptime", dt),
                                 ("DATE-OBS", Time.now().isot)])
            hdulist.append(fits.PrimaryHDU(header=myheader))
        test_conditions = {
            "co2_ppm": 1e6,
            "temp": 25.0,
            "rhum": 0.3,
            "pres": 1e3,
            "co2" : 450,
        }
        ntel = 4
        print("Kappa matrix")
        myprobe = shutter_probe(ntel)
        shutter_state = np.abs(myprobe[0]).astype(bool)
        self.shutter_set(shutter_state)
        #m = self.get_dark(dt)   #Darks are defined at the beginning (to check)

        if dt is None:
            cal_disp_stack, cal_broad_stack = self.get_frames_cal(1.0)
            test_sample, rms = cal_disp_stack[0], cal_disp_stack[1] 

        kappa = []
        std_kappa = []
        for beam in myprobe:
            shutter_state = np.abs(beam).astype(bool)
            self.shutter_set(shutter_state)
            cal_disp_stack, cal_broad_stack = self.get_frames_cal(dt)
            a, a_std = cal_disp_stack[0], cal_disp_stack[1]
            kappa.append(a)
            if dt is not None:
                std_kappa.append(a_std)
            else:
                std_kappa.append(rms)
        kappa = np.array(kappa)
        std_kappa = np.array(std_kappa)
    
        sleep(2.0)
    
        #Compute the element of the kappa matrix
        print(f"Shape: ", kappa.shape)
        # (5, 106, 10)
        # (frame, wl, output)
        n_wl = kappa.shape[1]
        kappa_new = []
        for kappa_line in kappa[1:]:
            kappa_new.append(kappa_line-kappa[0])  #Background correction
        kappa_new = np.array(kappa_new)
        kappa_new = kappa_new[:,:,:-2]   #Removes the background ROI values
        for i, akrow in enumerate(kappa_new):
            kappa_new[i,:,:] = akrow / (np.sum(akrow) / n_wl)
        for k, acell in np.ndenumerate(kappa_new):
            if kappa_new[k] <= kappa_threshold:
                kappa_new[k] = 0.
        kappa_old = np.copy(kappa)
        kappa = np.copy(kappa_new)
        print("Transfer matrix")   
    
        A = np.array([[1,-1,0,0],
                      [1,0,-1,0],
                      [1,0,0,-1],
                      [0,1,-1,0],
                      [0,1,0,-1],
                      [0,0,1,-1]])
        stepseries = offset_scan + np.linspace(-amp, amp, steps)
        f0 = 0.5/self.lam_mean * 1e-6
        test_conditions["A"] = A
        test_conditions["stepseries"] = stepseries
        all_pistons = []
        all_fringes = []
        all_fringes_std = []
        for amode in A:
            shutter_state= np.abs(amode).astype(bool)
            self.shutter_set(shutter_state)
            sleep(10 * self.pad)
            mysequence = amode[None,:] * stepseries[:,None]
            fringes, fringes_std = [], []
            pistons = []
            print("Scan of baseline: ",amode)
            for apos in mysequence:
                a, a_std = self.move_and_sample(apos, dt=dt, move_back=False)
                fringes.append(a)
                if dt is not None:
                    fringes_std.append(a_std)
                else:
                    fringes_std.append(rms)
                pistons.append(apos)
            fringes_std = np.array(fringes_std)
            fringes = np.array(fringes)
            all_fringes.append(fringes)
            all_fringes_std.append(fringes_std)
            all_pistons.append(pistons)
            relsteps = 2*stepseries
            # phases = 2*np.pi/(self.lambs[None,:]*1e6) * relsteps[:,None]
        all_fringes = np.array(all_fringes)
        all_fringes_std = np.array(all_fringes_std)
        all_pistons = np.array(all_pistons)
        self.move(np.array([0., 0., 0., 0.]))
        self.shutter_set(np.ones(4).astype(bool))
        phases = 2*np.pi / (self.sc_lambs[None,None,:,None]*1.0e6) * all_pistons[:,:,None,:]

        if saveto is not None:
            hdulist.append(fits.hdu.ImageHDU(data=kappa.T[:,self.sc_mask,:], name="KAPPA", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=std_kappa.T[:,self.sc_mask,:], name="KAPPAE", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=A, name="A", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes[:,:,self.sc_mask,:-2], name="FRINGES", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes_std[:,:,self.sc_mask,:-2], name="FRINGESE", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes[:,:,self.sc_mask,-2:], name="BG", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes_std[:,:,self.sc_mask,-2:], name="BGE", header=None))
            # hdulist.append(fits.hdu.ImageHDU(data=PHI_dft, name="PHI", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_pistons, name="PISTONS", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=self.sc_lambs, name="WAVELENGTHS", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=phases, name="PHASES", header=None))
            hdulist.writeto(saveto, overwrite=overwrite)
        return kappa, A, test_conditions

    def process_calib_pairwise(self, datafile="/dev/shm/cal_raw_d.fits",
                               saveto="/dev/shm/constructed_catm.nifits",
                               overwrite=True,
                              verbose=False, ):
        import astropy.io.fits as fits
        prefix = "HIERARCH NOTT "
        hdul = fits.open(datafile)
        phases = hdul["PHASES"].data
        fringes = hdul["FRINGES"].data
        A = hdul["A"].data
        kappa = hdul["KAPPA"].data
        PHI = []
        for i, amode in enumerate(A):
            sleep(10 * self.pad)
            print("Scan of baseline: ",amode)
            dft_phasor = np.exp(1j * phases)
            dft = dft_phasor.dot(fringes[i] - fringes[i].mean(axis=0))
            if verbose:
                plt.figure()
                plt.plot(phases, fringes[i,:,3], color="C0")
                plt.plot(phases, fringes[i,:,4], color="C1")
                ax2 = plt.gca().twinx()
                ax2.plot(phases, np.abs(dft[3])*dft_phasor.real, color="k", linestyle=":")
                ax2.plot(phases, np.real(dft[3] * np.conj(dft_phasor)), color="C0", linestyle="--")
                ax2.axvline(np.angle(dft[3]), color="C0")
                ax2.plot(phases, np.real(dft[4] * np.conj(dft_phasor)), color="C1", linestyle="--")
                ax2.axvline(np.angle(dft[4]), color="C1")
                for ks in np.arange(-1,2):
                    plt.axvline(np.pi * ks, color="k", linewidth=0.5)
                plt.title(f"""amp = {np.abs(dft[3]):.2f}, phase = {np.angle(dft[3]):.2f}
                            amp = {np.abs(dft[4]):.2f}, phase = {np.angle(dft[4]):.2f}""")
                plt.show()
            PHI.append(np.angle(dft))
        PHI = np.array(PHI)
        print("PHI ", PHI.shape)
        A2 = A[:3,:]
        Ap = np.linalg.pinv(A2)
        phi = (Ap.dot(-PHI[:3,:])).T
        print("phi ", phi.shape)
        phi = phi - phi[:,0][:,None]
        print("phi ", phi.shape)
        phi_all = np.zeros_like(kappa)
    
        print("phi_all ", phi_all.shape)
        phi_all[3:5,:] = phi[3:5,:]
        phi_all[2,1] = PHI[0,2]
        phi_all[5,2] = 0 # This is debatable
        phi_all[5,3] = PHI[-1,5] - phi_all[5,2]

        M = np.sqrt(kappa)*np.exp(1j*phi_all)
        if verbose:
            from kernuller.diagrams import plot_outputs_smart as kplot
            kplot(M)
        if saveto is not None:
            from nifits.io import oifits as io
            ni_catm = io.NI_CATM(data_array=M)
            mynifit = io.nifits(header=hdul[0].header,
                                ni_catm=ni_catm)
        return M

    def chip_calib(self, amp, steps=10, dt=0.5,
                    dn_object=None, bidir=True):
        test_conditions = {
            "co2_ppm": 1e6,
            "temp": 25.0,
            "rhum": 0.3,
            "pres": 1e3,
            "co2" : 450,
        }
        ntel = 4
        myprobe, piston_probe = full_hadamard_probe(ntel, amp, steps=steps, bidir=True)
        # myprobe = shutter_probe(ntel)
        shutter_phasor = np.ones_like(self.sc_lambs)[None,:,None] * myprobe[:,None,:]
        hadamard_phasor = np.exp(1j*2*np.pi/self.sc_lambs[None,:,None] * 1e-6*piston_probe[:,None,:])
        probe_series = np.concatenate((shutter_phasor, hadamard_phasor), axis=0)
        amplitude_full = np.ones((myprobe.shape[0] + piston_probe.shape[0], myprobe.shape[1]))
        amplitude_full[:myprobe.shape[0], :] *= myprobe
        piston_full = np.ones_like(amplitude_full)
        piston_full[-piston_probe.shape[0]:, :] = piston_probe
        test_conditions["amplitude_full"] = amplitude_full
        test_conditions["piston_full"] = piston_full
        test_conditions["probe_series"] = probe_series

        if dt is None:
            test_sample = self.sample_long_cal(1.0)
            rms = np.std(test_sample, axis=0)

        print("shutter_calibration")
        print("Assuming all start open")
        measurements = []
        stds = []
        beam_state = np.ones(ntel, dtype=bool)
        for aprobe in myprobe.astype(bool):
            print("aprobe:", aprobe, "beam_state", beam_state)
            for i, (astate, target_state) in enumerate(zip(beam_state, aprobe)):
                beam_id = i
                # print(astate, target_state)
                if astate != target_state:
                    # print("Changing")
                    if target_state:
                        print(f"Opening {beam_id}")
                        self.shutters[beam_id].open()
                        beam_state[i] = True
                    else:
                        print(f"Closing {beam_id}")
                        self.shutters[beam_id].close()
                        beam_state[i] = False
            print(beam_state)
            sleep(3 * self.pad)
            a = self.sample_long_cal(dt=dt)
            measurements.append(a.mean(axis=0))
            if dt is not None:
                stds.append(a.std(axis=0)/np.sqrt(a.shape[0]))
            else:
                stds.append(rms)
        for ashutter in self.shutters:
            ashutter.open()
        print("Sleeping to avoid shutter vibrations")
        sleep(2.0)

        initial_position = self.get_position()
        for aprobe in piston_probe:
            # Move_and_sample
            a = self.move_and_sample(aprobe, dt=dt, move_back=False)
            # append
            measurements.append(a.mean(axis=0))
            if dt is not None:
                stds.append(a.std(axis=0)/np.sqrt(a.shape[0]))
            else:
                stds.append(rms)
        self.move(initial_position)
        measurements = np.array(measurements)
        stds = np.array(stds)
        return measurements, stds, test_conditions


# TODO: adjust the calibration strategy and long integration strategy for when we miss frames

