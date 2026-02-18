import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from time import sleep, time
from tqdm import tqdm
from copy import copy
from datetime import datetime,timedelta,timezone

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
from nottcontrol.script.lib.nott_database import get_field
from configparser import ConfigParser
from nottcontrol import config 

opcuad = config["DEFAULT"]["opcuaaddress"]

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


class HumInt(object):
    def __init__(self, lam_mean=mean_wl,
                pad=0.15, interf=None,
                act_index=0,
                rois_interest=np.arange(1,10),
                verbose=False,
                db_server=None,
                opcuad=opcuad,
                nb_beams=4,
                non_motorized=0,
                offset = 8.0,snr_thresh=5):
        # self.lamb_min = lam_range[0]
        # self.lamb_max = lam_range[-1]
        self.lam_mean = lam_mean
        self.pad = pad
        self.shutter_pad = 5.5
        self.interf = interf
        self.act_index = act_index
        self.non_motorized = non_motorized # Index of the non-motorized beam
        self.nb_beams = nb_beams
        self.offset = offset * np.ones(self.nb_beams)
        self.offset[self.non_motorized] = 0
        self.verbose = verbose
        self.ts = db_server
        self.rois = [f"roi{n}_sum" for n in rois_interest]
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
        self.move(np.array([0., 0., 0., 0.]))

    # Auxiliary functions
    
    def __del__(self):
        self.opcua_conn.disconnect()
    
    def db_time(self):
        aresp = self.ts.ts.get(f"cam_integtime")
        return aresp[0]

    def four2three(self, position):
        return position - position[self.non_motorized]

    def deltaval2p(self, deltaval, frac, amp=800.):
        lam_micron = 1.0e6 * self.lam_mean
        deltap = lam_micron * frac
        inner = -deltaval / (amp * 2 * np.sin(2*np.pi/lam_micron * deltap))
        p = lam_micron /(2*np.pi) * np.arcsin(inner)
        return p

    # Shutter control functions
    
    def shutter_set(self, values, wait=True, verbose=False):
        if not isinstance(values, np.ndarray):
            thevalues = np.array(values)
        else:
            thevalues = values
        for i, ashutter in enumerate(self.shutters):
            values_bool = values.astype(bool)
            if values_bool[i]:
                ashutter.open()
            else:
                ashutter.close()
        if wait:
            sleep(self.shutter_pad)
        if verbose:
            for i, ashutter in enumerate(self.shutters):
                print(i, ashutter.getStatusInformation()[1], ashutter.getPositionAndSpeed()[0])

    # Piezo control functions

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

    # Sample functions

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
            res, std = self.get_frames_cal(dt=dt, dark=dark, sequence=False)
        if move_back:
            print(f"moving_back to {orig_pos}")
            self.move(orig_pos)
            sleep(self.pad)
        return res, std

    # Image calibration functions 

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

    def get_frames_cal(self, dt, dark=None, sequence=False):
        if dark is None:
            dark = self.dark
        frame = self.get_frames(dt)
        if not sequence:
            cal_mean, cal_mean_std = frame.calib_master_nifits_format(dark)
            return cal_mean, cal_mean_std
        else:
            cal_seq, cal_seq_std = frame.calib_seq_nifits_format(dark)
            return cal_seq, cal_seq_std

    def science_frame_sequence(self, dt, verbose=False):
        sci_frames = self.get_frames(dt) 
        return sci_frames

    def dark_sequence(self, dt=0.5, verbose=False):
        self.shutter_set(np.array([0,0,0,0]), wait=True, verbose=verbose)
        mydark = self.get_dark(dt=dt)
        self.shutter_set(np.array([1,1,1,1]), wait=True, verbose=verbose)
        return mydark
        
    def dark_frame_sequence(self, dt, verbose=False):
        self.shutter_set(np.array([0,0,0,0]), wait=True, verbose=verbose)
        dark_frames = self.get_frames(dt) 
        self.shutter_set(np.array([1,1,1,1]), wait=True, verbose=verbose)
        return dark_frames

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

    # Surface level functions
    
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

    def chip_calib_pairwise(self, amp, steps=10, dt=0.5,
                    offset_scan=0., saveto="/dev/shm/cal_raw.fits",
                    overwrite=True,
                    dn_object=None, bidir=True, verbose=False):
        import dnull as dn
        if saveto is not None:
            prefix = "HIERARCH NOTT "
            import astropy.io.fits as fits
            hdulist = fits.HDUList()
            myheader = fits.Header([(prefix+"co2_ppm", 1e6),
                                 (prefix+"temp", 25.0),
                                 (prefix+"rhum", 0.3),
                                 (prefix+"pres", 1e3),
                                 (prefix+"co2" , 450)])
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
        shutter_probe = dn.dnull.shutter_probe(ntel)
        shutter_state = np.abs(shutter_probe[0]).astype(bool)
        self.shutter_set(shutter_state)
        #m = self.get_dark(dt)   #Darks are defined at the beginning (to check)

        if dt is None:
            test_sample, rms = self.get_frames_cal(1.0)

        kappa = []
        std_kappa = []
        for beam in shutter_probe:
            shutter_state = np.abs(beam).astype(bool)
            self.shutter_set(shutter_state)
            a, a_std = self.get_frames_cal(dt)
            kappa.append(a)
            if dt is not None:
                std_kappa.append(a_std)
            else:
                std_kappa.append(rms)
        kappa = np.array(kappa)
        std_kappa = np.array(std_kappa)
    
        sleep(2.0)
    
        #Compute the element of the kappa matrix
        kappa_new = []
        for kappa_line in kappa[1:]:
            kappa_new.append(kappa_line-kappa[0])  #Background correction
        kappa_new = np.array(kappa_new)
        kappa_new = kappa_new[:,:-1]   #Removes the background ROI values
        for i in range(len(kappa_new)):
            kappa_new[i] = kappa_new[i]/np.sum(kappa_new[i])  #Normalize the column of the matrix with the sum
            for j in range(len(kappa_new[i])): 
                if kappa_new[i,j] < 1e-2:
                    kappa_new[i,j] = 0
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
        all_fringes = []
        all_fringes_std = []
        for amode in A:
            shutter_state= np.abs(amode).astype(bool)
            self.shutter_set(shutter_state)
            sleep(10 * self.pad)
            mysequence = amode[None,:] * stepseries[:,None]
            fringes, fringes_std = [], []
            print("Scan of baseline: ",amode)
            for apos in mysequence:
                a, a_std = self.move_and_sample(apos, dt=dt, move_back=False)
                fringes.append(a.mean(axis=0))
                fringes_std.append(a_std)
                if dt is not None:
                    fringes_std.append(a_std)
                else:
                    fringes_std.append(rms)
            fringes_std = np.array(fringes_std)
            fringes = np.array(fringes)
            all_fringes.append(fringes)
            all_fringes_std.append(fringes_std)
            relsteps = 2*stepseries
            phases = 2*np.pi/(self.lam_mean*1e6) * relsteps
        all_fringes = np.array(all_fringes)
        all_fringes_std = np.array(all_fringes_std)
        self.move(np.array([0., 0., 0., 0.]))
        self.shutter_set(np.ones(4).astype(bool))

        if saveto is not None:
            hdulist.append(fits.hdu.ImageHDU(data=kappa.T, name="KAPPA", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=std_kappa, name="KAPPAE", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=A, name="A", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes[:,:,:-1], name="FRINGES", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes_std[:,:,:-1], name="FRINGESE", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes[:,:,-1], name="BG", header=None))
            hdulist.append(fits.hdu.ImageHDU(data=all_fringes_std[:,:,-1], name="BGE", header=None))
            # hdulist.append(fits.hdu.ImageHDU(data=PHI_dft, name="PHI", header=None))
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
        import dnull as dn
        import jax.numpy as jp
        test_conditions = {
            "co2_ppm": 1e6,
            "temp": 25.0,
            "rhum": 0.3,
            "pres": 1e3,
            "co2" : 450,
        }
        ntel = 4
        shutter_probe, piston_probe = dn.dnull.full_hadamard_probe(ntel, amp, steps=steps, bidir=True)
        # shutter_probe = dn.dnull.shutter_probe(ntel)
        shutter_phasor = jp.ones_like(self.lambs)[None,:,None] * shutter_probe[:,None,:]
        hadamard_phasor = jp.exp(1j*2*np.pi/self.lambs[None,:,None] * 1e-6*piston_probe[:,None,:])
        probe_series = jp.concatenate((shutter_phasor, hadamard_phasor), axis=0)
        amplitude_full = np.ones((shutter_probe.shape[0] + piston_probe.shape[0], shutter_probe.shape[1]))
        amplitude_full[:shutter_probe.shape[0], :] *= shutter_probe
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
        for aprobe in shutter_probe.astype(bool):
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

